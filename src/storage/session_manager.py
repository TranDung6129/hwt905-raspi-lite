# src/storage/session_manager.py

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Quản lý session cho việc lưu trữ dữ liệu.
    """
    
    def __init__(self, session_prefix: str = "session"):
        """
        Khởi tạo SessionManager.
        
        Args:
            session_prefix: Tiền tố cho tên session
        """
        self.session_prefix = session_prefix
        self.current_session = self._create_new_session()
        logger.debug(f"SessionManager initialized with session: {self.current_session}")
    
    def _create_new_session(self) -> str:
        """Tạo session ID mới dựa trên timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.session_prefix}_{timestamp}"
    
    def get_current_session(self) -> str:
        """Lấy session hiện tại."""
        return self.current_session
    
    def create_new_session(self) -> str:
        """Tạo session mới và trả về ID."""
        self.current_session = self._create_new_session()
        logger.info(f"Created new session: {self.current_session}")
        return self.current_session
    
    def set_session(self, session_id: str):
        """Đặt session ID cụ thể."""
        self.current_session = session_id
        logger.info(f"Session set to: {self.current_session}")
