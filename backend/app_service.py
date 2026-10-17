from backend.plc_manager import PLCManager
import backend.tag_utils as tag_utils
import logging

logger = logging.getLogger(__name__)

class AppService:
    def __init__(self):
        self.manager = PLCManager()
        self.manager.add_plc("default", "Test PLC", "192.168.0.1", 0, 1, 102)
        
    def save_config(self, ip, rack, slot, port):
        """Update the configuration from UI."""
        self.manager.add_plc("default", "Test PLC", ip, rack, slot, port)
        return True
        
    def ping(self, ip, rack, slot, port):
        self.save_config(ip, rack, slot, port)
        success, msg, latency = self.manager.ping("default")
        return {
            "success": success,
            "message": msg,
            "latency": latency
        }
        
    def test_s7_communication(self, ip, rack, slot, port):
        self.save_config(ip, rack, slot, port)
        success, msg, latency, cpu_state, cpu_state_error = self.manager.test_s7_communication("default")
        return {
            "success": success,
            "message": msg,
            "latency": latency,
            "cpu_state": cpu_state,
            "cpu_state_error": cpu_state_error
        }
        
    def connect(self, ip, rack, slot, port):
        self.save_config(ip, rack, slot, port)
        success, msg = self.manager.connect("default")
        return {
            "success": success,
            "message": msg
        }
        
    def disconnect(self):
        success, msg = self.manager.disconnect("default")
        return {
            "success": success,
            "message": msg
        }
        
    def reconnect(self, ip, rack, slot, port):
        self.save_config(ip, rack, slot, port)
        success, msg = self.manager.reconnect("default")
        return {
            "success": success,
            "message": msg
        }
        
    def get_status(self):
        """Poll function for UI to get current state and logs."""
        return self.manager.get_status("default")

    # --- Tag Tables ---
    def get_all_tables(self):
        return self.manager.tag_manager.db.get_all_tables()

    def create_table(self, name, description=""):
        name = name.strip()
        if not name:
            return {"success": False, "message": "Table name cannot be empty."}
        table_id = self.manager.tag_manager.db.create_table(name, description)
        return {"success": True, "id": table_id}

    def update_table(self, table_id, name, description=""):
        name = name.strip()
        if not name:
            return {"success": False, "message": "Table name cannot be empty."}
        self.manager.tag_manager.db.update_table(table_id, name, description)
        return {"success": True}

    def delete_table(self, table_id):
        self.manager.tag_manager.db.delete_table(table_id)
        if self.manager.tag_manager.active_table_id == table_id:
            self.manager.tag_manager.set_active_table(None)
        return {"success": True}

    # --- Tags ---
    def get_tags_for_table(self, table_id):
        return self.manager.tag_manager.db.get_tags_for_table(table_id)

    def resolve_tag_address(self, area, db_number, address, data_type):
        try:
            res = tag_utils.resolve_address(area, db_number, address, data_type)
            return {"success": True, "resolved": res}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def create_tag(self, table_id, name, area, db_number, address, data_type, access_mode, description=""):
        name = str(name).strip()
        if not name:
            return {"success": False, "message": "Tag name is required."}
        try:
            tag_utils.parse_address(address, data_type, area, db_number)
        except Exception as e:
            return {"success": False, "message": str(e)}

        res = self.manager.tag_manager.db.create_tag(table_id, name, area, db_number, address, data_type, access_mode, description)
        if self.manager.tag_manager.active_table_id == table_id:
            self.manager.tag_manager.set_active_table(table_id)
        return {"success": True, "id": res}

    def update_tag(self, tag_id, name, area, db_number, address, data_type, access_mode, description=""):
        name = str(name).strip()
        if not name:
            return {"success": False, "message": "Tag name is required."}
        try:
            tag_utils.parse_address(address, data_type, area, db_number)
        except Exception as e:
            return {"success": False, "message": str(e)}

        self.manager.tag_manager.db.update_tag(tag_id, name, area, db_number, address, data_type, access_mode, description)
        if self.manager.tag_manager.active_table_id is not None:
            self.manager.tag_manager.set_active_table(self.manager.tag_manager.active_table_id)
        return {"success": True}

    def delete_tag(self, tag_id):
        self.manager.tag_manager.db.delete_tag(tag_id)
        if self.manager.tag_manager.active_table_id is not None:
            self.manager.tag_manager.set_active_table(self.manager.tag_manager.active_table_id)
        return {"success": True}

    def get_tag_details_for_write(self, tag_id):
        tag = self.manager.tag_manager.db.get_tag(tag_id)
        if not tag:
            return {"success": False, "message": "Tag not found."}
        t = dict(tag)
        live = self.manager.tag_manager.live_tags.get(tag_id, {})
        plc = self.manager.get_plc("default")
        
        try:
            resolved = tag_utils.resolve_address(t["area"], t.get("db_number"), t["address"], t["data_type"])
        except Exception:
            resolved = t["address"]
            
        return {
            "success": True,
            "tag": t,
            "resolved_address": resolved,
            "current_value": live.get("value"),
            "quality": live.get("quality", "UNKNOWN"),
            "timestamp": live.get("timestamp"),
            "plc_connected": (plc["state"] == "CONNECTED") if plc else False,
            "plc_ip": plc["ip"] if plc else "",
            "plc_port": plc["port"] if plc else 102
        }

    # --- Live Tags / Polling ---
    def set_active_table(self, table_id):
        self.manager.tag_manager.set_active_table(table_id)
        return True

    def set_polling(self, enabled, table_id=None):
        self.manager.tag_manager.set_polling(enabled, table_id)
        return True

    def get_live_tags(self):
        return {
            "tags": self.manager.tag_manager.live_tags,
            "diagnostics": self.manager.tag_manager.diagnostics
        }

    def write_tag(self, tag_id, value):
        success, msg = self.manager.tag_manager.write_tag(tag_id, value)
        return {
            "success": success,
            "message": msg
        }
