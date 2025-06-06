# src/storage/file_handlers.py

import csv
import json
import logging
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
    
    def __init__(self, file_path: Path):
        super().__init__(file_path)
        self.csv_writer = None
        self.header_written = False
    
    def open_for_writing(self):
        """Mở file CSV để ghi."""
        self.file_handle = open(self.file_path, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.file_handle)
        self._write_header()
        logger.debug(f"Opened CSV file for writing: {self.file_path}")
    
    def _write_header(self):
        """Viết header cho file CSV."""
        header = [
            'timestamp', 'acc_x', 'acc_y', 'acc_z',
            'disp_x', 'disp_y', 'disp_z', 'disp_magnitude',
            'dominant_freq_x', 'dominant_freq_y', 'dominant_freq_z', 'overall_dominant_freq',
            'rls_warmed_up'
        ]
        self.csv_writer.writerow(header)
        self.header_written = True
    
    def write_data(self, data: Dict[str, Any], timestamp: float):
        """Ghi dữ liệu vào file CSV."""
        if not self.csv_writer:
            raise RuntimeError("File not opened for writing")
        
        row = [
            timestamp,
            data.get('acc_x', 0),
            data.get('acc_y', 0),
            data.get('acc_z', 0),
            data.get('disp_x', 0),
            data.get('disp_y', 0),
            data.get('disp_z', 0),
            data.get('displacement_magnitude', 0),
            data.get('dominant_freq_x', 0),
            data.get('dominant_freq_y', 0),
            data.get('dominant_freq_z', 0),
            data.get('overall_dominant_frequency', 0),
            data.get('rls_warmed_up', False)
        ]
        self.csv_writer.writerow(row)
    
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


def create_file_handler(file_path: Path, storage_format: str) -> BaseFileHandler:
    """
    Factory function để tạo file handler phù hợp.
    
    Args:
        file_path: Đường dẫn đến file
        storage_format: Định dạng lưu trữ ('csv' hoặc 'json')
        
    Returns:
        Instance của file handler tương ứng
    """
    if storage_format.lower() == "csv":
        return CSVFileHandler(file_path)
    elif storage_format.lower() == "json":
        return JSONFileHandler(file_path)
    else:
        raise ValueError(f"Unsupported storage format: {storage_format}")
