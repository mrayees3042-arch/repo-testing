import sys
import os
import unittest
from unittest.mock import MagicMock
import math

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backend.tag_utils as tag_utils
from backend.s7_client import S7Client, Snap7Exception
from backend.tag_manager import TagManager
from backend.plc_manager import PLCManager
from backend.database import Database

class TestRepoGenVerification(unittest.TestCase):
    def test_01_snap7_exception_class(self):
        """Verify Snap7Exception is properly imported and evaluated without AttributeError."""
        import snap7
        self.assertFalse(hasattr(snap7, 'exceptions'), "snap7 should not have exceptions attribute in 3.2.1")
        try:
            raise Snap7Exception("Test error")
        except Snap7Exception as e:
            self.assertEqual(str(e), "Test error")

    def test_02_bool_normalization(self):
        """Verify BOOL normalization handles all documented forms and rejects invalid inputs."""
        # True values
        self.assertTrue(tag_utils.normalize_bool(True))
        self.assertTrue(tag_utils.normalize_bool(1))
        self.assertTrue(tag_utils.normalize_bool("true"))
        self.assertTrue(tag_utils.normalize_bool("TRUE"))
        self.assertTrue(tag_utils.normalize_bool("True"))
        self.assertTrue(tag_utils.normalize_bool("  true  "))
        self.assertTrue(tag_utils.normalize_bool("1"))
        self.assertTrue(tag_utils.normalize_bool(" 1 "))

        # False values
        self.assertFalse(tag_utils.normalize_bool(False))
        self.assertFalse(tag_utils.normalize_bool(0))
        self.assertFalse(tag_utils.normalize_bool("false"))
        self.assertFalse(tag_utils.normalize_bool("FALSE"))
        self.assertFalse(tag_utils.normalize_bool("False"))
        self.assertFalse(tag_utils.normalize_bool("  false  "))
        self.assertFalse(tag_utils.normalize_bool("0"))
        self.assertFalse(tag_utils.normalize_bool(" 0 "))

        # Rejections
        with self.assertRaises(ValueError):
            tag_utils.normalize_bool("")
        with self.assertRaises(ValueError):
            tag_utils.normalize_bool("   ")
        with self.assertRaises(ValueError):
            tag_utils.normalize_bool("invalid")
        with self.assertRaises(ValueError):
            tag_utils.normalize_bool("2")
        with self.assertRaises(ValueError):
            tag_utils.normalize_bool(-1)

    def test_03_neighboring_bit_preservation(self):
        """Verify encoding a single BOOL bit preserves all neighboring bits in the byte."""
        # Start with a byte with pattern 0b10101010 (0xAA)
        buf = bytearray([0xAA])
        
        # Set bit 0 to 1 -> 0b10101011 (0xAB)
        tag_utils.encode_value(True, "BOOL", buf, bit_offset=0)
        self.assertEqual(buf[0], 0xAB)
        
        # Set bit 1 to 0 -> 0b10101001 (0xA9)
        tag_utils.encode_value(False, "BOOL", buf, bit_offset=1)
        self.assertEqual(buf[0], 0xA9)
        
        # Verify bits 2 through 7 remained unchanged
        self.assertEqual(buf[0] & 0xFC, 0xA8)

    def test_04_address_parsing_and_conflicts(self):
        """Verify address parsing accepts valid formats and rejects conflicting prefixes."""
        # Valid addresses
        b, bi = tag_utils.parse_address("0.0", "BOOL", area="M")
        self.assertEqual((b, bi), (0, 0))
        b, bi = tag_utils.parse_address("M10.5", "BOOL", area="M")
        self.assertEqual((b, bi), (10, 5))
        b, bi = tag_utils.parse_address("DB1.DBD4", "REAL", area="DB", db_number=1)
        self.assertEqual((b, bi), (4, 0))
        b, bi = tag_utils.parse_address("MW20", "INT", area="M")
        self.assertEqual((b, bi), (20, 0))

        # Conflicting DB Number
        with self.assertRaises(ValueError) as ctx:
            tag_utils.parse_address("DB2.DBD4", "REAL", area="DB", db_number=1)
        self.assertIn("conflicts with selected DB Number 1", str(ctx.exception))

        # Conflicting Area Prefix (typed M prefix while DB area is selected)
        with self.assertRaises(ValueError) as ctx:
            tag_utils.parse_address("M10.0", "BOOL", area="DB", db_number=1)
        self.assertIn("selected area is 'DB'", str(ctx.exception))

        # Conflicting Area Prefix (typed DB prefix while M area is selected)
        with self.assertRaises(ValueError) as ctx:
            tag_utils.parse_address("DB1.DBD0", "REAL", area="M")
        self.assertIn("selected area is 'M'", str(ctx.exception))

        # Invalid bit offsets
        with self.assertRaises(ValueError):
            tag_utils.parse_address("0.8", "BOOL", area="M") # bit > 7
        with self.assertRaises(ValueError):
            tag_utils.parse_address("-1.0", "BOOL", area="M") # negative offset

        # Non-BOOL with non-zero bit offset
        with self.assertRaises(ValueError):
            tag_utils.parse_address("10.3", "INT", area="M")

    def test_05_numeric_bounds_and_finite_checks(self):
        """Verify numeric bounds validation and finite checks for REAL."""
        buf = bytearray(4)
        
        # REAL finite checks
        with self.assertRaises(ValueError):
            tag_utils.encode_value(float('nan'), "REAL", buf)
        with self.assertRaises(ValueError):
            tag_utils.encode_value(float('inf'), "REAL", buf)
        with self.assertRaises(ValueError):
            tag_utils.encode_value("-inf", "REAL", buf)
            
        # REAL valid float
        val = tag_utils.encode_value(123.456, "REAL", buf)
        self.assertAlmostEqual(val, 123.456, places=3)
        decoded = tag_utils.decode_value(buf, "REAL")
        self.assertTrue(math.isclose(decoded, 123.456, rel_tol=1e-4, abs_tol=1e-3))

        # Integer bounds
        buf1 = bytearray(1)
        with self.assertRaises(ValueError):
            tag_utils.encode_value(256, "BYTE", buf1)
        with self.assertRaises(ValueError):
            tag_utils.encode_value(-1, "BYTE", buf1)
            
        buf2 = bytearray(2)
        with self.assertRaises(ValueError):
            tag_utils.encode_value(32768, "INT", buf2)
        with self.assertRaises(ValueError):
            tag_utils.encode_value(-32769, "INT", buf2)

    def test_06_truthful_verification_reporting(self):
        """Verify that write verification failure clearly states write was sent."""
        plc_mgr = PLCManager()
        plc_mgr.plcs["default"] = {
            "id": "default",
            "state": "CONNECTED",
            "client": MagicMock()
        }
        client = plc_mgr.plcs["default"]["client"]
        client.connected = True
        client.is_connected.return_value = True
        
        # Simulate: write succeeds, but readback returns a different value
        client.write_tag.return_value = (True, "Success")
        client.read_tag.return_value = (True, True) # returns True when False was written
        
        tm = plc_mgr.tag_manager
        tm.db.get_tag = MagicMock(return_value={
            "id": 1,
            "name": "TestBOOL",
            "area": "M",
            "db_number": 0,
            "address": "0.0",
            "data_type": "BOOL",
            "access_mode": "Read/Write"
        })
        
        success, msg = tm.write_tag(1, "false")
        self.assertFalse(success)
        self.assertIn("Write sent; verification failed", msg)
        self.assertIn("Read back: True", msg)
        
        # Test readback error
        client.read_tag.return_value = (False, "Timeout on readback")
        success, msg = tm.write_tag(1, "false")
        self.assertFalse(success)
        self.assertIn("Write sent; verification failed", msg)
        
        plc_mgr._running = False

    def test_07_cpu_state_unsupported_protocol_error(self):
        """Verify CPU state protocol error 0x81/0x84 does not mark connection disconnected."""
        client = S7Client()
        client.connected = True
        client.client = MagicMock()
        client.client.get_connected.return_value = True
        
        # Simulate PLCSIM protocol error
        client.client.get_cpu_state.side_effect = Exception("S7 protocol error (class=0x84, code=0x04): The function cannot be performed")
        
        success, state, diag_msg = client.get_cpu_state()
        self.assertTrue(success, "CPU state query should return success=True for decoupled handling")
        self.assertEqual(state, "UNKNOWN — CPU state unavailable")
        self.assertTrue(client.connected, "Client should remain marked connected after unsupported CPU query")

    def test_08_transport_failure_clears_connection(self):
        """Verify transport failure marks connection disconnected immediately."""
        client = S7Client()
        client.connected = True
        client.client = MagicMock()
        client.client.get_connected.return_value = False
        
        # Simulate transport failure during read
        client.client.read_area.side_effect = Exception("S7ConnectionError: Not connected")
        
        success, val = client.read_tag("M", 0, 0, 0, "BOOL")
        self.assertFalse(success)
        self.assertFalse(client.connected, "Client connected flag must be cleared on transport failure")

    def test_09_manual_disconnect_cancels_reconnect(self):
        """Verify manual disconnect sets state to DISCONNECTED and does not auto-recover."""
        plc_mgr = PLCManager()
        plc_mgr.add_plc("default", "Test PLC", "192.168.0.1", 0, 1, 102)
        plc = plc_mgr.get_plc("default")
        plc["state"] = "CONNECTED"
        plc["client"].connected = True
        
        plc_mgr.disconnect("default")
        self.assertEqual(plc["state"], "DISCONNECTED")
        self.assertFalse(plc["client"].connected)
        
        plc_mgr._running = False

if __name__ == '__main__':
    unittest.main()
