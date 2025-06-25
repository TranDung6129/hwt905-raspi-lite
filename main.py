import logging
import time
import signal
import sys
import threading
from queue import Queue
import serial
import sdnotify

# Import các module và lớp đã được đơn giản hóa
from src import config
from src.utils.logger_setup import setup_logging
from src.core.connection_manager import SensorConnectionManager
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.storage.storage_manager import StorageManager
from src.core.async_data_manager import SerialReaderThread, DecoderThread

# Cờ để điều khiển vòng lặp chính
_running_flag = threading.Event()

def signal_handler(signum, frame):
    """Xử lý tín hiệu dừng một cách graceful. Chỉ set cờ, không exit."""
    logger = logging.getLogger(__name__)
    logger.info(f"Nhận tín hiệu {signum}. Đang yêu cầu dừng ứng dụng...")
    _running_flag.clear()

def main():
    # Initialize variables to None before the try block
    connection_manager = None
    ser_instance = None
    storage_manager = None
    reader_thread = None
    decoder_thread = None

    try:
        # 1. Thiết lập hệ thống ghi log
        setup_logging(log_level=config.LOG_LEVEL)
        logger = logging.getLogger(__name__)
        logger.info("Ứng dụng cảm biến HWT905 đang khởi động...")

        # Tích hợp Systemd Notifier
        notifier = sdnotify.SystemdNotifier()

        # 2. Thiết lập signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        _running_flag.set()

        # 3. Quản lý kết nối cảm biến
        connection_manager = SensorConnectionManager(
            port=config.SENSOR_UART_PORT,
            baudrate=config.SENSOR_BAUD_RATE,
            debug=(logger.level <= logging.DEBUG)
        )
        
        while _running_flag.is_set():
            ser_instance = connection_manager.establish_connection()
            if ser_instance and ser_instance.is_open:
                logger.info("Cảm biến đã được kết nối thành công và sẵn sàng đọc dữ liệu.")
                break
            logger.warning("Không thể kết nối tới cảm biến, thử lại sau 5 giây...")
            time.sleep(5)
                
        if not _running_flag.is_set():
            logger.warning("Dừng ứng dụng trong quá trình khởi tạo cảm biến.")
            return

        # 4. Khởi tạo các thành phần cốt lõi
        data_decoder = HWT905DataDecoder(
            debug=(logger.level <= logging.DEBUG), 
            ser_instance=ser_instance
        )
        
        storage_manager = StorageManager(
            base_dir=config.STORAGE_BASE_DIR,
            file_rotation_hours=config.STORAGE_FILE_ROTATION_HOURS,
            fields_to_write=[
                'timestamp', 
                'angle_roll', 'angle_pitch', 'angle_yaw',
                'temperature'
            ]
        )

        # 5. Thiết lập pipeline
        raw_data_queue = Queue(maxsize=8192)

        reader_thread = SerialReaderThread(
            data_decoder=data_decoder, 
            raw_data_queue=raw_data_queue, 
            running_flag=_running_flag
        )
        
        decoder_thread = DecoderThread(
            data_decoder=data_decoder,
            raw_data_queue=raw_data_queue,
            running_flag=_running_flag,
            storage_manager=storage_manager
        )

        # 6. Chạy các luồng
        logger.info("Bắt đầu các luồng đọc và giải mã...")
        reader_thread.start()
        decoder_thread.start()
        
        notifier.notify("READY=1")
        logger.info("Ứng dụng đã sẵn sàng.")

        # 7. Vòng lặp giám sát
        while _running_flag.is_set():
            if reader_thread.read_error.is_set():
                logger.error("Phát hiện lỗi nghiêm trọng từ luồng đọc. Dừng ứng dụng để systemd khởi động lại.")
                break

            if not reader_thread.is_alive():
                logger.error("Luồng đọc (ReaderThread) đã dừng đột ngột. Dừng ứng dụng.")
                break
            
            if not decoder_thread.is_alive():
                logger.error("Luồng giải mã (DecoderThread) đã dừng đột ngột. Dừng ứng dụng.")
                break

            notifier.notify("WATCHDOG=1")
            time.sleep(2)
            
    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng không mong muốn trong hàm main: {e}", exc_info=True)
    finally:
        logger.info("Bắt đầu quá trình dừng ứng dụng...")
        _running_flag.clear()

        if reader_thread and reader_thread.is_alive():
            reader_thread.join(timeout=5)
        if decoder_thread and decoder_thread.is_alive():
            decoder_thread.join(timeout=5)

        if storage_manager:
            storage_manager.close_current_file()
        if ser_instance and ser_instance.is_open:
            ser_instance.close()
        
        logger.info("Ứng dụng đã dừng hoàn toàn.")
        # Systemd sẽ thấy exit code khác 0 (do break/exception) và khởi động lại
        # nếu service được cấu hình với Restart=always.
        # Nếu thoát do signal, exit code sẽ do HĐH quyết định.
        # Chúng ta không cần sys.exit() ở đây nữa.

if __name__ == "__main__":
    main()