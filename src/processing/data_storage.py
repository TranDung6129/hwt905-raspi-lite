# src/processing/data_storage.py

import os
import json
import csv
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ProcessedDataStorage:
    """
    Lớp quản lý lưu trữ dữ liệu đã xử lý vào thư mục data.
    Hỗ trợ lưu trữ liên tục và đọc dữ liệu để truyền đi.
    """
    
    def __init__(self, base_data_dir: str = "data", 
                 storage_format: str = "csv",
                 max_file_size_mb: float = 10.0,
                 session_prefix: str = "session"):
        """
        Khởi tạo ProcessedDataStorage.
        
        Args:
            base_data_dir: Thư mục gốc để lưu dữ liệu
            storage_format: Định dạng lưu trữ ('csv' hoặc 'json')
            max_file_size_mb: Kích thước tối đa của file trước khi tạo file mới
            session_prefix: Tiền tố cho tên session
        """
        self.base_data_dir = Path(base_data_dir)
        self.processed_data_dir = self.base_data_dir / "processed_data"
        self.storage_format = storage_format
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.session_prefix = session_prefix
        
        # Tạo thư mục nếu chưa tồn tại
        self._ensure_directories()
        
        # Khởi tạo session hiện tại
        self.current_session = self._create_new_session()
        self.current_file_path = None
        self.current_file_handle = None
        self.current_csv_writer = None
        self.data_count_in_current_file = 0
        
        logger.info(f"ProcessedDataStorage initialized - Session: {self.current_session}, Format: {storage_format}")
    
    def _ensure_directories(self):
        """Tạo các thư mục cần thiết nếu chưa tồn tại."""
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {self.processed_data_dir}")
    
    def _create_new_session(self) -> str:
        """Tạo session ID mới dựa trên timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.session_prefix}_{timestamp}"
    
    def _get_file_extension(self) -> str:
        """Lấy phần mở rộng file dựa trên format."""
        return "csv" if self.storage_format == "csv" else "json"
    
    def _create_new_file(self):
        """Tạo file mới để lưu dữ liệu."""
        if self.current_file_handle:
            self._close_current_file()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        part_number = len(list(self.processed_data_dir.glob(f"{self.current_session}_part*.{self._get_file_extension()}"))) + 1
        
        filename = f"{self.current_session}_part{part_number:03d}_{timestamp}.{self._get_file_extension()}"
        self.current_file_path = self.processed_data_dir / filename
        
        if self.storage_format == "csv":
            self.current_file_handle = open(self.current_file_path, 'w', newline='', encoding='utf-8')
            self.current_csv_writer = csv.writer(self.current_file_handle)
            # Viết header cho CSV
            self._write_csv_header()
        else:
            self.current_file_handle = open(self.current_file_path, 'w', encoding='utf-8')
        
        self.data_count_in_current_file = 0
        logger.info(f"Created new data file: {self.current_file_path}")
    
    def _write_csv_header(self):
        """Viết header cho file CSV."""
        header = [
            'timestamp', 'acc_x', 'acc_y', 'acc_z',
            'disp_x', 'disp_y', 'disp_z', 'disp_magnitude',
            'freq_x', 'freq_y', 'freq_z', 'dominant_freq',
            'rls_warmed_up'
        ]
        self.current_csv_writer.writerow(header)
    
    def _close_current_file(self):
        """Đóng file hiện tại."""
        if self.current_file_handle:
            self.current_file_handle.close()
            self.current_file_handle = None
            self.current_csv_writer = None
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
    
    def store_processed_data(self, processed_data: Dict[str, Any], timestamp: float = None):
        """
        Lưu trữ dữ liệu đã xử lý vào file.
        
        Args:
            processed_data: Dữ liệu đã xử lý từ SensorDataProcessor
            timestamp: Timestamp Unix (sử dụng thời gian hiện tại nếu None)
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Tạo file mới nếu cần
        if self._should_create_new_file():
            self._create_new_file()
        
        try:
            if self.storage_format == "csv":
                self._store_csv_data(processed_data, timestamp)
            else:
                self._store_json_data(processed_data, timestamp)
            
            self.data_count_in_current_file += 1
            
            # Flush dữ liệu để đảm bảo được ghi vào disk
            if self.current_file_handle:
                self.current_file_handle.flush()
                
        except Exception as e:
            logger.error(f"Error storing processed data: {e}")
    
    def _store_csv_data(self, processed_data: Dict[str, Any], timestamp: float):
        """Lưu dữ liệu dưới định dạng CSV."""
        row = [
            timestamp,
            processed_data.get('acc_x', 0),
            processed_data.get('acc_y', 0),
            processed_data.get('acc_z', 0),
            processed_data.get('displacement_x', 0),
            processed_data.get('displacement_y', 0),
            processed_data.get('displacement_z', 0),
            processed_data.get('displacement_magnitude', 0),
            processed_data.get('dominant_frequency_x', 0),
            processed_data.get('dominant_frequency_y', 0),
            processed_data.get('dominant_frequency_z', 0),
            processed_data.get('overall_dominant_frequency', 0),
            processed_data.get('rls_warmed_up', False)
        ]
        self.current_csv_writer.writerow(row)
    
    def _store_json_data(self, processed_data: Dict[str, Any], timestamp: float):
        """Lưu dữ liệu dưới định dạng JSON."""
        data_entry = {
            'timestamp': timestamp,
            'data': processed_data
        }
        json.dump(data_entry, self.current_file_handle)
        self.current_file_handle.write('\n')  # Mỗi entry trên một dòng
    
    def get_stored_data_files(self, session: str = None) -> List[Path]:
        """
        Lấy danh sách các file dữ liệu đã lưu.
        
        Args:
            session: Session cụ thể (sử dụng session hiện tại nếu None)
            
        Returns:
            Danh sách các file path
        """
        if session is None:
            session = self.current_session
        
        pattern = f"{session}_part*.{self._get_file_extension()}"
        files = list(self.processed_data_dir.glob(pattern))
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
        data = []
        try:
            if self.storage_format == "csv":
                data = self._read_csv_data(file_path, limit)
            else:
                data = self._read_json_data(file_path, limit)
        except Exception as e:
            logger.error(f"Error reading data from {file_path}: {e}")
        
        return data
    
    def _read_csv_data(self, file_path: Path, limit: int = None) -> List[Dict[str, Any]]:
        """Đọc dữ liệu từ file CSV."""
        data = []
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                
                # Chuyển đổi các giá trị số
                processed_row = {}
                for key, value in row.items():
                    if key == 'timestamp':
                        processed_row[key] = float(value)
                    elif key == 'rls_warmed_up':
                        processed_row[key] = value.lower() == 'true'
                    else:
                        try:
                            processed_row[key] = float(value)
                        except ValueError:
                            processed_row[key] = value
                
                data.append(processed_row)
        
        return data
    
    def _read_json_data(self, file_path: Path, limit: int = None) -> List[Dict[str, Any]]:
        """Đọc dữ liệu từ file JSON."""
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                
                try:
                    entry = json.loads(line.strip())
                    data.append(entry)
                except json.JSONDecodeError:
                    continue
        
        return data
    
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
    
    def close(self):
        """Đóng storage và dọn dẹp tài nguyên."""
        self._close_current_file()
        logger.info(f"ProcessedDataStorage closed - Session: {self.current_session}")


