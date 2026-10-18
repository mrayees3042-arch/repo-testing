import time
import logging
import threading
import datetime
from backend.s7_client import S7Client
from backend.tag_manager import TagManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PLCManager:
    def __init__(self):
        self.plcs = {} # ID -> dict of config and state
        self.active_plc_id = None
        self._running = True
        self.tag_manager = TagManager(self)
        self.last_tag_poll = 0
        
        self._monitor_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        self._monitor_thread.start()
        
    def add_plc(self, plc_id, name, ip, rack, slot, port):
        """Add or update a PLC configuration."""
        if plc_id not in self.plcs:
            self.plcs[plc_id] = {
                "id": plc_id,
                "operation_lock": threading.RLock(),
                "generation": 0,
                "client": S7Client(),
                "state": "DISCONNECTED",
                "diagnostics": [],
                "cpu_state": "UNKNOWN",
                "cpu_state_error": None,
                "last_s7_success_time": None,
                "last_error": None,
                "last_reconnect_attempt": 0,
                "last_logged_state": None,
                "last_logged_error": None
            }
        
        self.plcs[plc_id].update({
            "name": name,
            "ip": ip.strip(),
            "rack": int(rack),
            "slot": int(slot),
            "port": int(port)
        })
        return plc_id
        
    def get_plc(self, plc_id):
        return self.plcs.get(plc_id)
        
    def _health_monitor_loop(self):
        """Continuously monitor connection health and handle auto-recovery."""
        while self._running:
            try:
                current_time = time.time()
                for plc_id, plc in list(self.plcs.items()):
                    client = plc.get("client")
                    if not client: continue
                    
                    if plc["state"] == "CONNECTED":
                        with plc["operation_lock"]:
                            if plc["state"] != "CONNECTED":
                                continue
                            generation = plc["generation"]
                            # 1. Transport check
                            if not client.connected or not client.is_connected():
                                plc["state"] = "CONNECTION LOST"
                                plc["cpu_state"] = "UNKNOWN"
                                if plc["last_logged_state"] != "CONNECTION LOST":
                                    self.log_diagnostic(plc_id, "CONNECTION LOST", "FAIL", "Transport socket disconnected")
                                    plc["last_logged_state"] = "CONNECTION LOST"
                                    plc["last_logged_error"] = "Transport socket disconnected"
                                continue

                            # 2. Lightweight health check (query CPU state)
                            try:
                                success, state, diag_msg = client.get_cpu_state()
                            except Exception as e:
                                success = False
                                state = "UNKNOWN"
                                diag_msg = str(e)

                            if not client.connected or not client.is_connected():
                                plc["state"] = "CONNECTION LOST"
                                plc["cpu_state"] = "UNKNOWN"
                                if plc["last_logged_state"] != "CONNECTION LOST":
                                    self.log_diagnostic(plc_id, "CONNECTION LOST", "FAIL", "Transport connection lost during health check")
                                    plc["last_logged_state"] = "CONNECTION LOST"
                                    plc["last_logged_error"] = "Transport connection lost"
                                continue

                            if generation != plc["generation"]:
                                continue
                            # If transport is intact:
                            if success:
                                plc["last_s7_success_time"] = datetime.datetime.now().strftime("%H:%M:%S")
                                if plc["cpu_state"] != state:
                                    plc["cpu_state"] = state
                                    plc["cpu_state_error"] = None
                                    self.log_diagnostic(plc_id, "CPU STATE", "PASS" if "RUN" in state or "STOP" in state else "INFO", state)
                                plc["last_logged_state"] = "CONNECTED"
                                plc["last_logged_error"] = None
                            else:
                                # CPU state query failed but socket is alive
                                plc["cpu_state"] = "UNKNOWN â€” CPU state unavailable"
                                plc["cpu_state_error"] = state

                    elif plc["state"] in ["CONNECTION LOST", "CONNECTION FAILED"]:
                        # Auto-recovery: throttle reconnects to once every 2 seconds
                        if current_time - plc.get("last_reconnect_attempt", 0) > 2.0:
                            plc["last_reconnect_attempt"] = current_time
                            
                            if plc["last_logged_state"] != "RECONNECTING":
                                self.log_diagnostic(plc_id, "RECONNECTING", "INFO", f"{plc['ip']}:{plc['port']}")
                                plc["last_logged_state"] = "RECONNECTING"
                                
                            generation = plc["generation"]
                            # Lightweight TCP check first (0.25s timeout)
                            tcp_ok, tcp_err = client.test_tcp_connection(plc["ip"], plc["port"], timeout=0.250)
                            
                            with plc["operation_lock"]:
                                if generation != plc["generation"] or plc["state"] not in ("CONNECTION LOST", "CONNECTION FAILED"):
                                    continue
                                if tcp_ok:
                                    success, msg, latency = client.connect(plc["ip"], plc["rack"], plc["slot"], plc["port"])
                                    if success:
                                        plc["state"] = "CONNECTED"
                                        plc["last_s7_success_time"] = datetime.datetime.now().strftime("%H:%M:%S")
                                        
                                        try:
                                            state_success, cpu_state, diag_msg = client.get_cpu_state()
                                        except Exception:
                                            state_success = True
                                            cpu_state = "UNKNOWN â€” CPU state unavailable"

                                        plc["cpu_state"] = cpu_state
                                        plc["cpu_state_error"] = None if state_success else cpu_state
                                        self.log_diagnostic(plc_id, "S7 RECONNECTED", "PASS", f"Latency {latency}ms | CPU: {cpu_state}")
                                        plc["last_logged_state"] = "CONNECTED"
                                        plc["last_logged_error"] = None
                                    else:
                                        plc["last_error"] = msg
                                        if plc["last_logged_error"] != msg:
                                            self.log_diagnostic(plc_id, "RECONNECT FAIL", "FAIL", msg)
                                            plc["last_logged_error"] = msg
                                else:
                                    if plc["last_logged_error"] != tcp_err:
                                        self.log_diagnostic(plc_id, "TCP UNREACHABLE", "FAIL", tcp_err)
                                        plc["last_logged_error"] = tcp_err

                # Check tag polling schedule (every 500ms)
                if current_time - self.last_tag_poll >= 0.5:
                    self.tag_manager.poll_tags()
                    self.last_tag_poll = time.time()
                    
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)
                
            time.sleep(0.150)
            
    def log_diagnostic(self, plc_id, operation, status, details=""):
        """Log a diagnostic event for a specific PLC."""
        plc = self.get_plc(plc_id)
        if not plc: return
        
        timestamp = time.strftime("%H:%M:%S")
        log_entry = {
            "time": timestamp,
            "operation": operation,
            "status": status,
            "details": details
        }
        
        plc["diagnostics"].append(log_entry)
        if len(plc["diagnostics"]) > 50:
            plc["diagnostics"].pop(0)
            
    def ping(self, plc_id):
        """Ping the configured IP."""
        plc = self.get_plc(plc_id)
        if not plc: return False, "PLC not found", 0
        
        ip = plc["ip"]
        client = plc["client"]
        
        success, msg, latency = client.ping(ip)
        status_str = "PASS" if success else "FAIL"
        
        details = f"{latency}ms" if success else msg
        self.log_diagnostic(plc_id, "PING", status_str, details)
        
        return success, msg, latency
        
    def test_s7_communication(self, plc_id):
        """Perform temporary connection, read CPU state, and disconnect."""
        plc = self.get_plc(plc_id)
        if not plc: return False, "PLC not found", 0, "UNKNOWN", "PLC not found"
        
        client = plc["client"]
        
        if client.is_connected():
            success, state, diag_msg = client.get_cpu_state()
            if success:
                self.log_diagnostic(plc_id, "S7 COMM TEST", "PASS", f"Active connection verified (CPU: {state})")
                return True, "S7 Communication Successful (using active connection)", 0, state, None
                
        test_client = S7Client()
        ip = plc["ip"]
        rack = plc["rack"]
        slot = plc["slot"]
        port = plc["port"]
        
        success, msg, latency = test_client.connect(ip, rack, slot, port)
        if not success:
            self.log_diagnostic(plc_id, "S7 TEST FAIL", "FAIL", msg)
            return False, msg, latency, "UNKNOWN", msg
            
        self.log_diagnostic(plc_id, "S7 TEST PASS", "PASS", f"{latency}ms")
        
        state_success, state_msg, diag_msg = test_client.get_cpu_state()
        if state_success and ("RUN" in state_msg or "STOP" in state_msg):
            self.log_diagnostic(plc_id, "CPU STATE", "PASS", state_msg)
        else:
            self.log_diagnostic(plc_id, "CPU STATE", "INFO", state_msg)
            
        test_client.disconnect()
        return True, "S7 Communication Successful", latency, state_msg if state_success else "UNKNOWN â€” CPU state unavailable", None
        
    def connect(self, plc_id):
        plc = self.get_plc(plc_id)
        if not plc:
            return False, "PLC not found"
        plc["generation"] += 1
        with plc["operation_lock"]:
            return self._connect_locked(plc_id)

    def _connect_locked(self, plc_id):
        """Establish persistent connection."""
        plc = self.get_plc(plc_id)
        if not plc: return False, "PLC not found"
        
        plc["state"] = "CONNECTING"
        client = plc["client"]
        
        success, msg, latency = client.connect(plc["ip"], plc["rack"], plc["slot"], plc["port"])
        
        if success:
            state_success, cpu_state, diag_msg = client.get_cpu_state()
            plc["state"] = "CONNECTED"
            plc["last_s7_success_time"] = datetime.datetime.now().strftime("%H:%M:%S")
            plc["cpu_state"] = cpu_state if state_success else "UNKNOWN â€” CPU state unavailable"
            plc["cpu_state_error"] = None if state_success else cpu_state
            
            self.log_diagnostic(plc_id, "CONNECT", "PASS", f"Connected in {latency}ms (CPU: {plc['cpu_state']})")
            return True, "Connected successfully"
        else:
            plc["state"] = "CONNECTION FAILED"
            self.log_diagnostic(plc_id, "CONNECT", "FAIL", msg)
            return False, msg
            
    def disconnect(self, plc_id):
        plc = self.get_plc(plc_id)
        if not plc:
            return False, "PLC not found"
        plc["generation"] += 1
        with plc["operation_lock"]:
            return self._disconnect_locked(plc_id)

    def _disconnect_locked(self, plc_id):
        """Disconnect persistent connection."""
        plc = self.get_plc(plc_id)
        if not plc: return False, "PLC not found"
        
        self.tag_manager.mark_stale("PLC disconnected")
        plc["state"] = "DISCONNECTING"
        client = plc["client"]
        
        client.disconnect()
        plc["state"] = "DISCONNECTED"
        plc["cpu_state"] = "UNKNOWN"
        plc["cpu_state_error"] = None
        plc["last_s7_success_time"] = None
        plc["last_reconnect_attempt"] = 0
        plc["last_logged_state"] = "DISCONNECTED"
        
        self.log_diagnostic(plc_id, "DISCONNECT", "PASS", "Manual disconnect")
        return True, "Disconnected"
        
    def reconnect(self, plc_id):
        """Disconnect and reconnect."""
        self.disconnect(plc_id)
        time.sleep(0.3)
        return self.connect(plc_id)
        
    def get_status(self, plc_id):
        """Get full status and diagnostics for UI."""
        plc = self.get_plc(plc_id)
        if not plc: return None
        
        return {
            "id": plc["id"],
            "name": plc["name"],
            "ip": plc["ip"],
            "rack": plc["rack"],
            "slot": plc["slot"],
            "port": plc["port"],
            "state": plc["state"],
            "cpu_state": plc["cpu_state"],
            "cpu_state_error": plc.get("cpu_state_error"),
            "last_s7_success_time": plc.get("last_s7_success_time"),
            "last_error": plc.get("last_error"),
            "diagnostics": list(plc["diagnostics"])
        }
