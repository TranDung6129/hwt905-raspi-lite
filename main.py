import logging
import time
import json
import threading
import signal
import sys
from queue import Queue
import serial
from typing import Optional

# Import các module và lớp cần thiết
from src.utils.common import load_config
from src.utils.logger_setup import setup_logging
from src.core.connection_manager import SensorConnectionManager
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.processing.data_processor import SensorDataProcessor
from src.storage.storage_manager import StorageManager
from src.core.async_data_manager import SerialReaderThread, DecoderThread, ProcessorThread, MqttPublisherThread
from src.sensors.hwt905_constants import (
    BAUD_RATE_9600, RATE_OUTPUT_200HZ, RATE_OUTPUT_100HZ, RATE_OUTPUT_50HZ, RATE_OUTPUT_10HZ,
    RSW_ACC_BIT, RSW_GYRO_BIT, RSW_ANGLE_BIT, RSW_MAG_BIT,
    RSW_TIME_BIT, RSW_PRESSURE_HEIGHT_BIT, RSW_GPS_LON_LAT_BIT,
    RSW_GPS_SPEED_BIT, RSW_QUATERNION_BIT, RSW_GPS_ACCURACY_BIT, RSW_PORT_STATUS_BIT
)


# Cờ để điều khiển vòng lặp chính
_running_flag = threading.Event()

def signal_handler(signum, frame):
    """Xử lý tín hiệu dừng một cách graceful"""
    logger = logging.getLogger(__name__)
    logger.info(f"Nhận tín hiệu {signum}. Đang dừng ứng dụng...")
    _running_flag.clear()
    sys.exit(0)


