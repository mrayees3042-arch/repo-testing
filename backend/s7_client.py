import snap7
try:
    from snap7.error import S7Error as Snap7Exception, S7ConnectionError, S7ProtocolError
except ImportError:
    try:
        from snap7.snap7exceptions import Snap7Exception
        S7ConnectionError = Snap7Exception
        S7ProtocolError = Snap7Exception
    except ImportError:
        try:
            from snap7.exceptions import Snap7Exception
            S7ConnectionError = Snap7Exception
            S7ProtocolError = Snap7Exception
        except ImportError:
            class Snap7Exception(Exception): pass
            class S7ConnectionError(Snap7Exception): pass
            class S7ProtocolError(Snap7Exception): pass

import time
import socket
import subprocess
import platform
import threading
import logging

logger = logging.getLogger(__name__)

class S7Client:
    def __init__(self):
        self.client = snap7.client.Client()
        self.connected = False
        self._lock = threading.Lock()
        
    def _is_transport_error(self, err):
        """Check if an exception indicates a socket or transport layer disconnection."""
        if isinstance(err, (S7ConnectionError, socket.error, ConnectionResetError, 
                            ConnectionAbortedError, BrokenPipeError, TimeoutError)):
            return True
        msg = str(err).lower()
        transport_keywords = [
            "not connected",
            "connection reset",
            "connection closed",
            "connection aborted",
            "unreachable peer",
            "broken pipe",
            "socket closed",
            "transport endpoint",
            "eof",
            "tcp : connection reset",
            "iso : connection closed",
            "tcp : unreachable peer"
        ]
        return any(k in msg for k in transport_keywords)

    def is_connected(self):
        """Check if the client is logically and physically connected."""
        with self._lock:
            if not self.connected:
                return False
            try:
                if hasattr(self.client, 'get_connected'):
                    return bool(self.client.get_connected())
                return True
            except Exception:
                self.connected = False
                return False

    def ping(self, ip_address, timeout=2.0):
        """Perform an ICMP ping to the target IP using the OS ping command."""
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', '-w', str(int(timeout * 1000)), ip_address]
        
        start_time = time.time()
        try:
            creationflags = 0
            if platform.system().lower() == 'windows':
                creationflags = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                creationflags=creationflags,
                text=True
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if result.returncode == 0:
                out_lower = result.stdout.lower()
                if "ttl=" in out_lower:
                    return True, "Success", elapsed_ms
                if ("unreachable" in out_lower or "timeout" in out_lower or "timed out" in out_lower
                    or "100% loss" in out_lower or "verlust" in out_lower or "perte" in out_lower):
                    return False, "Destination host unreachable", elapsed_ms
                return True, "Success", elapsed_ms
            else:
                return False, f"Ping failed (code {result.returncode})", elapsed_ms
        except Exception as e:
            return False, str(e), int((time.time() - start_time) * 1000)

    def test_tcp_connection(self, ip, port, timeout=2.0):
        """Test if the TCP port is open before attempting S7 connection to provide better diagnostics."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((ip, port))
            return True, "TCP Port Open"
        except socket.timeout:
            return False, f"TCP connection to {ip}:{port} timed out."
        except ConnectionRefusedError:
            return False, f"TCP connection to {ip}:{port} was refused."
        except Exception as e:
            return False, f"TCP connection failed: {str(e)}"
            
    def connect(self, ip, rack, slot, port=102):
        """Connect to the S7 PLC."""
        with self._lock:
            if self.connected:
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                finally:
                    self.connected = False
                
            # Recreate the client object to ensure a clean state
            try:
                if hasattr(self.client, 'destroy'):
                    self.client.destroy()
            except Exception:
                pass
            self.client = snap7.client.Client()
            
            # Set timeouts (1500ms default prevents false drops on plant network jitter)
            try:
                self.client.set_param(5, 1500) # RecvTimeout
                self.client.set_param(4, 1500) # SendTimeout
                self.client.set_param(3, 1000) # PingTimeout
            except Exception:
                pass
                
            # Test TCP connection first
            tcp_ok, tcp_err = self.test_tcp_connection(ip, port)
            if not tcp_ok:
                return False, tcp_err, 0
                
            start_time = time.time()
            try:
                self.client.connect(ip, rack, slot, tcp_port=port)
                self.connected = True
                elapsed_ms = int((time.time() - start_time) * 1000)
                return True, "Connected successfully", elapsed_ms
            except Snap7Exception as e:
                self.connected = False
                return False, f"S7 connection failed: {str(e)}", int((time.time() - start_time) * 1000)
            except Exception as e:
                self.connected = False
                return False, f"Unexpected error during connection: {str(e)}", int((time.time() - start_time) * 1000)

    def disconnect(self):
        """Disconnect from the PLC."""
        with self._lock:
            if getattr(self, 'connected', False):
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                finally:
                    self.connected = False
                    
            try:
                if hasattr(self.client, 'destroy'):
                    self.client.destroy()
            except Exception:
                pass
            self.client = snap7.client.Client()
            return True, "Disconnected"
        
    def decode_cpu_state(self, raw_state):
        """Decode the raw CPU state returned by snap7."""
        if isinstance(raw_state, str):
            state_upper = raw_state.upper()
            if "RUN" in state_upper: return "RUN"
            if "STOP" in state_upper: return "STOP"
            return "UNKNOWN"
            
        if hasattr(raw_state, 'name'):
            name_upper = raw_state.name.upper()
            if "RUN" in name_upper: return "RUN"
            if "STOP" in name_upper: return "STOP"
            return "UNKNOWN"
            
        if isinstance(raw_state, int):
            if raw_state == 8: return "RUN"
            if raw_state == 4: return "STOP"
            return "UNKNOWN"
            
        return "UNKNOWN"

    def get_cpu_state(self):
        """
        Retrieve the CPU state.
        Distinguishes unsupported CPU-state requests from transport failures.
        """
        with self._lock:
            if not getattr(self, 'connected', False):
                return False, "Not connected", "CPU_STATE Not connected"
                
            try:
                raw_state = self.client.get_cpu_state()
                raw_type = type(raw_state).__name__
                decoded = self.decode_cpu_state(raw_state)
                diagnostic_msg = f"CPU_STATE raw={raw_state} type={raw_type} decoded={decoded}"
                
                if decoded in ["RUN", "STOP"]:
                    return True, decoded, diagnostic_msg
                else:
                    return True, f"UNKNOWN ({raw_state})", diagnostic_msg
                    
            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e)
                diagnostic_msg = f"CPU_STATE raw=ERROR type={error_type} decoded=UNKNOWN ({error_str})"
                
                # Check for transport failure
                if self._is_transport_error(e):
                    self.connected = False
                    try:
                        self.client.disconnect()
                    except Exception:
                        pass
                    return False, f"Transport failure: {error_str}", diagnostic_msg
                
                # Check for unsupported service (e.g. S7ProtocolError 0x8104 / 0x8404 on S7-1200 / PLCSIM)
                error_lower = error_str.lower()
                if (isinstance(e, S7ProtocolError) or
                    "s7 protocol error" in error_lower or 
                    "the function cannot be performed" in error_lower or 
                    "job pending" in error_lower or 
                    "service is not implemented" in error_lower or
                    "0x81" in error_lower or
                    "0x84" in error_lower):
                    # Supported PLC connection, but CPU-state service not implemented
                    return True, "UNKNOWN — CPU state unavailable", diagnostic_msg
                    
                # Unknown failure, do not immediately assume disconnected unless transport error
                return False, f"Failed: {error_str}", diagnostic_msg

    def _get_area_enum(self, area_str):
        area_str = area_str.upper()
        if area_str in ["M", "MK"]: return snap7.type.Areas.MK
        if area_str in ["I", "E", "PE"]: return snap7.type.Areas.PE
        if area_str in ["Q", "A", "PA"]: return snap7.type.Areas.PA
        if area_str == "DB": return snap7.type.Areas.DB
        raise ValueError(f"Unknown area: {area_str}")

    def read_tag(self, area_str, db_number, byte_offset, bit_offset, data_type):
        """Read a tag value from the PLC."""
        import backend.tag_utils as tag_utils
        
        with self._lock:
            if not getattr(self, 'connected', False):
                return False, "Not connected"
            
            try:
                area = self._get_area_enum(area_str)
                size = tag_utils.get_data_type_size(data_type)
                
                start_time = time.time()
                buffer = self.client.read_area(area, db_number, byte_offset, size)
                latency = int((time.time() - start_time) * 1000)
                
                val = tag_utils.decode_value(buffer, data_type, bit_offset)
                return True, val
                
            except Exception as e:
                if self._is_transport_error(e):
                    self.connected = False
                    try:
                        self.client.disconnect()
                    except Exception:
                        pass
                return False, str(e)

    def write_tag(self, area_str, db_number, byte_offset, bit_offset, data_type, value):
        """
        Write a tag value to the PLC with read-modify-write for BOOL to preserve neighboring bits.
        Normalizes input before writing.
        """
        import backend.tag_utils as tag_utils
        
        with self._lock:
            if not getattr(self, 'connected', False):
                return False, "Not connected"
                
            try:
                area = self._get_area_enum(area_str)
                size = tag_utils.get_data_type_size(data_type)
                
                if data_type.upper() == "BOOL":
                    norm_val = tag_utils.normalize_bool(value)
                    # Read-modify-write for BOOL to prevent adjacent bit corruption
                    buffer = self.client.read_area(area, db_number, byte_offset, 1)
                    tag_utils.encode_value(norm_val, data_type, buffer, bit_offset)
                    self.client.write_area(area, db_number, byte_offset, buffer)
                else:
                    buffer = bytearray(size)
                    tag_utils.encode_value(value, data_type, buffer, 0)
                    self.client.write_area(area, db_number, byte_offset, buffer)
                    
                return True, "Success"
                
            except Exception as e:
                if self._is_transport_error(e):
                    self.connected = False
                    try:
                        self.client.disconnect()
                    except Exception:
                        pass
                return False, str(e)
