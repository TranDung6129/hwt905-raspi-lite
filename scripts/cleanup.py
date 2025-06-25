#!/usr/bin/env python3
# scripts/cleanup.py

import logging
import os
import sys
import time
from datetime import datetime, timedelta

# Add project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src import config
    from src.utils.logger_setup import setup_logging
except ImportError as e:
    print(f"FATAL: Could not import necessary modules. Error: {e}")
    sys.exit(1)

logger = logging.getLogger(__name__)

def cleanup_old_files(data_dir: str, days_to_keep: int):
    """
    Scans a directory and deletes files with specific extensions (.sent, .empty)
    that are older than a specified number of days.
    """
    if not os.path.isdir(data_dir):
        logger.warning(f"Thư mục '{data_dir}' không tồn tại. Không có gì để dọn dẹp.")
        return

    logger.info(f"Bắt đầu quét thư mục '{data_dir}' để xóa các file cũ hơn {days_to_keep} ngày...")
    
    cutoff_time = datetime.now() - timedelta(days=days_to_keep)
    files_deleted_count = 0
    
    for filename in os.listdir(data_dir):
        # Chỉ xem xét các file đã được xử lý
        if filename.endswith((".sent", ".empty")):
            filepath = os.path.join(data_dir, filename)
            
            try:
                # Lấy thời gian sửa đổi cuối cùng của file
                file_mod_time_ts = os.path.getmtime(filepath)
                file_mod_time = datetime.fromtimestamp(file_mod_time_ts)
                
                if file_mod_time < cutoff_time:
                    logger.info(f"Đang xóa file cũ: {filename} (sửa đổi lần cuối: {file_mod_time.strftime('%Y-%m-%d %H:%M')})")
                    os.remove(filepath)
                    files_deleted_count += 1
                    
            except FileNotFoundError:
                # File có thể đã bị xóa bởi một tiến trình khác
                logger.warning(f"File '{filename}' không tìm thấy khi đang cố xóa.")
                continue
            except OSError as e:
                logger.error(f"Lỗi khi xóa file '{filepath}': {e}")

    if files_deleted_count > 0:
        logger.info(f"Hoàn thành dọn dẹp. Đã xóa {files_deleted_count} file.")
    else:
        logger.info("Không tìm thấy file nào đủ cũ để xóa.")

def main():
    """Main function to run the cleanup script."""
    setup_logging(log_level=config.LOG_LEVEL)
    logger.info("Bắt đầu kịch bản dọn dẹp dữ liệu...")
    
    cleanup_old_files(
        data_dir=config.STORAGE_BASE_DIR,
        days_to_keep=config.STORAGE_CLEANUP_DAYS
    )
    
    logger.info("Kịch bản dọn dẹp dữ liệu đã kết thúc.")

if __name__ == "__main__":
    main() 