def main():
    # 1. Tải cấu hình ứng dụng
    try:
        app_config = load_config("config/app_config.json")
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        print(f"FATAL ERROR: Không thể tải file cấu hình app_config.json: {e}")
        exit(1)

    # 2. Thiết lập hệ thống ghi log
    log_config = app_config.get("logging", {})
    log_file_path = log_config.get("log_file_path", "logs/application.log")
    log_level = log_config.get("log_level", "INFO")
    max_bytes = log_config.get("max_bytes", 10485760)
    backup_count = log_config.get("backup_count", 5)

    setup_logging(log_file_path, log_level, max_bytes, backup_count)
    logger = logging.getLogger(__name__)

    logger.info("Ứng dụng Backend IMU đã khởi động.")
    logger.debug(f"Đã tải cấu hình: {app_config}")

    # Thiết lập signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    _running_flag.set()

    # 3. Đọc cấu hình điều khiển quy trình
    process_control_config = app_config.get("process_control", {})
    decoding_enabled = process_control_config.get("decoding", True)
    processing_enabled = process_control_config.get("processing", True)
    mqtt_sending_enabled = process_control_config.get("mqtt_sending", True)
    
    logger.info(f"Cấu hình quy trình: Decoding={decoding_enabled}, Processing={processing_enabled}, MQTT Sending={mqtt_sending_enabled}")

    # 4. Quản lý kết nối và cấu hình cảm biến
    sensor_config = app_config["sensor"]
    connection_manager = SensorConnectionManager(
        sensor_config=sensor_config,
        debug=(logger.level <= logging.DEBUG)
    )
    
    ser_instance: Optional[serial.Serial] = None
    
    # Vòng lặp để đảm bảo kết nối đúng
    while _running_flag.is_set():
        if ser_instance is None or not ser_instance.is_open:
            ser_instance = connection_manager.establish_connection()
            if not ser_instance:
                # establish_connection đã là vòng lặp vô hạn, nên trường hợp này chỉ xảy ra nếu app dừng
                logger.info("Quá trình kết nối bị dừng do cờ _running_flag được xóa.")
                break 

        if not connection_manager.ensure_correct_config():
            # Baudrate đã được thay đổi, cần kết nối lại
            logger.info("Baudrate của cảm biến đã được thay đổi. Đang kết nối lại...")
            ser_instance = None # Đặt lại để vòng lặp thực hiện kết nối lại
            continue

        # Kết nối đã ổn và baudrate đã đúng. Sẵn sàng để chạy pipeline
        # LƯUÝ: Không cần cấu hình lại cảm biến vì:
        # 1. HWT905 lưu cấu hình vĩnh viễn (persist qua power cycle)
        # 2. Connection manager đã verify baudrate và connection thành công
        # 3. Cấu hình lại mỗi lần khởi động gây chậm startup và có thể confict
        # 4. Nếu cần thay đổi config, sử dụng tool riêng biệt
        logger.info("Cảm biến đã được kết nối thành công và sẵn sàng đọc dữ liệu.")
        break # Thoát khỏi vòng lặp setup
            
    if not _running_flag.is_set():
        logger.warning("Dừng ứng dụng trong quá trình khởi tạo cảm biến.")
        return

    # Khởi tạo DataDecoder với instance serial đã kết nối
    data_decoder = HWT905DataDecoder(debug=(logger.level <= logging.DEBUG), ser_instance=ser_instance)
    
    target_output_rate = sensor_config["default_output_rate_hz"]
    app_config["processing"]["dt_sensor_actual"] = 1.0 / target_output_rate

    # 5. Khởi tạo các thành phần dựa trên cấu hình
    storage_config = app_config.get("data_storage", {"enabled": False})
    
    decoded_storage_manager: Optional[StorageManager] = None
    if decoding_enabled and storage_config.get("enabled", False):
        logger.info("Khởi tạo StorageManager cho dữ liệu DECODED.")
        decoded_storage_manager = StorageManager(
            storage_config,
            data_type="decoded",
            fields_to_write=['acc_x', 'acc_y', 'acc_z']
        )

    sensor_data_processor: Optional[SensorDataProcessor] = None
    processed_storage_manager: Optional[StorageManager] = None
    if processing_enabled:
        logger.info("Khởi tạo SensorDataProcessor.")
        processing_config = app_config["processing"]
        sensor_data_processor = SensorDataProcessor(
            dt_sensor=processing_config["dt_sensor_actual"],
            gravity_g=processing_config["gravity_g"],
            acc_filter_type=processing_config.get("acc_filter_type"),
            acc_filter_param=processing_config.get("acc_filter_param"),
            rls_sample_frame_size=processing_config["rls_sample_frame_size"],
            rls_calc_frame_multiplier=processing_config["rls_calc_frame_multiplier"],
            rls_filter_q=processing_config["rls_filter_q"],
            fft_n_points=processing_config["fft_n_points"],
            fft_min_freq_hz=processing_config["fft_min_freq_hz"],
            fft_max_freq_hz=processing_config["fft_max_freq_hz"]
        )
        if storage_config.get("enabled", False):
            logger.info("Khởi tạo StorageManager cho dữ liệu PROCESSED.")
            
            # Chỉ định các cột cần ghi cho file processed_data.csv
            processed_fields_to_write = [
                'vel_x', 'vel_y', 'vel_z',
                'disp_x', 'disp_y', 'disp_z',
                'dominant_freq_x', 'dominant_freq_y', 'dominant_freq_z'
            ]
            
            processed_storage_manager = StorageManager(
                storage_config,
                data_type="processed",
                fields_to_write=processed_fields_to_write
            )

    # 6. Thiết lập pipeline bất đồng bộ 3 (hoặc 4) luồng
    raw_data_queue = Queue(maxsize=8192)
    decoded_data_queue = Queue(maxsize=8192) if processing_enabled else None
    mqtt_queue = Queue(maxsize=8192) if mqtt_sending_enabled else None

    # Luồng 1: Đọc từ Serial
    reader_thread = SerialReaderThread(data_decoder, raw_data_queue, _running_flag)
    
    # Luồng 2: Giải mã và lưu dữ liệu giải mã
    decoder_thread = DecoderThread(
        data_decoder=data_decoder,
        raw_data_queue=raw_data_queue,
        decoded_data_queue=decoded_data_queue,
        running_flag=_running_flag,
        decoded_storage_manager=decoded_storage_manager
    )

    # Luồng 3: Xử lý và lưu dữ liệu xử lý (chỉ khởi tạo nếu processing được bật)
    processor_thread = None
    if processing_enabled and sensor_data_processor:
        processor_thread = ProcessorThread(
            decoded_data_queue=decoded_data_queue,
            running_flag=_running_flag,
            sensor_data_processor=sensor_data_processor,
            processed_storage_manager=processed_storage_manager,
            mqtt_queue=mqtt_queue
        )

    # Luồng 4: Gửi dữ liệu qua MQTT (chỉ khởi tạo nếu được bật)
    mqtt_publisher_thread = None
    if mqtt_sending_enabled and mqtt_queue:
        mqtt_publisher_thread = MqttPublisherThread(
            mqtt_queue=mqtt_queue,
            running_flag=_running_flag
        )

    # 7. Chạy các luồng
    logger.info("Bắt đầu các luồng đọc, giải mã và xử lý bất đồng bộ...")
    reader_thread.start()
    decoder_thread.start()
    if processor_thread:
        processor_thread.start()
    if mqtt_publisher_thread:
        mqtt_publisher_thread.start()

    try:
        # Vòng lặp chính với auto-reconnection
        while True:
            # Vòng lặp giám sát kết nối
            connection_lost = False
            while _running_flag.is_set():
                # Kiểm tra xem có mất kết nối không
                if reader_thread.is_connection_lost() or data_decoder.ser is None or not data_decoder.ser.is_open:
                    logger.warning("Phát hiện mất kết nối với cảm biến!")
                    connection_lost = True
                    break
                time.sleep(1)
            
            # Nếu mất kết nối, thực hiện reconnection
            if connection_lost:
                logger.info("🔄 Bắt đầu quá trình kết nối lại...")
                
                # Reset connection lost flag
                reader_thread.reset_connection_lost()
                
                # Dừng các luồng hiện tại
                logger.info("Đang dừng các luồng để chuẩn bị kết nối lại...")
                _running_flag.clear()
                
                # Đợi các luồng kết thúc với timeout
                reader_thread.join(timeout=5)
                decoder_thread.join(timeout=5)
                if processor_thread and processor_thread.is_alive():
                    processor_thread.join(timeout=5)
                if mqtt_publisher_thread and mqtt_publisher_thread.is_alive():
                    mqtt_publisher_thread.join(timeout=5)
                
                # Reset các queue
                logger.info("Đang làm trống hàng đợi...")
                while not raw_data_queue.empty():
                    try:
                        raw_data_queue.get_nowait()
                    except:
                        break
                
                if decoded_data_queue:
                    while not decoded_data_queue.empty():
                        try:
                            decoded_data_queue.get_nowait()
                        except:
                            break
                
                if mqtt_queue:
                    while not mqtt_queue.empty():
                        try:
                            mqtt_queue.get_nowait()
                        except:
                            break
                
                # Đóng kết nối cũ
                connection_manager.close_connection()
                
                # Reset running flag và thử kết nối lại
                _running_flag.set()
                logger.info("Đang thử kết nối lại với cảm biến...")
                
                # Thiết lập lại kết nối
                ser_instance = None
                reconnect_attempts = 0
                max_attempts = 10  # Giới hạn số lần thử để tránh vòng lặp vô hạn
                
                while _running_flag.is_set() and reconnect_attempts < max_attempts:
                    reconnect_attempts += 1
                    logger.info(f"Lần thử kết nối lại: {reconnect_attempts}/{max_attempts}")
                    
                    if ser_instance is None or not ser_instance.is_open:
                        ser_instance = connection_manager.establish_connection()
                        if not ser_instance:
                            logger.warning("Kết nối thất bại, thử lại sau 5 giây...")
                            time.sleep(5)
                            continue

                    if not connection_manager.ensure_correct_config():
                        logger.info("Baudrate của cảm biến đã được thay đổi. Đang kết nối lại...")
                        ser_instance = None
                        continue
                    
                    logger.info("✅ Cảm biến đã được kết nối lại thành công!")
                    break
                
                if not _running_flag.is_set():
                    logger.info("Quá trình reconnection bị dừng do _running_flag được clear.")
                    break
                    
                if reconnect_attempts >= max_attempts:
                    logger.error(f"❌ Không thể kết nối lại sau {max_attempts} lần thử. Dừng ứng dụng.")
                    break
                    
                # Cập nhật data_decoder với kết nối mới
                data_decoder.set_ser_instance(ser_instance)
                
                # Tạo lại các luồng
                logger.info("Đang tạo lại các luồng...")
                reader_thread = SerialReaderThread(data_decoder, raw_data_queue, _running_flag)
                
                decoder_thread = DecoderThread(
                    data_decoder=data_decoder,
                    raw_data_queue=raw_data_queue,
                    decoded_data_queue=decoded_data_queue,
                    running_flag=_running_flag,
                    decoded_storage_manager=decoded_storage_manager
                )
                
                processor_thread = None
                if processing_enabled and sensor_data_processor:
                    processor_thread = ProcessorThread(
                        decoded_data_queue=decoded_data_queue,
                        running_flag=_running_flag,
                        sensor_data_processor=sensor_data_processor,
                        processed_storage_manager=processed_storage_manager,
                        mqtt_queue=mqtt_queue
                    )
                
                mqtt_publisher_thread = None
                if mqtt_sending_enabled and mqtt_queue:
                    mqtt_publisher_thread = MqttPublisherThread(
                        mqtt_queue=mqtt_queue,
                        running_flag=_running_flag
                    )
                
                # Khởi động lại các luồng
                logger.info("Đang khởi động lại các luồng...")
                reader_thread.start()
                decoder_thread.start()
                if processor_thread:
                    processor_thread.start()
                if mqtt_publisher_thread:
                    mqtt_publisher_thread.start()
                
                logger.info("✅ Đã kết nối lại thành công và khởi động lại hệ thống!")
                continue
            else:
                # Thoát bình thường (không phải do mất kết nối)
                break 
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu dừng (Ctrl+C). Đang dừng ứng dụng...")
    except Exception as e:
        logger.error(f"Lỗi không mong muốn trong vòng lặp chính: {e}")
    finally:
        # Đảm bảo _running_flag được clear trong mọi trường hợp
        _running_flag.clear()

    # 8. Đợi các luồng kết thúc
    logger.info("Đang đợi các luồng kết thúc...")
    reader_thread.join()
    decoder_thread.join()
    if processor_thread:
        processor_thread.join()
    if mqtt_publisher_thread:
        mqtt_publisher_thread.join()
    
    # Đợi cho queue được xử lý hết
    raw_data_queue.join()
    if decoded_data_queue:
        decoded_data_queue.join()
    if mqtt_queue:
        mqtt_queue.join()
    logger.info("Hàng đợi đã được xử lý xong.")

    # 9. Dọn dẹp
    logger.info("Đang dọn dẹp tài nguyên...")
    if connection_manager:
        connection_manager.close_connection()
    if decoded_storage_manager:
        decoded_storage_manager.close()
    if processed_storage_manager:
        processed_storage_manager.close()
    logger.info("Ứng dụng Backend IMU đã dừng.")


if __name__ == '__main__':
    main()