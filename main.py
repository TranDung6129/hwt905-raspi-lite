import logging
import time
import signal
import sys
import threading
import argparse
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
    logger.info(f"Nhận tín hiệu dừng {signum}. Đang thoát ứng dụng...")
    _running_flag.clear()

def cleanup_threads(reader_thread, decoder_thread, storage_manager, ser_instance, session_flag):
    """Dọn dẹp và dừng tất cả threads và kết nối"""
    logger = logging.getLogger(__name__)
    logger.info("Bắt đầu dọn dẹp threads và kết nối...")
    
    # Dừng flag phiên để báo hiệu threads dừng
    session_flag.clear()
    
    # Đợi threads dừng với timeout
    if reader_thread and reader_thread.is_alive():
        reader_thread.join(timeout=3)
        if reader_thread.is_alive():
            logger.warning("Reader thread chưa dừng sau 3 giây")
    
    if decoder_thread and decoder_thread.is_alive():
        decoder_thread.join(timeout=3)
        if decoder_thread.is_alive():
            logger.warning("Decoder thread chưa dừng sau 3 giây")
    
    # Đóng storage và serial connection
    if storage_manager:
        storage_manager.close_current_file()
    
    if ser_instance and ser_instance.is_open:
        ser_instance.close()
        logger.info("Đã đóng kết nối serial")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='HWT905 Sensor Data Collection')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with verbose logging')
    args = parser.parse_args()

    try:
        # 1. Thiết lập hệ thống ghi log
        log_level = 'DEBUG' if args.debug else config.LOG_LEVEL
        setup_logging(log_level=log_level)
        logger = logging.getLogger(__name__)
        logger.info("Ứng dụng cảm biến HWT905 đang khởi động...")
        
        if args.debug:
            logger.info("Debug mode enabled - sẽ hiển thị thông tin chi tiết về gói tin")

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
            debug=args.debug
        )
        
        # Vòng lặp chính với kết nối lại hoàn toàn
        while _running_flag.is_set():
            # Initialize variables for this connection attempt
            ser_instance = None
            storage_manager = None
            reader_thread = None
            decoder_thread = None
            session_flag = threading.Event()  # Flag riêng cho phiên kết nối này
            
            try:
                # Thử kết nối với cảm biến
                logger.info("Đang thử thiết lập kết nối với cảm biến...")
                ser_instance = connection_manager.establish_connection()
                
                if not ser_instance or not ser_instance.is_open:
                    logger.warning("Không thể kết nối tới cảm biến, thử lại sau 5 giây...")
                    time.sleep(5)
                    continue
                
                logger.info("Cảm biến đã được kết nối thành công và sẵn sàng đọc dữ liệu.")

                # 4. Khởi tạo các thành phần cốt lõi cho kết nối này
                data_decoder = HWT905DataDecoder(
                    debug=args.debug, 
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

                # 5. Thiết lập pipeline mới với session flag
                raw_data_queue = Queue(maxsize=8192)
                session_flag.set()  # Bật flag cho phiên này

                reader_thread = SerialReaderThread(
                    data_decoder=data_decoder, 
                    raw_data_queue=raw_data_queue, 
                    running_flag=session_flag,  # Dùng session flag thay vì main flag
                    connection_manager=connection_manager
                )
                
                decoder_thread = DecoderThread(
                    data_decoder=data_decoder,
                    raw_data_queue=raw_data_queue,
                    running_flag=session_flag,  # Dùng session flag thay vì main flag
                    storage_manager=storage_manager,
                    reader_thread=reader_thread
                )

                # 6. Chạy các luồng
                logger.info("Bắt đầu các luồng đọc và giải mã...")
                reader_thread.start()
                decoder_thread.start()
                
                notifier.notify("READY=1")
                logger.info("Ứng dụng đã sẵn sàng.")

                # 7. Vòng lặp giám sát cho kết nối hiện tại
                while _running_flag.is_set():
                    # Kiểm tra trạng thái threads
                    if not reader_thread.is_alive():
                        logger.warning("Luồng đọc (ReaderThread) đã dừng - có thể mất kết nối")
                        break
                    
                    if not decoder_thread.is_alive():
                        logger.warning("Luồng giải mã (DecoderThread) đã dừng - có thể có lỗi")
                        break

                    notifier.notify("WATCHDOG=1")
                    time.sleep(2)
                
                # Nếu ra khỏi vòng lặp giám sát mà _running_flag vẫn set
                # có nghĩa là mất kết nối, không phải thoát ứng dụng
                if _running_flag.is_set():
                    logger.warning("Phát hiện mất kết nối. Dọn dẹp và chuẩn bị kết nối lại...")
                    cleanup_threads(reader_thread, decoder_thread, storage_manager, ser_instance, session_flag)
                    
                    # Chờ một chút trước khi thử kết nối lại
                    logger.info("Chờ 3 giây trước khi thử kết nối lại...")
                    time.sleep(3)
                    continue
                else:
                    # _running_flag đã bị clear, nghĩa là cần thoát ứng dụng
                    logger.info("Nhận lệnh thoát ứng dụng")
                    cleanup_threads(reader_thread, decoder_thread, storage_manager, ser_instance, session_flag)
                    break
                    
            except Exception as e:
                logger.error(f"Lỗi trong kết nối hiện tại: {e}", exc_info=True)
                cleanup_threads(reader_thread, decoder_thread, storage_manager, ser_instance, session_flag)
                
                if _running_flag.is_set():
                    logger.info("Chờ 5 giây trước khi thử kết nối lại sau lỗi...")
                    time.sleep(5)
                    continue
                else:
                    break
            
    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng không mong muốn trong hàm main: {e}", exc_info=True)
    finally:
        logger.info("Ứng dụng đã dừng hoàn toàn.")

if __name__ == "__main__":
    main()