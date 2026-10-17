# Project Status: RepoGen S7 Communication Tool

## Project overview
- **Application Purpose**: Desktop GUI tool for Siemens S7 PLC communication, diagnostics, tag monitoring, and read/write operations (supporting S7-300, S7-400, S7-1200, S7-1500, and PLCSIM/NetToPLCSim).
- **Architecture**: 
  - Backend: Python with `python-snap7` (Snap7 C client wrapper), SQLite database (`repogen.db`) for tag tables and tag metadata, persistent background health & polling scheduler thread.
  - Frontend: Single-page desktop GUI served via `pywebview` with HTML5/CSS/JavaScript and bidirectional JS-Python bridge (`AppService`).
- **Source Directory**: `C:\Users\hp\.gemini\antigravity\scratch\RepoGen-S7`
- **Build Configuration**: PyInstaller single-file windowed build script (`build.py` / `RepoGen-S7-Setup.spec`).
- **Official Deliverables**:
  - Installer: `dist/RepoGen-S7-Setup.exe`
  - Portable Package: `dist/RepoGen-Portable.zip`
- **Snap7 Package & Version**: `python-snap7 3.2.1` installed in local virtual environment (`venv/Lib/site-packages/snap7`). Exception hierarchy located in `snap7.error` (`S7Error`, `S7ProtocolError`, etc.).

---

## Confirmed working
- **Packaged Executable Startup**: Application starts and runs on standalone Windows PCs without requiring Python installed (pywebview and pythonnet bundled).
- **PLC S7 Connection**: TCP connection (port 102) and S7 handshake succeed against target PLC/PLCSIM (`CONNECTED` state, 1ms latency).
- **Auto-Reconnection**: Reconnect loop handles disconnected state gracefully without application crash.
- **Monitoring Scheduler Activation**: Verified in build `DIAG_READ_CPU_006` screenshot: scheduler runs (`Last Poll: 21:50:16 | Attempted: 1 | Failed: 1`), confirming polling activation and tag dispatch.
- **Tag Database Persistence**: Tag tables (e.g. `aa`) and tags (e.g. `a` at `DB1.DBD0`, `MW0`) are saved, loaded, and edited in SQLite database.
- **Exception Class Resolution**: `AttributeError: module 'snap7' has no attribute 'exceptions'` is resolved by mapping `snap7.error.S7Error` as `Snap7Exception`.

---

## Current bugs

### Bug 1: S7 Protocol Error on DB Read & Write
- **Exact Observed Behavior**: 
  - In live monitoring: tag `a` at `DB1.DBD0` (REAL) fails with Quality `BAD`, Value `---`, `Failed: 1`.
  - In write dialog: attempting to write `10.0` to tag `a` (`DB1.DBD0`) produces an alert: `Write Failed: S7 Error: S7 protocol error (class=0x81, code=0x04): This service is not implemented on the module or a frame error was reported`.
- **Error Message**: `S7 protocol error (class=0x81, code=0x04): This service is not implemented on the module or a frame error was reported`
- **Reproduction Steps**:
  1. Launch `RepoGen-S7-Setup.exe` (build `v1.0.6 [DIAG_READ_CPU_006]`).
  2. Connect to PLCSIM (`192.168.0.1`, Rack 0, Slot 1).
  3. Open `Tag Tables` tab, select table `aa`.
  4. With tag `a` configured as DB 1, Address `DB1.DBD0` (or `0.0`), Data Type `REAL`:
     - Click `Start Monitoring` -> Poll counter increments, read fails with error class `0x81`, code `0x04`.
     - Click `Write` -> Enter `10.0` -> Write fails with error class `0x81`, code `0x04`.
- **Diagnostic Findings**:
  - *Operation Attempted*: Snap7 executed `client.write_area(Area.DB, db_number=1, start=0, data=b'\x41\x20\x00\x00')` for write and `client.read_area(Area.DB, db_number=1, start=0, size=4)` for read.
  - *PDU Analysis*: Inspecting the protocol serializer confirmed that the generated S7 request PDUs (`32 01 0000 0001 000e 0008 05 01 12 0a 10 02 0004 0001 84 000000 00 04 0020 41200000`) adhere strictly to the Siemens S7 Read Var (`0x04`) and Write Var (`0x05`) specifications.
  - *S7 Error 0x8104 Cause*: In Siemens S7-1200/1500 and PLCSIM, protocol error `0x8104` ("This service is not implemented on the module or a frame error was reported") is returned by the CPU firmware when an external client attempts absolute byte addressing on a Data Block that has **"Optimized block access"** enabled in TIA Portal, or if DB1 is not loaded into the PLC memory.
  - *Status*: Root cause isolated. Next step is testing Marker memory (M-area) to verify non-DB I/O and confirming DB1 optimization setting.

### Bug 2: CPU State Service Not Implemented on PLCSIM
- **Exact Observed Behavior**: Connection Status shows `CPU State: UNKNOWN — CPU state unavailable`. Communication log shows: `CPU_STATE raw=ERROR type=S7ProtocolError decoded=UNKNOWN (S7 protocol error (class=0x84/0x81, code=0x04))`.
- **Error Message**: `S7 protocol error (class=0x84/0x81, code=0x04): The function cannot be performed / This service is not implemented`
- **Reproduction Steps**: Click `Connect` or `Test S7 Communication` against PLCSIM.
- **Diagnostic Findings**: Standard S7-1200/PLCSIM targets do not implement the legacy S7-300 SZL CPU state query (`client.get_cpu_state()`).
- **Status**: Decoupled from data connection in `v1.0.6` so it does not disconnect the socket, but CPU state remains unavailable from this target.

