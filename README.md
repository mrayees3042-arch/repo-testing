# RepoGen S7 — Siemens S7 PLC Communication & Diagnostics Tool (v1)

RepoGen S7 is a desktop GUI utility built for Siemens S7 PLC communication, diagnostics, tag monitoring, and read/write operations. It supports S7-300, S7-400, S7-1200, S7-1500, and PLCSIM/NetToPLCSim environments.

## Features
- **S7 Communication**: Fast ISO-on-TCP connection over port 102 using Snap7.
- **Diagnostics**: Network Ping, TCP Port verification, CPU-state queries, and connection health monitoring with auto-reconnection.
- **Tag Tables & Monitoring**: Live monitoring with real-time poll diagnostics (Attempted, Success, Failed, Latency, Quality).
- **Read & Write Verification**: Support for DB variables (REAL, BOOL, INT, etc.) and Marker memory (MW, MD) with read-modify-write bit safety and write readback verification.
- **Standalone Desktop GUI**: Built with Python and pywebview, packaged as a single standalone executable.

## Directory Structure
- `backend/` — Core S7 client (`s7_client.py`), tag manager (`tag_manager.py`), address parser and codec (`tag_utils.py`), PLC health monitor (`plc_manager.py`), and SQLite persistence (`database.py`).
- `frontend/` — Single-page interface assets (HTML, CSS, JavaScript).
- `dist/` — Standalone executable and portable archive deliverables.
- `main.py` — Application entry point.
- `build.py` — PyInstaller packaging script.
- `PROJECT_STATUS.md` — Detailed engineering status, bug resolutions, and technical handover.

## Quick Start (Development)
```bash
# Set up virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install python-snap7 pywebview

# Run application
python main.py
```
