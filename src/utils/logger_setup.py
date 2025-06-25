import logging
import sys

class ColoredFormatter(logging.Formatter):
    """Custom formatter với màu sắc cho các level log khác nhau"""
    
    # Mã màu ANSI
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[37m',      # White  
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m'   # Magenta
    }
    RESET = '\033[0m'  # Reset màu

    def format(self, record):
        # Lấy màu cho level hiện tại
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Format message
        log_message = super().format(record)
        
        # Thêm màu vào level name
        colored_message = log_message.replace(
            record.levelname, 
            f"{color}{record.levelname}{self.RESET}"
        )
        
        return colored_message

def setup_logging(log_level: str):
    """
    Thiết lập cấu hình logging với màu sắc cho ứng dụng.
    Log sẽ chỉ được ghi ra console (stdout).

    Args:
        log_level (str): Cấp độ log (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR').
    """
    logger = logging.getLogger()
    
    # Xác định cấp độ log, mặc định là INFO nếu không hợp lệ
    level = logging.getLevelName(log_level.upper())
    if not isinstance(level, int):
        level = logging.INFO
        
    logger.setLevel(level)

    # Định dạng của log message
    formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Xóa tất cả các handler hiện có để tránh nhân đôi log
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # Handler cho console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"Logging đã được thiết lập. Cấp độ: {log_level.upper()}")