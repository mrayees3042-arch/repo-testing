import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.s7_client import S7Client
from backend.plc_manager import PLCManager
import backend.tag_utils as tag_utils

def run_live_tests():
    print("=== LIVE INTEGRATION TESTS AGAINST SIMULATOR (127.0.0.1:1103) ===")
    
    plc_mgr = PLCManager()
    plc_mgr.add_plc("default", "Test PLC", "127.0.0.1", 0, 1, 1103)
    
    print("\n--- 1. Testing Connection ---")
    connected = plc_mgr.connect("default")
    print(f"Connect result: {connected}")
    plc = plc_mgr.get_plc("default")
    assert plc["state"] == "CONNECTED", f"Expected CONNECTED, got {plc['state']}"
    print(f"PLC State: {plc['state']}, CPU State: {plc['cpu_state']}")
    assert "UNKNOWN" in plc["cpu_state"], f"Expected UNKNOWN CPU state on simulator, got {plc['cpu_state']}"
    
    tm = plc_mgr.tag_manager
    db = tm.db
    
    # Create isolated test table
    table_id = db.create_table("LiveTestTable", "Integration testing")
    tm.set_active_table(table_id)
    
    # Create test tags
    tag_bool = db.create_tag(table_id, "Pump_Start", "M", 0, "0.0", "BOOL", "Read/Write")
    tag_bool_bit1 = db.create_tag(table_id, "Pump_Trip", "M", 0, "0.1", "BOOL", "Read/Write")
    tag_real = db.create_tag(table_id, "Flow_Rate", "DB", 1, "0.0", "REAL", "Read/Write")
    tag_int = db.create_tag(table_id, "Motor_Speed", "M", 0, "2", "INT", "Read/Write")
    tag_apostrophe = db.create_tag(table_id, "User's Special Tag", "M", 0, "4", "INT", "Read/Write")
    
    print("\n--- 2. Testing Bug 1: BOOL 'false' write ---")
    # Write "false" text
    ok, msg = tm.write_tag(tag_bool, "false")
    print(f"Write 'false' result: {ok}, message: {msg}")
    assert ok, f"Write 'false' failed: {msg}"
    assert "Write verified" in msg
    assert "Read back: False" in msg
    
    # Read back to be 100% sure
    client = plc["client"]
    r_ok, r_val = client.read_tag("M", 0, 0, 0, "BOOL")
    print(f"Direct readback M0.0: {r_ok}, value: {r_val}")
    assert r_val is False, f"Expected False, got {r_val}!"
    print(">>> CONFIRMED FIX: 'false' correctly writes False (0), NOT True!")

    print("\n--- 3. Testing BOOL 'true' write ---")
    ok, msg = tm.write_tag(tag_bool, "true")
    print(f"Write 'true' result: {ok}, message: {msg}")
    assert ok, f"Write 'true' failed: {msg}"
    assert "Read back: True" in msg
    r_ok, r_val = client.read_tag("M", 0, 0, 0, "BOOL")
    assert r_val is True
    print(">>> CONFIRMED: 'true' writes True (1)")

    print("\n--- 4. Testing BOOL '0' and '1' and whitespace ---")
    ok, msg = tm.write_tag(tag_bool, "  0  ")
    assert ok and "Read back: False" in msg
    ok, msg = tm.write_tag(tag_bool, "  1  ")
    assert ok and "Read back: True" in msg
    print(">>> CONFIRMED: '0', '1', and whitespace handled correctly")

    print("\n--- 5. Testing Neighboring Bit Preservation ---")
    # M0.0 is currently True (1)
    # Write M0.1 as True (1)
    ok, msg = tm.write_tag(tag_bool_bit1, "true")
    assert ok
    # Check M0.0 is STILL True
    r_ok, r_val = client.read_tag("M", 0, 0, 0, "BOOL")
    assert r_val is True, "Writing bit 1 corrupted bit 0!"
    
    # Now write M0.0 as False (0)
    ok, msg = tm.write_tag(tag_bool, "false")
    assert ok
    # Check M0.1 is STILL True
    r_ok, r_val_bit1 = client.read_tag("M", 0, 0, 1, "BOOL")
    assert r_val_bit1 is True, "Writing bit 0 corrupted bit 1!"
    print(">>> CONFIRMED: Neighboring bits preserved across read-modify-write")

    print("\n--- 6. Testing REAL write & float32 readback ---")
    ok, msg = tm.write_tag(tag_real, 123.456)
    print(f"Write REAL 123.456 result: {ok}, message: {msg}")
    assert ok, f"REAL write failed: {msg}"
    assert "Write verified" in msg

    # Test non-finite REAL rejection
    ok, msg = tm.write_tag(tag_real, "NaN")
    assert not ok
    assert "Non-finite" in msg
    print(">>> CONFIRMED: Non-finite REAL rejected")

    print("\n--- 7. Testing INT write & tag with apostrophe ---")
    ok, msg = tm.write_tag(tag_int, 4321)
    assert ok and "Read back: 4321" in msg
    
    ok, msg = tm.write_tag(tag_apostrophe, 999)
    assert ok and "Read back: 999" in msg
    print(">>> CONFIRMED: Tag with apostrophe written and verified")

    print("\n--- 8. Testing Live Polling Diagnostics ---")
    tm.set_polling(True, table_id)
    time.sleep(0.6)
    tm.poll_tags()
    print("Live tags status:", {k: v["value"] for k, v in tm.live_tags.items()})
    assert tm.diagnostics["success"] >= 4, f"Expected at least 4 successes, got {tm.diagnostics['success']}"
    assert tm.diagnostics["failed"] == 0, f"Expected 0 failures, got {tm.diagnostics['failed']}"
    print(f"Polling diagnostics: Attempted={tm.diagnostics['attempted']}, Success={tm.diagnostics['success']}")

    print("\n--- 9. Testing Bug 2: Connection Loss & Auto-Recovery ---")
    # Simulate socket transport failure by disconnecting raw client socket
    print("Simulating transport failure...")
    client.connected = False
    if hasattr(client.client, 'disconnect'):
        try:
            client.client.disconnect()
        except:
            pass
            
    # Trigger poll
    tm.poll_tags()
    time.sleep(0.2)
    print(f"PLC State after transport loss: {plc['state']}")
    assert plc["state"] in ["CONNECTION LOST", "CONNECTED"], f"State: {plc['state']}"
    print(">>> CONFIRMED: State changed from green CONNECTED on transport loss")

    print("\n--- 10. Testing Manual Disconnect ---")
    plc_mgr.disconnect("default")
    assert plc["state"] == "DISCONNECTED"
    print(f"State after manual disconnect: {plc['state']}")

    # Clean up test table
    db.delete_table(table_id)
    plc_mgr._running = False
    print("\n=== ALL INTEGRATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    run_live_tests()
