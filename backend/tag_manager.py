import time
import math
import struct
from backend.database import Database
import backend.tag_utils as tag_utils

class TagManager:
    def __init__(self, plc_manager):
        self.db = Database()
        self.plc_manager = plc_manager
        
        # In-memory dict for live tag values
        # tag_id -> {"value": val, "quality": "GOOD"/"BAD"/"STALE", "timestamp": str, "error": str, "latency": int}
        self.live_tags = {}
        self.active_table_id = None
        self.polling_enabled = False
        self.active_group_id = None
        self.diagnostics = {
            "last_cycle": "Never",
            "attempted": 0,
            "success": 0,
            "failed": 0,
            "last_error": "None"
        }

    def set_active_table(self, table_id):
        self.active_table_id = table_id
        # Table navigation must not discard the live group's last known readings.
        grouped = {t["id"] for t in self.db.get_group_tags(self.active_group_id)} if self.active_group_id is not None else set()
        retained = {key: value for key, value in self.live_tags.items() if key in grouped}
        self.live_tags = retained
        
        if table_id:
            tags = self.db.get_tags_for_table(table_id)
            for t in tags:
                self.live_tags.setdefault(t["id"], {
                    "value": None,
                    "quality": "UNKNOWN",
                    "timestamp": None,
                    "error": None,
                    "latency": 0
                })

    def mark_stale(self, reason):
        for tag_id, cached in list(self.live_tags.items()):
            if cached.get("value") is not None:
                self.live_tags[tag_id] = {**cached, "quality": "STALE", "error": reason}

    def set_polling(self, enabled, table_id=None):
        self.polling_enabled = enabled
        if not enabled:
            self.mark_stale("Monitoring stopped")
        if table_id is not None:
            self.set_active_table(table_id)

    def poll_tags(self):
        """Called by plc_manager's background thread to read all active tags."""
        if not self.polling_enabled and self.active_group_id is None:
            return
            
        tags_by_id = {}
        if self.polling_enabled and self.active_table_id:
            tags_by_id.update((t["id"], t) for t in self.db.get_tags_for_table(self.active_table_id))
        if self.active_group_id is not None:
            tags_by_id.update((t["id"], t) for t in self.db.get_group_tags(self.active_group_id))
        tags = list(tags_by_id.values())
        attempted = len(tags)
        
        if attempted == 0:
            self.diagnostics["last_cycle"] = time.strftime("%H:%M:%S")
            self.diagnostics["attempted"] = 0
            self.diagnostics["success"] = 0
            self.diagnostics["failed"] = 0
            self.diagnostics["last_error"] = "No tags defined in active table"
            return
        
        plc = self.plc_manager.get_plc("default")
        if not plc or plc["state"] != "CONNECTED":
            for t in tags:
                self._update_live_tag(t["id"], None, "BAD", "PLC not connected", 0)
            self.diagnostics["last_cycle"] = time.strftime("%H:%M:%S")
            self.diagnostics["attempted"] = attempted
            self.diagnostics["success"] = 0
            self.diagnostics["failed"] = attempted
            self.diagnostics["last_error"] = "PLC not connected"
            return

        client = plc.get("client")
        if not client or not getattr(client, 'connected', False) or (hasattr(client, 'is_connected') and not client.is_connected()):
            for t in tags:
                self._update_live_tag(t["id"], None, "BAD", "S7 Client disconnected", 0)
            self.diagnostics["last_cycle"] = time.strftime("%H:%M:%S")
            self.diagnostics["attempted"] = attempted
            self.diagnostics["success"] = 0
            self.diagnostics["failed"] = attempted
            self.diagnostics["last_error"] = "S7 Client disconnected"
            return
            
        success_count = 0
        failed_count = 0
        last_error = "None"
            
        for t in tags:
            try:
                byte_offset, bit_offset = tag_utils.parse_address(t["address"], t["data_type"], t.get("area"), t.get("db_number"))
                
                start_time = time.time()
                success, val = client.read_tag(t["area"], t["db_number"] or 0, byte_offset, bit_offset, t["data_type"])
                latency = int((time.time() - start_time) * 1000)
                
                if success:
                    self._update_live_tag(t["id"], val, "GOOD", None, latency)
                    success_count += 1
                else:
                    self._update_live_tag(t["id"], None, "BAD", str(val), latency)
                    failed_count += 1
                    last_error = str(val)
                    
            except Exception as e:
                self._update_live_tag(t["id"], None, "BAD", str(e), 0)
                failed_count += 1
                last_error = str(e)
                
        self.diagnostics["last_cycle"] = time.strftime("%H:%M:%S")
        self.diagnostics["attempted"] = attempted
        self.diagnostics["success"] = success_count
        self.diagnostics["failed"] = failed_count
        self.diagnostics["last_error"] = last_error

    def _update_live_tag(self, tag_id, value, quality, error, latency):
        timestamp = time.strftime("%H:%M:%S")
        existing = self.live_tags.get(tag_id, {})
        # If read failed but we have a prior good value, preserve it marked stale with original timestamp
        if quality == "BAD" and existing.get("value") is not None and existing.get("quality") in ("GOOD", "STALE"):
            self.live_tags[tag_id] = {
                "value": existing["value"],
                "quality": "STALE",
                "timestamp": existing.get("timestamp", timestamp),
                "error": error,
                "latency": latency
            }
        else:
            self.live_tags[tag_id] = {
                "value": value,
                "quality": quality,
                "timestamp": timestamp if quality == "GOOD" else None,
                "sampled_at": time.time() if quality == "GOOD" else None,
                "error": error,
                "latency": latency
            }

    def write_tag(self, tag_id, value):
        tag = None
        if self.active_table_id:
            tags = self.db.get_tags_for_table(self.active_table_id)
            tag = next((t for t in tags if t["id"] == tag_id), None)
            
        if not tag:
            tag = self.db.get_tag(tag_id)
            
        if not tag:
            return False, "Tag not found."
            
        if tag["access_mode"] == "Read Only":
            return False, "Tag is configured as Read Only."
            
        plc = self.plc_manager.get_plc("default")
        if not plc or plc["state"] != "CONNECTED":
            return False, "Connect to a PLC before writing."
            
        client = plc.get("client")
        if not client or not getattr(client, "connected", False) or (hasattr(client, 'is_connected') and not client.is_connected()):
            return False, "Connect to a PLC before writing."
        
        # Validate and normalize input value before attempting any write
        data_type = tag["data_type"].upper()
        norm_value = value
        
        try:
            if data_type == "BOOL":
                norm_value = tag_utils.normalize_bool(value)
            elif data_type == "REAL":
                f_val = float(str(value).strip())
                if math.isnan(f_val) or math.isinf(f_val):
                    return False, "Non-finite REAL values (NaN/Infinity) are not permitted."
                norm_value = struct.unpack(">f", struct.pack(">f", f_val))[0]
            elif data_type in ["BYTE", "USINT"]:
                i_val = int(value)
                if not (0 <= i_val <= 255):
                    return False, f"Value {i_val} out of bounds for {data_type} (0 to 255)."
                norm_value = i_val
            elif data_type == "SINT":
                i_val = int(value)
                if not (-128 <= i_val <= 127):
                    return False, f"Value {i_val} out of bounds for SINT (-128 to 127)."
                norm_value = i_val
            elif data_type == "INT":
                i_val = int(value)
                if not (-32768 <= i_val <= 32767):
                    return False, f"Value {i_val} out of bounds for INT (-32768 to 32767)."
                norm_value = i_val
            elif data_type in ["UINT", "WORD"]:
                i_val = int(value)
                if not (0 <= i_val <= 65535):
                    return False, f"Value {i_val} out of bounds for {data_type} (0 to 65535)."
                norm_value = i_val
            elif data_type == "DINT":
                i_val = int(value)
                if not (-2147483648 <= i_val <= 2147483647):
                    return False, f"Value {i_val} out of bounds for DINT (-2147483648 to 2147483647)."
                norm_value = i_val
            elif data_type in ["UDINT", "DWORD"]:
                i_val = int(value)
                if not (0 <= i_val <= 4294967295):
                    return False, f"Value {i_val} out of bounds for {data_type} (0 to 4294967295)."
                norm_value = i_val
        except (ValueError, TypeError, OverflowError, struct.error) as e:
            return False, f"Invalid value for {data_type}: {str(e)}"
            
        try:
            byte_offset, bit_offset = tag_utils.parse_address(tag["address"], tag["data_type"], tag.get("area"), tag.get("db_number"))
            
            # Perform the write
            success, msg = client.write_tag(tag["area"], tag["db_number"] or 0, byte_offset, bit_offset, tag["data_type"], norm_value)
            
            if not success:
                return False, f"Write failed: {msg}"
                
            # Verification step: read back from PLC to confirm memory update
            success_read, val = client.read_tag(tag["area"], tag["db_number"] or 0, byte_offset, bit_offset, tag["data_type"])
            if not success_read:
                # Explicitly state write was sent, but verification failed
                return False, f"Write sent; verification failed (readback error: {val})"
                
            if data_type == "REAL":
                read_f = float(val)
                req_f = float(norm_value)
                if not math.isfinite(read_f) or read_f != req_f:
                    return False, f"Write sent; verification failed. Read back: {read_f} (expected {req_f})"
            elif data_type == "BOOL":
                val_bool = tag_utils.normalize_bool(val)
                req_bool = norm_value # already a bool
                if val_bool != req_bool:
                    return False, f"Write sent; verification failed. Read back: {val_bool} (expected {req_bool})"
            else:
                if int(val) != int(norm_value):
                    return False, f"Write sent; verification failed. Read back: {val} (expected {norm_value})"
                        
            return True, f"Write verified (Read back: {val})"
            
        except Exception as e:
            return False, f"Write error: {str(e)}"
