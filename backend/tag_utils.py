import snap7.util
import snap7.type
import struct
import math
import re

def get_data_type_size(data_type):
    """Returns the size in bytes for a given S7 data type."""
    data_type = data_type.upper()
    if data_type in ["BOOL", "BYTE", "SINT", "USINT"]:
        return 1
    elif data_type in ["INT", "UINT", "WORD"]:
        return 2
    elif data_type in ["DINT", "UDINT", "DWORD", "REAL"]:
        return 4
    else:
        raise ValueError(f"Unsupported data type: {data_type}")

def normalize_bool(value):
    """
    Explicitly normalizes boolean inputs:
    - Accepts booleans True/False
    - Accepts 1/0 integers and floats
    - Accepts case-insensitive strings 'true', 'false', '1', '0' with surrounding whitespace
    - Rejects empty strings and invalid inputs with a clear ValueError
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        elif value == 0:
            return False
        else:
            raise ValueError(f"Invalid BOOL numeric value: {value}. Expected 1 or 0.")
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1"):
            return True
        elif v in ("false", "0"):
            return False
        elif not v:
            raise ValueError("BOOL value cannot be empty.")
        else:
            raise ValueError(f"Invalid BOOL value: '{value}'. Expected 'true', 'false', '1', or '0'.")
    raise ValueError(f"Unsupported BOOL type: {type(value).__name__}")

def parse_address(address_str, data_type, area=None, db_number=None):
    """
    Parses an address string into (byte_offset, bit_offset).
    Validates conflicting prefixes against the selected memory area and DB number.
    Rejects conflicting prefixes so the application cannot silently access a different location.
    """
    if not address_str or not str(address_str).strip():
        raise ValueError("Address cannot be empty.")
        
    raw_addr = str(address_str).strip().upper()
    dt_upper = data_type.upper()
    area_upper = area.upper() if area else None
    
    # 1. Check for DB prefix (e.g. "DB1.DBD0", "DB2.DBX4.0", "DB10.10.0")
    db_match = re.match(r"^DB(\d+)\.(.+)$", raw_addr)
    if db_match:
        spec_db = int(db_match.group(1))
        remainder = db_match.group(2)
        
        if area_upper and area_upper != "DB":
            raise ValueError(f"Address specifies Data Block 'DB{spec_db}', but selected area is '{area}'.")
        if db_number is not None and int(db_number) != spec_db:
            raise ValueError(f"Address specifies DB{spec_db}, which conflicts with selected DB Number {db_number}.")
            
        raw_addr = remainder

    # 2. Check for memory area prefixes (M, I, Q, DBX, etc.)
    # Check DB sub-prefixes
    if raw_addr.startswith(("DBX", "DBB", "DBW", "DBD")):
        sub = raw_addr[:3]
        if area_upper and area_upper != "DB":
            raise ValueError(f"Address prefix '{sub}' is for Data Blocks, but selected area is '{area}'.")
        # Validate data type matches prefix size
        if sub == "DBX" and dt_upper != "BOOL":
            raise ValueError(f"Address prefix 'DBX' is for BOOL tags, but tag type is {dt_upper}.")
        elif sub == "DBB" and get_data_type_size(dt_upper) != 1:
            raise ValueError(f"Address prefix 'DBB' is for 1-byte tags (BYTE/SINT/USINT), but tag type is {dt_upper}.")
        elif sub == "DBW" and get_data_type_size(dt_upper) != 2:
            raise ValueError(f"Address prefix 'DBW' is for 2-byte tags (INT/UINT/WORD), but tag type is {dt_upper}.")
        elif sub == "DBD" and get_data_type_size(dt_upper) != 4:
            raise ValueError(f"Address prefix 'DBD' is for 4-byte tags (DINT/UDINT/DWORD/REAL), but tag type is {dt_upper}.")
        raw_addr = raw_addr[3:]
        
    elif raw_addr.startswith(("M", "I", "Q", "A", "E")):
        prefix_char = raw_addr[0]
        expected_area = "M" if prefix_char == "M" else ("I" if prefix_char in ("I", "E") else "Q")
        if area_upper and area_upper not in (expected_area, "MK" if expected_area == "M" else ("PE" if expected_area == "I" else "PA")):
            raise ValueError(f"Address prefix '{prefix_char}' is for area '{expected_area}', but selected area is '{area}'.")
            
        # Check size specifier (e.g. MW, MD, MB, IW, QD)
        if len(raw_addr) > 1 and raw_addr[1] in ["B", "W", "D", "X"]:
            size_char = raw_addr[1]
            if size_char == "X" and dt_upper != "BOOL":
                raise ValueError(f"Address prefix '{prefix_char}X' is for BOOL tags, but tag type is {dt_upper}.")
            elif size_char == "B" and get_data_type_size(dt_upper) != 1:
                raise ValueError(f"Address prefix '{prefix_char}B' is for 1-byte tags, but tag type is {dt_upper}.")
            elif size_char == "W" and get_data_type_size(dt_upper) != 2:
                raise ValueError(f"Address prefix '{prefix_char}W' is for 2-byte tags, but tag type is {dt_upper}.")
            elif size_char == "D" and get_data_type_size(dt_upper) != 4:
                raise ValueError(f"Address prefix '{prefix_char}D' is for 4-byte tags, but tag type is {dt_upper}.")
            raw_addr = raw_addr[2:]
        else:
            raw_addr = raw_addr[1:]
            
    # Now parse numeric byte (and optional bit) offset
    if dt_upper == "BOOL":
        if "." not in raw_addr:
            raise ValueError(f"BOOL address must specify a bit offset (e.g. '0.0' or '10.3'). Got: '{address_str}'")
        parts = raw_addr.split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid BOOL address format: '{address_str}'. Expected 'byte.bit' (e.g. '0.0').")
        try:
            byte_offset = int(parts[0])
            bit_offset = int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid non-integer in BOOL address: '{address_str}'")
            
        if byte_offset < 0:
            raise ValueError(f"Byte offset cannot be negative: {byte_offset}")
        if bit_offset < 0 or bit_offset > 7:
            raise ValueError(f"Bit offset must be between 0 and 7. Got {bit_offset}")
        return byte_offset, bit_offset
    else:
        # Non-BOOL type
        if "." in raw_addr:
            parts = raw_addr.split(".")
            if len(parts) == 2 and parts[1] == "0":
                try:
                    byte_offset = int(parts[0])
                except ValueError:
                    raise ValueError(f"Invalid non-integer in address: '{address_str}'")
            else:
                raise ValueError(f"Data type {data_type} cannot have a non-zero bit offset: '{address_str}'")
        else:
            try:
                byte_offset = int(raw_addr)
            except ValueError:
                raise ValueError(f"Invalid non-integer address: '{address_str}'")
                
        if byte_offset < 0:
            raise ValueError(f"Byte offset cannot be negative: {byte_offset}")
        return byte_offset, 0

def resolve_address(area, db_number, address_str, data_type):
    """
    Returns the canonical resolved address string (e.g. 'DB1.DBD0', 'MW10', 'M10.3').
    """
    byte_offset, bit_offset = parse_address(address_str, data_type, area, db_number)
    area = area.upper()
    dt = data_type.upper()
    
    if area == "DB":
        db_num = db_number if db_number is not None else 1
        if dt == "BOOL":
            prefix = "DBX"
            offset_str = f"{byte_offset}.{bit_offset}"
        elif dt in ["BYTE", "SINT", "USINT"]:
            prefix = "DBB"
            offset_str = str(byte_offset)
        elif dt in ["INT", "UINT", "WORD"]:
            prefix = "DBW"
            offset_str = str(byte_offset)
        else: # DINT, UDINT, DWORD, REAL
            prefix = "DBD"
            offset_str = str(byte_offset)
        return f"DB{db_num}.{prefix}{offset_str}"
    else:
        area_code = "M" if area in ("M", "MK") else ("I" if area in ("I", "E", "PE") else "Q")
        if dt == "BOOL":
            return f"{area_code}{byte_offset}.{bit_offset}"
        elif dt in ["BYTE", "SINT", "USINT"]:
            return f"{area_code}B{byte_offset}"
        elif dt in ["INT", "UINT", "WORD"]:
            return f"{area_code}W{byte_offset}"
        else:
            return f"{area_code}D{byte_offset}"

def decode_value(buffer, data_type, bit_offset=0):
    """Decodes a bytearray into a Python value using snap7.util."""
    data_type = data_type.upper()
    
    if data_type == "BOOL":
        return snap7.util.get_bool(buffer, 0, bit_offset)
        
    elif data_type == "BYTE":
        return snap7.util.get_usint(buffer, 0)
    elif data_type == "SINT":
        return snap7.util.get_sint(buffer, 0)
    elif data_type == "USINT":
        return snap7.util.get_usint(buffer, 0)
        
    elif data_type == "INT":
        return snap7.util.get_int(buffer, 0)
    elif data_type == "UINT":
        return snap7.util.get_uint(buffer, 0)
    elif data_type == "WORD":
        return snap7.util.get_word(buffer, 0)
        
    elif data_type == "DINT":
        return snap7.util.get_dint(buffer, 0)
    elif data_type == "UDINT":
        return snap7.util.get_udint(buffer, 0)
    elif data_type == "DWORD":
        return snap7.util.get_dword(buffer, 0)
    elif data_type == "REAL":
        return snap7.util.get_real(buffer, 0)
        
    else:
        raise ValueError(f"Unsupported data type for decoding: {data_type}")

def encode_value(value, data_type, buffer, bit_offset=0):
    """
    Encodes a Python value into an existing bytearray using snap7.util.
    Returns the normalized/cast value used for encoding.
    """
    data_type = data_type.upper()
    
    try:
        if data_type == "BOOL":
            val = normalize_bool(value)
            snap7.util.set_bool(buffer, 0, bit_offset, val)
            return val
            
        elif data_type == "BYTE":
            val = int(value)
            if not (0 <= val <= 255):
                raise ValueError(f"Value {val} out of bounds for BYTE (0 to 255)")
            snap7.util.set_usint(buffer, 0, val)
            return val
            
        elif data_type == "SINT":
            val = int(value)
            if not (-128 <= val <= 127):
                raise ValueError(f"Value {val} out of bounds for SINT (-128 to 127)")
            snap7.util.set_sint(buffer, 0, val)
            return val
            
        elif data_type == "USINT":
            val = int(value)
            if not (0 <= val <= 255):
                raise ValueError(f"Value {val} out of bounds for USINT (0 to 255)")
            snap7.util.set_usint(buffer, 0, val)
            return val
            
        elif data_type == "INT":
            val = int(value)
            if not (-32768 <= val <= 32767):
                raise ValueError(f"Value {val} out of bounds for INT (-32768 to 32767)")
            snap7.util.set_int(buffer, 0, val)
            return val
            
        elif data_type == "UINT":
            val = int(value)
            if not (0 <= val <= 65535):
                raise ValueError(f"Value {val} out of bounds for UINT (0 to 65535)")
            snap7.util.set_uint(buffer, 0, val)
            return val
            
        elif data_type == "WORD":
            val = int(value)
            if not (0 <= val <= 65535):
                raise ValueError(f"Value {val} out of bounds for WORD (0 to 65535)")
            snap7.util.set_word(buffer, 0, val)
            return val
            
        elif data_type == "DINT":
            val = int(value)
            if not (-2147483648 <= val <= 2147483647):
                raise ValueError(f"Value {val} out of bounds for DINT (-2147483648 to 2147483647)")
            snap7.util.set_dint(buffer, 0, val)
            return val
            
        elif data_type == "UDINT":
            val = int(value)
            if not (0 <= val <= 4294967295):
                raise ValueError(f"Value {val} out of bounds for UDINT (0 to 4294967295)")
            snap7.util.set_udint(buffer, 0, val)
            return val
            
        elif data_type == "DWORD":
            val = int(value)
            if not (0 <= val <= 4294967295):
                raise ValueError(f"Value {val} out of bounds for DWORD (0 to 4294967295)")
            snap7.util.set_dword(buffer, 0, val)
            return val
            
        elif data_type == "REAL":
            if isinstance(value, str):
                val = float(value.strip())
            else:
                val = float(value)
            if math.isnan(val) or math.isinf(val):
                raise ValueError("Non-finite REAL values (NaN/Infinity) are not allowed.")
            snap7.util.set_real(buffer, 0, val)
            return val
            
        else:
            raise ValueError(f"Unsupported data type for encoding: {data_type}")
            
    except ValueError as e:
        raise ValueError(f"Cannot cast '{value}' to {data_type}: {str(e)}")
    except struct.error as e:
        raise ValueError(f"Value '{value}' is out of bounds for {data_type}: {str(e)}")
