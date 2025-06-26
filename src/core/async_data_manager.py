# src/core/async_data_manager.py
import threading
import logging
import time
from queue import Queue, Empty
from typing import Optional
import numpy as np
import serial

from ..sensors.hwt905_data_decoder import HWT905DataDecoder
from ..storage.storage_manager import StorageManager
from ..sensors.hwt905_constants import PACKET_TYPE_ACC, PACKET_TYPE_ANGLE
from ..core.connection_manager import SensorConnectionManager
from .. import config

logger = logging.getLogger(__name__)

def convert_numpy_to_native(data):
    """
    Hàm đệ quy để chuyển đổi tất cả các giátrị numpy.ndarray hoặc numpy number
    trong một cấu trúc dữ liệu (dict, list) thành kiểu dữ liệu gốc của Python.
    """
    if isinstance(data, dict):
        return {k: convert_numpy_to_native(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_numpy_to_native(i) for i in data]
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif isinstance(data, (np.generic, np.number)):
        return data.item()
    return data

class SerialReaderThread(threading.Thread):
    """
    Luồng chuyên đọc dữ liệu thô từ cổng serial và đưa vào hàng đợi.
    """
    def __init__(self, data_decoder: HWT905DataDecoder, raw_data_queue: Queue, running_flag: threading.Event, connection_manager: SensorConnectionManager = None):
        super().__init__(daemon=True, name="SerialReaderThread")
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.running_flag = running_flag
        self.connection_manager = connection_manager
        self.raw_packet_count = 0
        self.last_log_time = time.time()

    def run(self):
        logger.info("Luồng đọc Serial đã bắt đầu.")
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while self.running_flag.is_set():
            try:
                raw_packet = self.data_decoder.read_raw_packet()
                if raw_packet:
                    self.raw_data_queue.put(raw_packet)
                    self.raw_packet_count += 1
                    consecutive_failures = 0  # Reset counter khi đọc thành công
                else:
                    # Nếu không có dữ liệu, ngủ một chút để tránh chiếm dụng CPU
                    time.sleep(0.001)

                current_time = time.time()
                if current_time - self.last_log_time >= 10.0:
                    rate = self.raw_packet_count / (current_time - self.last_log_time)
                    logger.info(f"Tốc độ đọc: {rate:.2f} packets/s. Queue size: {self.raw_data_queue.qsize()}")
                    self.raw_packet_count = 0
                    self.last_log_time = current_time

            except (serial.SerialException, Exception) as e:
                consecutive_failures += 1
                
                # Sử dụng connection_manager để xử lý lỗi
                if self.connection_manager:
                    need_reconnect = self.connection_manager.handle_serial_error(e, consecutive_failures, max_consecutive_failures)
                    
                    if need_reconnect:
                        logger.warning("Mất kết nối serial. Dừng luồng để main thực hiện kết nối lại...")
                        # Dừng luồng và để main xử lý việc kết nối lại
                        self.running_flag.clear()
                        break
                    else:
                        # Chỉ cần chờ 1 giây rồi thử lại
                        time.sleep(1)
                else:
                    # Fallback nếu không có connection_manager
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning("Quá nhiều lỗi liên tiếp. Dừng luồng...")
                        self.running_flag.clear()
                        break
                    time.sleep(1)
                    
        logger.info("Luồng đọc Serial đã dừng.")


class DecoderThread(threading.Thread):
    """
    Luồng chuyên lấy dữ liệu thô từ hàng đợi, giải mã và lưu trữ TẤT CẢ dữ liệu góc.
    """
    def __init__(self,
                 data_decoder: HWT905DataDecoder,
                 raw_data_queue: Queue,
                 running_flag: threading.Event,
                 storage_manager: StorageManager,
                 reader_thread: SerialReaderThread):
        super().__init__(daemon=True, name="DecoderThread")
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.running_flag = running_flag
        self.storage_manager = storage_manager
        self.reader_thread = reader_thread  # Reference để kiểm tra trạng thái
        
        self.decoded_packet_count = 0
        self.saved_packet_count = 0  # Số packet thực sự được lưu
        self.last_log_time = time.time()

    def run(self):
        logger.info("Luồng Giải mã & Lưu trữ đã bắt đầu (lưu TẤT CẢ dữ liệu góc).")
        
        while self.running_flag.is_set() or not self.raw_data_queue.empty():
            try:
                raw_packet = self.raw_data_queue.get(timeout=1)
                
                # 1. Giải mã gói tin
                packet_info = self.data_decoder.decode_raw_packet(raw_packet)

                if not packet_info or "error" in packet_info:
                    self.raw_data_queue.task_done()
                    continue
                
                self.decoded_packet_count += 1
                
                # 2. Chỉ xử lý dữ liệu góc (angle packet type 0x53)
                packet_type = packet_info.get("type")
                if packet_type == PACKET_TYPE_ANGLE and "angle_roll" in packet_info and "angle_pitch" in packet_info and "angle_yaw" in packet_info:
                    current_time = time.time()
                    
                    # 3. Lưu TẤT CẢ dữ liệu góc - không có rate limiting
                    data_to_store = {
                        "timestamp": packet_info.get("timestamp", current_time),
                        "angle_roll": packet_info.get("angle_roll"),
                        "angle_pitch": packet_info.get("angle_pitch"), 
                        "angle_yaw": packet_info.get("angle_yaw")
                    }
                    
                    # Thêm nhiệt độ nếu có
                    if "temperature" in packet_info:
                        data_to_store["temperature"] = packet_info.get("temperature")
                    
                    self.saved_packet_count += 1
                    
                    # Ghi vào file
                    self.storage_manager.write_data(data_to_store)

                self.raw_data_queue.task_done()

                # Ghi log định kỳ
                current_time = time.time()
                if current_time - self.last_log_time >= 10.0:
                    time_interval = current_time - self.last_log_time
                    decode_rate = self.decoded_packet_count / time_interval
                    save_rate = self.saved_packet_count / time_interval
                    q_info = f"Queue raw: {self.raw_data_queue.qsize()}"
                    efficiency = (self.saved_packet_count / self.decoded_packet_count * 100) if self.decoded_packet_count > 0 else 0
                    
                    logger.info(f"Decode: {decode_rate:.1f}Hz, Lưu góc: {save_rate:.1f}Hz, Hiệu suất: {efficiency:.1f}%. {q_info}")
                    self.decoded_packet_count = 0
                    self.saved_packet_count = 0
                    self.last_log_time = current_time

            except Empty:
                if not self.running_flag.is_set():
                    logger.info("Hàng đợi thô trống và cờ đã tắt, thoát luồng Decoder.")
                    break
                continue
                
            except Exception as e:
                logger.error(f"Lỗi trong luồng Decoder: {e}", exc_info=True)
                self.running_flag.clear()
                break
                
        logger.info("Luồng Giải mã & Lưu trữ đã dừng.")
        # Đóng file đang mở khi luồng dừng
        self.storage_manager.close_current_file()