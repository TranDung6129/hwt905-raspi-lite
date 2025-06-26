# src/storage/storage_manager.py

import logging
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class StorageManager:
    """
    Quản lý việc lưu trữ dữ liệu cảm biến vào file CSV.
    Tự động xoay vòng file lưu trữ dựa trên thời gian (ví dụ: mỗi giờ một file mới).
    """

    def __init__(self,
                 base_dir: str,
                 file_rotation_hours: int,
                 fields_to_write: List[str],
                 reconnection_strategy: str = "new_file"):
        """
        Khởi tạo StorageManager.

        Args:
            base_dir (str): Thư mục gốc để lưu các file dữ liệu.
            file_rotation_hours (int): Số giờ trước khi tạo một file mới.
            fields_to_write (List[str]): Danh sách các tên cột cho file CSV.
            reconnection_strategy (str): "new_file" hoặc "continue_file" - cách xử lý khi kết nối lại.
        """
        self.base_dir = base_dir
        self.file_rotation_delta = timedelta(hours=file_rotation_hours)
        self.fields_to_write = fields_to_write
        self.reconnection_strategy = reconnection_strategy

        self.current_file_path: Optional[str] = None
        self.current_file_writer: Optional[csv.DictWriter] = None
        self.current_file_handle: Optional[Any] = None
        self.current_file_start_time: Optional[datetime] = None

        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"StorageManager khởi tạo. Lưu dữ liệu trong '{self.base_dir}', xoay file mỗi {file_rotation_hours} giờ. Chế độ kết nối lại: {reconnection_strategy}")

    def _get_new_filepath(self) -> str:
        """Tạo đường dẫn file mới dựa trên thời gian hiện tại."""
        now = datetime.now()
        filename = f"data_{now.strftime('%Y%m%d-%H%M%S')}.csv"
        return os.path.join(self.base_dir, filename)

    def _open_new_file(self):
        """Mở một file CSV mới để ghi và ghi header."""
        self.close_current_file()  # Đảm bảo file cũ đã được đóng

        self.current_file_path = self._get_new_filepath()
        self.current_file_start_time = datetime.now()
        try:
            self.current_file_handle = open(self.current_file_path, 'w', newline='', encoding='utf-8')
            self.current_file_writer = csv.DictWriter(self.current_file_handle, fieldnames=self.fields_to_write)
            self.current_file_writer.writeheader()
            logger.info(f"Mở file lưu trữ mới: {self.current_file_path}")
        except IOError as e:
            logger.error(f"Không thể mở file mới '{self.current_file_path}': {e}")
            self.current_file_path = None
            self.current_file_writer = None
            self.current_file_handle = None
            self.current_file_start_time = None

    def _find_latest_file(self) -> Optional[str]:
        """Tìm file dữ liệu mới nhất trong thư mục."""
        if not os.path.exists(self.base_dir):
            return None
            
        data_files = []
        for filename in os.listdir(self.base_dir):
            if filename.startswith('data_') and filename.endswith('.csv'):
                file_path = os.path.join(self.base_dir, filename)
                if os.path.isfile(file_path):
                    # Lấy thời gian sửa đổi cuối cùng
                    mtime = os.path.getmtime(file_path)
                    data_files.append((mtime, file_path))
        
        if data_files:
            # Sắp xếp theo thời gian và lấy file mới nhất
            data_files.sort(reverse=True)
            return data_files[0][1]
        return None

    def _continue_existing_file(self, file_path: str) -> bool:
        """Tiếp tục ghi vào file đã có."""
        try:
            self.current_file_path = file_path
            # Lấy thời gian tạo file từ tên file
            filename = os.path.basename(file_path)
            if filename.startswith('data_') and filename.endswith('.csv'):
                # Extract timestamp từ filename (format: data_YYYYMMDD-HHMMSS.csv)
                timestamp_str = filename[5:20]  # Lấy phần YYYYMMDD-HHMMSS
                try:
                    self.current_file_start_time = datetime.strptime(timestamp_str, '%Y%m%d-%H%M%S')
                except ValueError:
                    # Nếu không parse được, dùng thời gian hiện tại
                    self.current_file_start_time = datetime.now()
            else:
                self.current_file_start_time = datetime.now()
                
            # Mở file ở chế độ append
            self.current_file_handle = open(self.current_file_path, 'a', newline='', encoding='utf-8')
            self.current_file_writer = csv.DictWriter(self.current_file_handle, fieldnames=self.fields_to_write)
            
            logger.info(f"Tiếp tục ghi vào file hiện có: {self.current_file_path}")
            return True
        except Exception as e:
            logger.error(f"Không thể mở file để tiếp tục '{file_path}': {e}")
            return False

    def write_data(self, data: Dict[str, Any]):
        """
        Ghi một dòng dữ liệu vào file CSV hiện tại.
        Kiểm tra và xoay vòng file nếu cần thiết.
        """
        # Nếu chưa có file nào được mở, quyết định mở file mới hay tiếp tục file cũ
        if self.current_file_writer is None:
            if self.reconnection_strategy == "continue_file":
                # Thử tìm và tiếp tục file mới nhất
                latest_file = self._find_latest_file()
                if latest_file and self._continue_existing_file(latest_file):
                    # Kiểm tra xem file cũ có cần rotation không
                    if (self.current_file_start_time and 
                        datetime.now() >= self.current_file_start_time + self.file_rotation_delta):
                        # File cũ đã quá thời hạn, tạo file mới
                        self._open_new_file()
                else:
                    # Không tìm thấy file cũ hoặc không mở được, tạo file mới
                    self._open_new_file()
            else:
                # Chế độ new_file - luôn tạo file mới
                self._open_new_file()
        
        # Kiểm tra xem có cần xoay vòng file không (cho file hiện tại)
        elif (self.current_file_start_time and 
              datetime.now() >= self.current_file_start_time + self.file_rotation_delta):
            self._open_new_file()

        # Ghi dữ liệu nếu file đã mở thành công
        if self.current_file_writer and self.current_file_handle:
            try:
                self.current_file_writer.writerow(data)
            except IOError as e:
                logger.error(f"Lỗi khi ghi vào file '{self.current_file_path}': {e}")
                # Cố gắng mở lại file ở lần ghi tiếp theo
                self.close_current_file()

    def close_current_file(self):
        """Đóng file đang mở hiện tại."""
        if self.current_file_handle:
            try:
                self.current_file_handle.close()
                logger.info(f"Đóng file: {self.current_file_path}")
            except IOError as e:
                logger.error(f"Lỗi khi đóng file '{self.current_file_path}': {e}")
        
        self.current_file_path = None
        self.current_file_writer = None
        self.current_file_handle = None
        self.current_file_start_time = None