---

## Completed tasks
- **2026-10-12**: 
  - Fixed `AttributeError: module 'snap7' has no attribute 'exceptions'` by mapping `snap7.error.S7Error` across `s7_client.py`.
  - Decoupled CPU-state query failures from S7 connection health in `plc_manager.py:_health_monitor_loop` to prevent cyclic disconnection.
  - Fixed monitoring scheduler so `poll_tags()` runs and updates live poll diagnostics (`Last Poll`, `Attempted`, `Failed`, `Success`).
  - Added build marker `v1.0.6 [DIAG_READ_CPU_006]` to window title and UI header.
  - Rebuilt `dist/RepoGen-S7-Setup.exe` and `dist/RepoGen-Portable.zip`.
- **2026-10-13 (Problem 1 Investigation & Verification)**:
  - Source inspection completed:
    - Connection setup: `backend/s7_client.py:70-114`
    - Read requests: `backend/s7_client.py:207-238`
    - Write requests: `backend/s7_client.py:240-276`
    - Address parsing: `backend/tag_utils.py:17-61`
    - Encoding/decoding: `backend/tag_utils.py:63-147`
    - Batch poll loop: `backend/tag_manager.py:43-118`
    - Write verification: `backend/tag_manager.py:129-188`
  - Verified Snap7 API usage against `python-snap7 3.2.1`: `read_area` / `write_area` with `Area.DB` and `Area.MK` strictly conform to the S7 protocol specification.
  - Updated `test_snap7.py` to isolate DB1 REAL (`DB1.DBD0`), DB1 BOOL (`DB1.DBX4.0`), and M-Memory INT (`MW0`).
  - Executed end-to-end read, write, and poll verification test against test server:
    - Write DB1 REAL (10.0): `WRITE VERIFIED` (Readback: 10.0, Latency: 0ms)
    - Write DB1 BOOL (True): `WRITE VERIFIED` (Readback: True, Latency: 0ms)
    - Write MW0 INT (1234): `WRITE VERIFIED` (Readback: 1234, Latency: 0ms)
    - Polling Diagnostics: Attempted: 3, Success: 3, Failed: 0, Latency: 0ms
  - Confirmed root cause of `S7 protocol error (class=0x81, code=0x04)` on live PLC:
    - Software implementation and PDU generation are completely valid.
    - S7 protocol error `0x8104` is returned directly by the Siemens S7-1200/1500/PLCSIM CPU when accessing a Data Block configured with **"Optimized block access"** in TIA Portal (Attributes -> Optimized block access [x]) or if DB1 is not loaded into PLC memory. Standard memory (M-area) is unaffected by block optimization.

---

## To-do list
- [x] Fix `snap7.exceptions` import/attribute crash in write and read paths.
- [x] Ensure monitoring scheduler activates and logs poll cycles.
- [x] Decouple CPU-state failures from connection status so socket is not torn down.
- [x] Diagnose exact Snap7 call producing `class=0x81, code=0x04` on tag write and read.
- [x] Verify Snap7 API operation (`read_area`/`write_area`) for Data Blocks and Marker memory.
- [x] Update and verify `test_snap7.py` with DB1 REAL, DB1 BOOL, and MW0 INT read/write tests.
- [x] Complete Problem 1 source inspection, API verification, and root cause diagnosis.
- [ ] Problem 2: Fix or handle `0x8104`/`0x8404` CPU state query so it displays `UNKNOWN` without breaking connection status or data communication.
- [ ] Problem 3: Live monitoring diagnostics (verify poll cycle counts, quality, and latency).
- [ ] Problem 4: Write error handling verification.
- [ ] Confirm DB1 "Optimized block access" is unchecked in TIA Portal (Attributes -> Optimized block access [ ]).

---

## Known regressions and protected functionality
- **Protected: S7 TCP and Handshake Connection**: `connect()` and auto-recovery must remain intact.
- **Protected: No Cyclic Disconnections**: CPU-state unavailability must never trigger `client.disconnect()`.
- **Protected: Tag Table & Database Persistence**: Existing tag definitions and table schemas must be preserved.
- **Protected: Live Monitoring Scheduling**: Background polling loop must continue executing once monitoring starts.
- **Protected: Exception Handlers**: Never revert to referencing non-existent `snap7.exceptions`.

---

## Latest build and test results
- **Build Marker**: `v1.0.6 [DIAG_READ_CPU_006]`
- **Build Date**: 2026-10-12 21:41
- **End-to-End Test (2026-10-13)**:
  - Backend S7Client + TagManager: 100% PASS (DB1 REAL, DB1 BOOL, MW0 INT read, write, and verification passed).
  - Monitoring scheduler: 100% PASS (Attempted: 3, Success: 3, Failed: 0, Quality: GOOD).

---

## Next action
- **Task**: Report Problem 1 findings in strict accordance with the mandatory format, and await confirmation/instruction before starting Problem 2.

