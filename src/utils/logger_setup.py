import logging
import sys

class ColoredFormatter(logging.Formatter):
    """Custom formatter với màu sắc cho các level log khác nhau"""
    
    # Mã màu ANSI
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan - toàn bộ dòng
        'INFO': '\033[32m',      # Green - chỉ level name
        'WARNING': '\033[33m',   # Yellow - toàn bộ dòng
        'ERROR': '\033[31m',     # Red - toàn bộ dòng
        'CRITICAL': '\033[35m'   # Magenta - toàn bộ dòng
    }
    RESET = '\033[0m'  # Reset màu

    def format(self, record):
        # Format message cơ bản
        log_message = super().format(record)
        
        # Thay đổi levelname thành format [LEVEL]
        bracketed_level = f"[{record.levelname}]"
        log_message = log_message.replace(record.levelname, bracketed_level)
        
        # Áp dụng màu sắc theo quy tắc
        color = self.COLORS.get(record.levelname, self.RESET)
        
        if record.levelname == 'INFO':
            # INFO: chỉ tô màu xanh lá cho [INFO]
            colored_message = log_message.replace(
                bracketed_level, 
                f"{color}{bracketed_level}{self.RESET}"
            )
        else:
            # Các level khác: tô màu toàn bộ dòng
            colored_message = f"{color}{log_message}{self.RESET}"
        
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