import os
import sys
import webview
from backend.app_service import AppService
import logging

# Configure file and stream logging
app_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
log_file = os.path.join(app_dir, "repogen_runtime.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8", mode="a"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_base_path():
    """
    Get the absolute path to the resource, works for dev and for PyInstaller.
    PyInstaller creates a temp folder and stores path in _MEIPASS.
    """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))

def main():
    logger.info("========================================")
    logger.info("Starting RepoGen S7 Communication Tool")
    logger.info("DIAG_READ_CPU_006 - Version: 1.0.6")
    logger.info(f"Executable path: {sys.executable}")
    logger.info(f"Runtime log path: {log_file}")
    logger.info("========================================")

    # Initialize backend service
    service = AppService()
    
    # Find frontend path
    base_path = get_base_path()
    frontend_path = os.path.join(base_path, 'frontend', 'index.html')
    
    logger.info(f"Loading frontend from: {frontend_path}")
    
    # Check if frontend exists to prevent white screen of death
    if not os.path.exists(frontend_path):
        logger.error(f"Frontend file not found: {frontend_path}")
        sys.exit(1)

    window = webview.create_window(
        title="RepoGen - S7 Communication Tool - v1.0.6 [DIAG_READ_CPU_006]", 
        url=frontend_path,
        js_api=service,
        width=1024,
        height=768,
        min_size=(800, 600),
        resizable=True,
        background_color='#121212'
    )
    
    # Start the webview application
    try:
        webview.start(debug=False)
    except Exception as e:
        logger.error(f"Failed to start webview: {e}")
        
    logger.info("Application closed")

if __name__ == '__main__':
    main()
