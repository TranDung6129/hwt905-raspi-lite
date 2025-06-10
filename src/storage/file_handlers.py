# src/storage/file_handlers.py

import csv
import json
import logging
import numpy as np
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class BaseFileHandler(ABC):
    """
    Lớp cơ sở cho các file handler.
    """
    
    def __init__(self, file_path: Path):
        """
        Khởi tạo BaseFileHandler.
        
        Args:
            file_path: Đường dẫn đến file
        """
        self.file_path = file_path
        self.file_handle = None
    
    @abstractmethod
    def open_for_writing(self):
        """Mở file để ghi."""
        pass
    
    @abstractmethod
    def write_data(self, data: Dict[str, Any], timestamp: float):
        """Ghi dữ liệu vào file."""
        pass
    
    @abstractmethod
    def read_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Đọc dữ liệu từ file."""
        pass
    
    def close(self):
        """Đóng file."""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
            logger.debug(f"Closed file: {self.file_path}")
    
    def flush(self):
        """Flush dữ liệu vào disk."""
        if self.file_handle:
            self.file_handle.flush()


class CSVFileHandler(BaseFileHandler):
    """
    Handler cho file CSV.
    """
    
    def __init__(self, file_path: Path, fields_to_write: Optional[List[str]] = None):
        super().__init__(file_path)
        self.dict_writer = None
        self.file_handle = None
        # Đảm bảo 'timestamp' luôn là cột đầu tiên nếu fields_to_write được sử dụng
        if fields_to_write:
            self.fields_to_write = ['timestamp'] + [f for f in fields_to_write if f != 'timestamp']
        else:
            self.fields_to_write = None
        self.header_written = False
    
    def open_for_writing(self):
        """Mở file CSV để ghi."""
        try:
            self.file_handle = open(self.file_path, 'w', newline='', encoding='utf-8')
            # DictWriter sẽ được khởi tạo khi có dữ liệu đầu tiên để xác định header
        except IOError as e:
            logger.error(f"Failed to open CSV file for writing {self.file_path}: {e}")
            raise
    
    def write_data(self, data: Dict[str, Any], timestamp: float):
        """Ghi dữ liệu vào file CSV."""
        if not self.file_handle:
            logger.warning("Attempted to write to a closed or non-existent CSV file.")
            return
        
        full_data = {'timestamp': timestamp, **data}

        # Chuyển đổi các giá trị là list/numpy array thành chuỗi JSON trước khi ghi
        processed_data = {}
        for key, value in full_data.items():
            if isinstance(value, (list, tuple, np.ndarray)):
                processed_data[key] = json.dumps(value.tolist() if isinstance(value, np.ndarray) else value)
            else:
                processed_data[key] = value

        try:
            if not self.header_written:
                # Xác định header: ưu tiên fields_to_write, sau đó là các khóa của dữ liệu
                header = self.fields_to_write if self.fields_to_write else list(processed_data.keys())
                self.dict_writer = csv.DictWriter(self.file_handle, fieldnames=header, extrasaction='ignore')
                self.dict_writer.writeheader()
                self.header_written = True

            # Ghi dòng dữ liệu. extrasaction='ignore' sẽ bỏ qua các key không có trong header.
            self.dict_writer.writerow(processed_data)
        except Exception as e:
            logger.error(f"Error writing data to CSV file {self.file_path}: {e}")
    
    def read_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Đọc dữ liệu từ file CSV."""
        data = []
        
        if not self.file_path.exists():
            return data
        
        try:
            with open(self.file_path, 'r', newline='', encoding='utf-8') as f:
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
        except Exception as e:
            logger.error(f"Error reading CSV data from {self.file_path}: {e}")
        
        return data


class JSONFileHandler(BaseFileHandler):
    """
    Handler cho file JSON.
    """
    
    def open_for_writing(self):
        """Mở file JSON để ghi."""
        self.file_handle = open(self.file_path, 'w', encoding='utf-8')
        logger.debug(f"Opened JSON file for writing: {self.file_path}")
    
    def write_data(self, data: Dict[str, Any], timestamp: float):
        """Ghi dữ liệu vào file JSON."""
        if not self.file_handle:
            raise RuntimeError("File not opened for writing")
        
        data_entry = {
            'timestamp': timestamp,
            'data': data
        }
        json.dump(data_entry, self.file_handle)
        self.file_handle.write('\n')  # Mỗi entry trên một dòng
    
    def read_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Đọc dữ liệu từ file JSON."""
        data = []
        
        if not self.file_path.exists():
            return data
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if limit and i >= limit:
                        break
                    
                    try:
                        entry = json.loads(line.strip())
                        data.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error reading JSON data from {self.file_path}: {e}")
        
        return data


def create_file_handler(file_path: Path, file_format: str, **kwargs) -> BaseFileHandler:
    """
    Factory function để tạo file handler phù hợp.
    
    Args:
        file_path: Đường dẫn đến file
        file_format: Định dạng lưu trữ ('csv' hoặc 'json')
        **kwargs: Các tham số tùy chọn
        
    Returns:
        Instance của file handler tương ứng
    """
    file_format = file_format.lower()
    if file_format == "csv":
        return CSVFileHandler(file_path, fields_to_write=kwargs.get('fields_to_write'))
    elif file_format == "json":
        return JSONFileHandler(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_format}")
