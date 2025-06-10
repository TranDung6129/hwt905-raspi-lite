# src/storage/storage_manager.py

import logging
from typing import Dict, Any, List, Optional

from .data_storage import DataStorage

logger = logging.getLogger(__name__)

class StorageManager:
    """
    Lớp quản lý tổng thể việc lưu trữ và truyền dữ liệu.
    Tích hợp với luồng xử lý hiện tại để hỗ trợ lưu trữ trong môi trường kết nối gián đoạn.
    """
    
    def __init__(self, storage_config: Dict[str, Any], 
                 data_type: str = "processed",
                 fields_to_write: Optional[List[str]] = None):
        """
        Khởi tạo StorageManager.
        
        Args:
            storage_config: Cấu hình cho storage system
            data_type: Loại dữ liệu ('processed' hoặc 'decoded') để xác định thư mục con.
            fields_to_write: Danh sách các cột cụ thể để ghi (cho CSV).
        """
        self.storage_enabled = storage_config.get("enabled", True)
        self.immediate_transmission = storage_config.get("immediate_transmission", True)
        self.batch_transmission_size = storage_config.get("batch_transmission_size", 50)
        self.data_type = data_type
        
        if self.storage_enabled:
            # Tạo thư mục con dựa trên data_type
            sub_dir = f"{self.data_type}_data"
            
            self.data_storage = DataStorage(
                base_data_dir=storage_config.get("base_dir", "data"),
                sub_dir=sub_dir,
                storage_format=storage_config.get("format", "csv"),
                max_file_size_mb=storage_config.get("max_file_size_mb", 10.0),
                session_prefix=storage_config.get("session_prefix", "session"),
                fields_to_write=fields_to_write
            )
        else:
            self.data_storage = None
        
        logger.info(f"StorageManager initialized for '{self.data_type}' - Enabled: {self.storage_enabled}, Immediate transmission: {self.immediate_transmission}")
    
    def store_and_prepare_for_transmission(self, data: Dict[str, Any], timestamp: float = None) -> Optional[Dict[str, Any]]:
        """
        Lưu trữ dữ liệu và chuẩn bị cho việc truyền.
        
        Args:
            data: Dữ liệu (đã xử lý hoặc đã giải mã)
            timestamp: Timestamp (sử dụng thời gian hiện tại nếu None)
            
        Returns:
            Dữ liệu để truyền ngay (nếu immediate_transmission=True), None nếu chỉ lưu trữ
        """
        # Luôn lưu trữ nếu storage được bật
        if self.storage_enabled and self.data_storage:
            self.data_storage.store_data(data, timestamp)
        
        # Trả về dữ liệu để truyền ngay nếu được cấu hình
        if self.immediate_transmission:
            return data
        
        return None
    
    def get_batch_for_transmission(self) -> List[Dict[str, Any]]:
        """
        Lấy một batch dữ liệu từ storage để truyền đi.
        
        Returns:
            Danh sách dữ liệu cần truyền
        """
        if not self.storage_enabled or not self.data_storage:
            return []
        
        return self.data_storage.get_pending_data_for_transmission(self.batch_transmission_size)
    
    def get_current_session(self) -> Optional[str]:
        """Lấy session hiện tại."""
        if self.data_storage:
            return self.data_storage.get_current_session()
        return None
    
    def create_new_session(self) -> Optional[str]:
        """Tạo session mới."""
        if self.data_storage:
            return self.data_storage.create_new_session()
        return None
    
    def is_enabled(self) -> bool:
        """Kiểm tra xem storage có được bật không."""
        return self.storage_enabled
    
    def close(self):
        """Đóng storage manager."""
        if self.data_storage:
            self.data_storage.close()
