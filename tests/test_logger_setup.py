import pytest
import logging
import os
import shutil
from pathlib import Path
import re # Để kiểm tra nội dung log

# Thêm đường dẫn src vào PYTHONPATH để có thể import các module từ src
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.logger_setup import setup_logging

# --- Fixtures ---
@pytest.fixture
def clean_log_env(tmp_path):
    """
    Fixture để tạo môi trường log sạch cho mỗi bài kiểm thử.
    Nó trả về đường dẫn file log tạm thời.
    """
    log_dir = tmp_path / "test_logs"
    log_file = log_dir / "test_application.log"
    
    # Đảm bảo không có handler nào còn sót lại từ các test trước
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.setLevel(logging.NOTSET) # Reset level
    
    yield str(log_file) # Cung cấp đường dẫn file log
    
    # Dọn dẹp sau khi test hoàn tất
    if log_dir.exists():
        shutil.rmtree(log_dir)

# --- Test cases cho setup_logging ---
def test_setup_logging_creates_file_and_logs(clean_log_env):
    """Kiểm tra setup_logging tạo file và ghi log đúng cách."""
    log_file_path = clean_log_env
    
    setup_logging(log_file_path, "DEBUG")
    
    logger = logging.getLogger() # Lấy root logger đã được setup
    logger.debug("This is a DEBUG message.")
    logger.info("This is an INFO message.")
    logger.warning("This is a WARNING message.")
    logger.error("This is an ERROR message.")
    
    # Đảm bảo log được flush vào file trước khi đọc
    for handler in logger.handlers:
        handler.flush()
    
    # Đọc nội dung file log
    log_content = Path(log_file_path).read_text(encoding='utf-8')
    
    assert Path(log_file_path).exists()
    assert "This is a DEBUG message." in log_content
    assert "This is an INFO message." in log_content
    assert "This is a WARNING message." in log_content
    assert "This is an ERROR message." in log_content
    assert "DEBUG" in log_content # Kiểm tra cấp độ DEBUG có trong log

def test_setup_logging_level_filtering(clean_log_env):
    """Kiểm tra bộ lọc cấp độ log hoạt động chính xác."""
    log_file_path = clean_log_env
    
    setup_logging(log_file_path, "INFO") # Chỉ cho phép INFO trở lên
    
    logger = logging.getLogger()
    logger.debug("This DEBUG message should NOT appear.")
    logger.info("This INFO message SHOULD appear.")
    
    for handler in logger.handlers:
        handler.flush()
    
    log_content = Path(log_file_path).read_text(encoding='utf-8')
    
    assert "This DEBUG message should NOT appear." not in log_content
    assert "This INFO message SHOULD appear." in log_content

def test_setup_logging_rotation(clean_log_env):
    """
    Kiểm tra cơ chế xoay vòng file log.
    Sẽ cần ghi nhiều dữ liệu để kích hoạt.
    """
    log_file_path = clean_log_env
    
    # Thiết lập kích thước file rất nhỏ để dễ dàng kích hoạt xoay vòng
    setup_logging(log_file_path, "DEBUG", max_bytes=100, backup_count=2)
    
    logger = logging.getLogger()
    
    # Ghi đủ log để kích hoạt xoay vòng
    for i in range(20): # Ghi 20 dòng, mỗi dòng đủ dài
        logger.info(f"Log message number {i:02d} {'x' * 50}.")
    
    # Đảm bảo log được flush
    for handler in logger.handlers:
        handler.flush()

    # Kiểm tra sự tồn tại của các file backup
    assert Path(log_file_path).exists() # File hiện tại
    assert Path(f"{log_file_path}.1").exists() # File backup đầu tiên

    # Kiểm tra nội dung của file hiện tại và file backup
    current_log_content = Path(log_file_path).read_text(encoding='utf-8')
    backup_log_content = Path(f"{log_file_path}.1").read_text(encoding='utf-8')

    # Kiểm tra xem message cuối cùng có trong file hiện tại không
    assert "Log message number 19" in current_log_content
    
    # Điều chỉnh kiểm tra: file backup phải chứa một message log hợp lệ (không nhất thiết phải là message đầu tiên)
    # Kiểm tra rằng backup file có định dạng log thích hợp (ngày tháng, cấp độ, v.v.)
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - root - INFO - Log message number \d+", backup_log_content)
    
    # Thử ghi thêm để tạo file backup thứ hai và kiểm tra xoay vòng đúng
    for i in range(20, 40):
        logger.info(f"New log message number {i:02d} {'y' * 50}.")
    
    for handler in logger.handlers:
        handler.flush()
        
    assert Path(f"{log_file_path}.1").exists() # Backup 1 vẫn tồn tại (hoặc đã chuyển)
    assert Path(f"{log_file_path}.2").exists() # Backup 2 đã được tạo
    
    # Do backup_count=1, file .2 sẽ trở thành .1 và file .1 cũ sẽ bị xóa hoặc là file .2 mới được tạo.
    # Logic kiểm tra này phức tạp hơn một chút vì tên file có thể thay đổi.
    # Mục tiêu chính là xác nhận các file backup đã được tạo.
    
    # Reset logger để không ảnh hưởng đến các test khác
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.setLevel(logging.NOTSET)