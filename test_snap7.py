import sys
import os
import time
sys.path.append(os.path.abspath('C:\\Users\\hp\\.gemini\\antigravity\\scratch\\RepoGen-S7'))

from backend.s7_client import S7Client

def test(ip="192.168.0.1", rack=0, slot=1, port=102):
    client = S7Client()
    print(f"Connecting to {ip}:{port} (Rack {rack}, Slot {slot})...")
    success, msg, latency = client.connect(ip, rack, slot, port)
    print(f"Connect: {success}, {msg} ({latency}ms)")
    if not success:
        return
        
    print("\n--- 1. Testing DB1 REAL (DB1.DBD0) ---")
    success, val = client.read_tag("DB", 1, 0, 0, "REAL")
    print(f"Read DB1.DBD0 Result: {success}, {val}")
    w_ok, w_val = client.write_tag("DB", 1, 0, 0, "REAL", 10.0)
    print(f"Write DB1.DBD0 (10.0) Result: {w_ok}, {w_val}")

    print("\n--- 2. Testing DB1 BOOL (DB1.DBX4.0) ---")
    success, val = client.read_tag("DB", 1, 4, 0, "BOOL")
    print(f"Read DB1.DBX4.0 Result: {success}, {val}")
    w_ok, w_val = client.write_tag("DB", 1, 4, 0, "BOOL", True)
    print(f"Write DB1.DBX4.0 (True) Result: {w_ok}, {w_val}")
    
    print("\n--- 3. Testing M-Memory INT (MW0) ---")
    success, val = client.read_tag("M", 0, 0, 0, "INT")
    print(f"Read MW0 Result: {success}, {val}")
    w_ok, w_val = client.write_tag("M", 0, 0, 0, "INT", 1234)
    print(f"Write MW0 (1234) Result: {w_ok}, {w_val}")
    r_ok, r_val = client.read_tag("M", 0, 0, 0, "INT")
    print(f"Readback MW0 Result: {r_ok}, {r_val}")

    client.disconnect()
    print("\nDisconnected.")

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 102
    rack = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    slot = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    test(ip, rack, slot, port)