class StorageManager:
    """
    Lớp quản lý tổng thể việc lưu trữ và truyền dữ liệu.
    Tích hợp với luồng xử lý hiện tại để hỗ trợ lưu trữ trong môi trường kết nối gián đoạn.
    """
    
    def __init__(self, storage_config: Dict[str, Any]):
        """
        Khởi tạo StorageManager.
        
        Args:
            storage_config: Cấu hình cho storage system
        """
        self.storage_enabled = storage_config.get("enabled", True)
        self.immediate_transmission = storage_config.get("immediate_transmission", True)
        self.batch_transmission_size = storage_config.get("batch_transmission_size", 50)
        
        if self.storage_enabled:
            self.data_storage = ProcessedDataStorage(
                base_data_dir=storage_config.get("base_dir", "data"),
                storage_format=storage_config.get("format", "csv"),
                max_file_size_mb=storage_config.get("max_file_size_mb", 10.0),
                session_prefix=storage_config.get("session_prefix", "session")
            )
        else:
            self.data_storage = None
        
        logger.info(f"StorageManager initialized - Enabled: {self.storage_enabled}, Immediate transmission: {self.immediate_transmission}")
    
    def store_and_prepare_for_transmission(self, processed_data: Dict[str, Any], timestamp: float = None) -> Optional[Dict[str, Any]]:
        """
        Lưu trữ dữ liệu và chuẩn bị cho việc truyền.
        
        Args:
            processed_data: Dữ liệu đã xử lý
            timestamp: Timestamp (sử dụng thời gian hiện tại nếu None)
            
        Returns:
            Dữ liệu để truyền ngay (nếu immediate_transmission=True), None nếu chỉ lưu trữ
        """
        # Luôn lưu trữ nếu storage được bật
        if self.storage_enabled and self.data_storage:
            self.data_storage.store_processed_data(processed_data, timestamp)
        
        # Trả về dữ liệu để truyền ngay nếu được cấu hình
        if self.immediate_transmission:
            return processed_data
        
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
    
    def close(self):
        """Đóng storage manager."""
        if self.data_storage:
            self.data_storage.close()
