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
    def __init__(self, data_decoder: HWT905DataDecoder, raw_data_queue: Queue, running_flag: threading.Event):
        super().__init__(daemon=True, name="SerialReaderThread")
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.running_flag = running_flag
        self.raw_packet_count = 0
        self.last_log_time = time.time()
        self.read_error = threading.Event() # Cờ báo lỗi đọc nghiêm trọng

    def run(self):
        logger.info("Luồng đọc Serial đã bắt đầu.")
        while self.running_flag.is_set():
            try:
                raw_packet = self.data_decoder.read_raw_packet()
                if raw_packet:
                    self.raw_data_queue.put(raw_packet)
                    self.raw_packet_count += 1
                else:
                    # Nếu không có dữ liệu, có thể kết nối đã mất. Luồng chính sẽ xử lý.
                    # Ngủ một chút để tránh chiếm dụng CPU
                    time.sleep(0.001)

                current_time = time.time()
                if current_time - self.last_log_time >= 10.0:
                    rate = self.raw_packet_count / (current_time - self.last_log_time)
                    logger.info(f"[Reader] Tốc độ đọc: {rate:.2f} packets/s. Queue size: {self.raw_data_queue.qsize()}")
                    self.raw_packet_count = 0
                    self.last_log_time = current_time

            except serial.SerialException as se:
                logger.error(f"[Reader] Lỗi Serial trong luồng đọc: {se}. Báo hiệu và dừng luồng.", exc_info=True)
                self.read_error.set() # Báo hiệu lỗi
                break
            except Exception as e:
                logger.error(f"[Reader] Lỗi không mong muốn trong luồng đọc: {e}", exc_info=True)
                self.read_error.set() # Báo hiệu lỗi
                break
        logger.info("Luồng đọc Serial đã dừng.")


class DecoderThread(threading.Thread):
    """
    Luồng chuyên lấy dữ liệu thô từ hàng đợi, giải mã và lưu trữ chỉ dữ liệu góc với tần số tối đa 200Hz.
    """
    def __init__(self,
                 data_decoder: HWT905DataDecoder,
                 raw_data_queue: Queue,
                 running_flag: threading.Event,
                 storage_manager: StorageManager):
        super().__init__(daemon=True, name="DecoderThread")
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.running_flag = running_flag
        self.storage_manager = storage_manager
        
        self.decoded_packet_count = 0
        self.saved_packet_count = 0  # Số packet thực sự được lưu
        self.skipped_packet_count = 0  # Số packet bị bỏ qua do rate limiting
        self.last_log_time = time.time()
        self.last_save_time = 0  # Thời gian lưu packet cuối cùng
        
        # Lấy rate limiting từ config
        self.target_rate_hz = config.DATA_COLLECTION_RATE_HZ
        self.save_interval = 1.0 / self.target_rate_hz if self.target_rate_hz > 0 else 0  # Nếu = 0 thì disable rate limiting

    def run(self):
        rate_info = f"tối đa {self.target_rate_hz}Hz" if self.target_rate_hz > 0 else "không giới hạn tần số"
        logger.info(f"Luồng Giải mã & Lưu trữ đã bắt đầu (chỉ lưu dữ liệu góc, {rate_info}).")
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
                    
                    # 3. Kiểm tra rate limiting
                    should_save = (self.target_rate_hz == 0) or (current_time - self.last_save_time >= self.save_interval)
                    if should_save:
                        # Chuẩn bị dữ liệu để lưu
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
                        self.last_save_time = current_time
                        
                        # Ghi vào file
                        self.storage_manager.write_data(data_to_store)
                    else:
                        # Bỏ qua packet này do rate limiting
                        self.skipped_packet_count += 1

                self.raw_data_queue.task_done()

                # Ghi log định kỳ
                current_time = time.time()
                if current_time - self.last_log_time >= 10.0:
                    time_interval = current_time - self.last_log_time
                    decode_rate = self.decoded_packet_count / time_interval
                    save_rate = self.saved_packet_count / time_interval
                    skip_rate = self.skipped_packet_count / time_interval
                    q_info = f"Queue raw: {self.raw_data_queue.qsize()}"
                    efficiency = (self.saved_packet_count / self.decoded_packet_count * 100) if self.decoded_packet_count > 0 else 0
                    logger.info(f"Decode: {decode_rate:.1f}Hz, Lưu góc: {save_rate:.1f}Hz, Bỏ qua: {skip_rate:.1f}Hz, Hiệu suất: {efficiency:.1f}%. {q_info}")
                    self.decoded_packet_count = 0
                    self.saved_packet_count = 0
                    self.skipped_packet_count = 0
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