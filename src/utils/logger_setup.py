import logging
import logging.handlers
from pathlib import Path
from src.utils.common import ensure_directory_exists # Import hàm tiện ích

def setup_logging(log_file_path: str, log_level: str, max_bytes: int = 10485760, backup_count: int = 5):
    """
    Thiết lập cấu hình logging cho ứng dụng.
    Log sẽ được ghi ra console và vào một file.

    Args:
        log_file_path (str): Đường dẫn đến file log.
        log_level (str): Cấp độ log (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR').
        max_bytes (int): Kích thước tối đa của file log trước khi nó được xoay vòng (bytes).
        backup_count (int): Số lượng file log cũ được giữ lại.
    """
    log_directory = Path(log_file_path).parent
    ensure_directory_exists(str(log_directory))

    # Lấy logger gốc của ứng dụng 
    logger = logging.getLogger()
    logger.setLevel(logging.getLevelName(log_level.upper()))

    # Định dạng của log message
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Xóa tất cả các handler hiện có để tránh nhân đôi log khi hàm được gọi nhiều lần (ví dụ trong test)
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # Handler cho console (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler cho file log (xoay vòng khi đạt kích thước)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info(f"Logging đã được thiết lập thành công. Cấp độ: {log_level.upper()}, File: {log_file_path}")

def setup_logger(log_level: int = logging.INFO, name: str = None):
    """
    Thiết lập logger đơn giản cho service.
    
    Args:
        log_level: Cấp độ log (logging.INFO, logging.DEBUG, etc.)
        name: Tên logger (None để sử dụng root logger)
    """
    # Tạo hoặc lấy logger
    logger = logging.getLogger(name)
    
    # Xóa handlers cũ nếu có
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # Thiết lập level
    logger.setLevel(log_level)
    
    # Tạo formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Tạo console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Thêm handler
    logger.addHandler(console_handler)
    
    return logger