"""COM Bridge to Adobe Photoshop with auto-reconnect"""
import win32com.client
import pythoncom
import time
import logging

logger = logging.getLogger(__name__)


class PhotoshopBridge:
    """Wrapper for Photoshop COM interface with error handling"""
    
    def __init__(self, max_retries=3):
        self.app = None
        self.max_retries = max_retries
        self._connect()
    
    def _connect(self):
        """Establish COM connection to Photoshop"""
        try:
            pythoncom.CoInitialize()
            self.app = win32com.client.Dispatch("Photoshop.Application")
            logger.info(f"Connected to Photoshop {self.app.Version}")
        except Exception as e:
            logger.error(f"Failed to connect to Photoshop: {e}")
            raise ConnectionError("Adobe Photoshop не запущен или недоступен")
    
    def reconnect(self):
        """Attempt to reconnect to Photoshop"""
        logger.warning("Attempting to reconnect to Photoshop...")
        self.app = None
        time.sleep(1)
        self._connect()
    
    def execute_jsx(self, jsx_code):
        """Execute ExtendScript (JSX) code in Photoshop
        
        Args:
            jsx_code: JavaScript code to execute
            
        Returns:
            Result string from Photoshop
        """
        for attempt in range(self.max_retries):
            try:
                result = self.app.DoJavaScript(jsx_code)
                return result
            except Exception as e:
                logger.error(f"JSX execution failed (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    self.reconnect()
                else:
                    raise
        return None
    
    @property
    def active_document(self):
        """Get currently active Photoshop document"""
        try:
            return self.app.ActiveDocument
        except:
            return None
    
    def close(self):
        """Clean up COM resources"""
        self.app = None
        pythoncom.CoUninitialize()
