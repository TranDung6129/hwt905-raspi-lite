# src/storage/data_storage.py

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .session_manager import SessionManager
from .file_handlers import create_file_handler, BaseFileHandler

logger = logging.getLogger(__name__)

class DataStorage:
    """
    Lớp quản lý lưu trữ dữ liệu vào thư mục data.
    Hỗ trợ lưu trữ liên tục và đọc dữ liệu để truyền đi.
    """
    
    def __init__(self, base_data_dir: str = "data",
                 sub_dir: str = "processed_data",
                 storage_format: str = "csv",
                 max_file_size_mb: float = 10.0,
                 session_prefix: str = "session",
                 fields_to_write: Optional[List[str]] = None):
        """
        Khởi tạo DataStorage.
        
        Args:
            base_data_dir: Thư mục gốc để lưu dữ liệu
            sub_dir: Thư mục con để lưu trữ dữ liệu (vd: 'processed_data', 'decoded_data')
            storage_format: Định dạng lưu trữ ('csv' hoặc 'json')
            max_file_size_mb: Kích thước tối đa của file trước khi tạo file mới
            session_prefix: Tiền tố cho tên session
            fields_to_write: Danh sách các cột cụ thể để ghi vào file CSV.
        """
        self.base_data_dir = Path(base_data_dir)
        self.data_dir = self.base_data_dir / sub_dir
        self.storage_format = storage_format.lower()
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.fields_to_write = fields_to_write
        
        # Khởi tạo session manager
        self.session_manager = SessionManager(session_prefix)
        
        # Tạo thư mục nếu chưa tồn tại
        self._ensure_directories()
        
        # File handling
        self.current_file_path = None
        self.current_file_handler = None
        self.data_count_in_current_file = 0
        
        logger.info(f"DataStorage initialized for '{sub_dir}' - Session: {self.session_manager.get_current_session()}, Format: {storage_format}")
    
    def _ensure_directories(self):
        """Tạo các thư mục cần thiết nếu chưa tồn tại."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {self.data_dir}")
    
    def _get_file_extension(self) -> str:
        """Lấy phần mở rộng file dựa trên format."""
        return "csv" if self.storage_format == "csv" else "json"
    
    def _create_new_file(self):
        """Tạo file mới để lưu dữ liệu."""
        if self.current_file_handler:
            self._close_current_file()
        
        current_session = self.session_manager.get_current_session()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Tính part number dựa trên số file hiện có
        pattern = f"{current_session}_part*.{self._get_file_extension()}"
        existing_files = list(self.data_dir.glob(pattern))
        part_number = len(existing_files) + 1
        
        filename = f"{current_session}_part{part_number:03d}_{timestamp}.{self._get_file_extension()}"
        self.current_file_path = self.data_dir / filename
        
        # Tạo file handler mới với các trường được chỉ định
        self.current_file_handler = create_file_handler(
            self.current_file_path, 
            self.storage_format, 
            fields_to_write=self.fields_to_write
        )
        self.current_file_handler.open_for_writing()
        
        self.data_count_in_current_file = 0
        logger.info(f"Created new data file: {self.current_file_path}")
    
    def _close_current_file(self):
        """Đóng file hiện tại."""
        if self.current_file_handler:
            self.current_file_handler.close()
            self.current_file_handler = None
            logger.debug(f"Closed file: {self.current_file_path}")
    
    def _should_create_new_file(self) -> bool:
        """Kiểm tra xem có cần tạo file mới không."""
        if not self.current_file_path or not self.current_file_path.exists():
            return True
        
        try:
            file_size = self.current_file_path.stat().st_size
            return file_size >= self.max_file_size_bytes
        except OSError:
            return True
    
    def store_data(self, data: Dict[str, Any], timestamp: float = None):
        """
        Lưu trữ dữ liệu vào file.
        
        Args:
            data: Dữ liệu cần lưu
            timestamp: Timestamp Unix (sử dụng thời gian hiện tại nếu None)
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Tạo file mới nếu cần
        if self._should_create_new_file():
            self._create_new_file()
        
        try:
            # Ghi dữ liệu thông qua file handler
            self.current_file_handler.write_data(data, timestamp)
            self.data_count_in_current_file += 1
            
            # Flush dữ liệu để đảm bảo được ghi vào disk
            self.current_file_handler.flush()
                
        except Exception as e:
            logger.error(f"Error storing data: {e}")
    
    def get_stored_data_files(self, session: str = None) -> List[Path]:
        """
        Lấy danh sách các file dữ liệu đã lưu.
        
        Args:
            session: Session cụ thể (sử dụng session hiện tại nếu None)
            
        Returns:
            Danh sách các file path
        """
        if session is None:
            session = self.session_manager.get_current_session()
        
        pattern = f"{session}_part*.{self._get_file_extension()}"
        files = list(self.data_dir.glob(pattern))
        return sorted(files)
    
    def read_stored_data(self, file_path: Path, limit: int = None) -> List[Dict[str, Any]]:
        """
        Đọc dữ liệu từ file đã lưu.
        
        Args:
            file_path: Đường dẫn đến file
            limit: Giới hạn số dòng đọc (None = đọc tất cả)
            
        Returns:
            Danh sách các entry dữ liệu
        """
        try:
            # Tạo file handler tạm để đọc dữ liệu
            file_handler = create_file_handler(file_path, self.storage_format)
            data = file_handler.read_data(limit)
            return data
        except Exception as e:
            logger.error(f"Error reading data from {file_path}: {e}")
            return []
    
    def get_pending_data_for_transmission(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """
        Lấy dữ liệu chưa được truyền đi để gửi qua MQTT.
        
        Args:
            batch_size: Số lượng records tối đa trong một batch
            
        Returns:
            Danh sách dữ liệu cần truyền
        """
        # Đơn giản hóa: đọc từ file gần nhất
        files = self.get_stored_data_files()
        if not files:
            return []
        
        latest_file = files[-1]
        return self.read_stored_data(latest_file, limit=batch_size)
    
    def get_current_session(self) -> str:
        """Lấy session hiện tại."""
        return self.session_manager.get_current_session()
    
    def create_new_session(self) -> str:
        """Tạo session mới."""
        new_session = self.session_manager.create_new_session()
        # Đóng file hiện tại để tạo file mới trong session mới
        if self.current_file_handler:
            self._close_current_file()
        return new_session
    
    def close(self):
        """Đóng storage và dọn dẹp tài nguyên."""
        self._close_current_file()
        logger.info(f"DataStorage closed - Session: {self.session_manager.get_current_session()}")
