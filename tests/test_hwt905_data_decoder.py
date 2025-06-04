
"""
Tests cho lớp HWT905DataDecoder, kết nối tới cảm biến thực tế.

Lưu ý: Tests này yêu cầu cảm biến HWT905 được kết nối với /dev/ttyUSB0
và đang hoạt động với baudrate 115200.

Để chạy test này:
pytest -v tests/test_hwt905_data_decoder.py
"""

import os
import sys
import time
import pytest
from typing import Dict, Any, List, Optional

# Thêm thư mục gốc vào đường dẫn để import các module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.sensors.hwt905_constants import (
    PACKET_TYPE_ACC, PACKET_TYPE_GYRO, PACKET_TYPE_ANGLE, 
    PACKET_TYPE_MAG, PACKET_TYPE_QUATERNION
)

# Cấu hình kết nối tới cảm biến thực
DEVICE_PORT = "/dev/ttyUSB0"
DEVICE_BAUDRATE = 115200
CONNECTION_TIMEOUT = 2.0  # thời gian chờ kết nối (giây)
READ_TIMEOUT = 0.1  # thời gian chờ đọc (giây)
SAMPLES_TO_COLLECT = 10  # số lượng mẫu để đọc

# Skip test nếu không có cảm biến kết nối
def is_sensor_connected():
    """Kiểm tra xem cảm biến có được kết nối không."""
    return os.path.exists(DEVICE_PORT)

@pytest.fixture
def decoder_instance():
    """Fixture để tạo và dọn dẹp một instance HWT905DataDecoder."""
    # Skip nếu không có cảm biến kết nối
    if not is_sensor_connected():
        pytest.skip(f"Cảm biến HWT905 không được kết nối ở {DEVICE_PORT}")
    
    # Tạo instance decoder
    decoder = HWT905DataDecoder(
        port=DEVICE_PORT,
        baudrate=DEVICE_BAUDRATE,
        timeout=READ_TIMEOUT,
        debug=True  # Bật debug để xem chi tiết log
    )
    
    # Kiểm tra kết nối thành công
    if not decoder.connect():
        pytest.skip(f"Không thể kết nối tới cảm biến ở {DEVICE_PORT} với baudrate {DEVICE_BAUDRATE}")
        
    # Chờ kết nối ổn định
    time.sleep(1)
        
    yield decoder  # Cung cấp instance cho test
    
    # Dọn dẹp sau khi test hoàn thành
    decoder.close()


@pytest.mark.skipif(not is_sensor_connected(), reason=f"Cảm biến HWT905 không được kết nối ở {DEVICE_PORT}")
class TestHWT905DataDecoder:
    """Kiểm tra chức năng của lớp HWT905DataDecoder với cảm biến thực."""
    
    def test_connection(self, decoder_instance):
        """Kiểm tra kết nối tới cảm biến."""
        assert decoder_instance.ser is not None
        assert decoder_instance.ser.is_open
        assert decoder_instance.port == DEVICE_PORT
        assert decoder_instance.baudrate == DEVICE_BAUDRATE
        
    def test_read_packets(self, decoder_instance):
        """Kiểm tra đọc các gói dữ liệu từ cảm biến."""
        packets_read = 0
        packet_types = set()
        
        # Thời gian bắt đầu đọc
        start_time = time.time()
        max_time = 5  # Thời gian tối đa để đọc (giây)
        
        # Đọc một số lượng gói tin hoặc cho đến khi hết thời gian
        while packets_read < SAMPLES_TO_COLLECT and (time.time() - start_time) < max_time:
            packet = decoder_instance.read_one_packet()
            
            # Nếu đọc được gói hợp lệ
            if packet is not None and "error" not in packet:
                packets_read += 1
                packet_types.add(packet["type"])
                
                # In thông tin gói tin để debug
                print(f"Packet {packets_read}: Type={packet['type_name']}")
        
        # Kiểm tra đã đọc được ít nhất một số gói tin
        assert packets_read > 0, f"Không thể đọc gói tin nào sau {max_time} giây"
        
        # Báo cáo các loại gói tin đã đọc được
        print(f"\nĐã đọc được {packets_read} gói tin thuộc {len(packet_types)} loại khác nhau")
        
    def test_decode_sensor_data(self, decoder_instance):
        """Kiểm tra giải mã dữ liệu từ các loại gói tin phổ biến."""
        # Dictionary để lưu trữ các loại gói tin đã nhận
        received_packets: Dict[int, Dict[str, Any]] = {}
        
        # Các loại gói tin mong đợi (các loại phổ biến nhất)
        expected_packet_types = [
            PACKET_TYPE_ACC,
            PACKET_TYPE_GYRO,
            PACKET_TYPE_ANGLE,
            PACKET_TYPE_MAG,
            PACKET_TYPE_QUATERNION
        ]
        
        # Thời gian bắt đầu đọc
        start_time = time.time()
        max_time = 10  # Thời gian tối đa để đọc (giây)
        
        # Đọc gói tin cho đến khi nhận đủ các loại cần thiết hoặc hết thời gian
        while len(received_packets) < len(expected_packet_types) and (time.time() - start_time) < max_time:
            packet = decoder_instance.read_one_packet()
            
            if packet is not None and "error" not in packet and packet["type"] in expected_packet_types:
                # Lưu trữ gói tin mới nhất cho mỗi loại
                received_packets[packet["type"]] = packet
                print(f"Đã nhận gói tin loại: {packet['type_name']}")
        
        # Kiểm tra kết quả thu được
        print(f"\nĐã nhận được {len(received_packets)}/{len(expected_packet_types)} loại gói tin mong đợi")
        
        # Kiểm tra các gói tin đã nhận
        self._validate_packet_data(received_packets)
    
    def _validate_packet_data(self, received_packets: Dict[int, Dict[str, Any]]):
        """Xác thực dữ liệu trong các gói tin đã nhận."""
        # Kiểm tra gói tin gia tốc (ACCELERATION)
        if PACKET_TYPE_ACC in received_packets:
            acc_packet = received_packets[PACKET_TYPE_ACC]
            assert "acc_x" in acc_packet
            assert "acc_y" in acc_packet
            assert "acc_z" in acc_packet
            assert "temperature" in acc_packet
            
            # Kiểm tra phạm vi giá trị hợp lý
            assert abs(acc_packet["acc_x"]) < 10  # ±10g là hợp lý cho HWT905
            assert abs(acc_packet["acc_y"]) < 10
            assert abs(acc_packet["acc_z"]) < 10
            assert -40 < acc_packet["temperature"] < 85  # phạm vi nhiệt độ hợp lý
            
            print(f"Gia tốc: x={acc_packet['acc_x']:.3f}g, y={acc_packet['acc_y']:.3f}g, z={acc_packet['acc_z']:.3f}g")
            print(f"Nhiệt độ: {acc_packet['temperature']:.1f}°C")
        
        # Kiểm tra gói tin góc (ANGLE)
        if PACKET_TYPE_ANGLE in received_packets:
            angle_packet = received_packets[PACKET_TYPE_ANGLE]
            assert "angle_roll" in angle_packet
            assert "angle_pitch" in angle_packet
            assert "angle_yaw" in angle_packet
            
            # Kiểm tra phạm vi giá trị hợp lý
            assert -180 <= angle_packet["angle_roll"] <= 180
            assert -180 <= angle_packet["angle_pitch"] <= 180
            assert -180 <= angle_packet["angle_yaw"] <= 180
            
            print(f"Góc: roll={angle_packet['angle_roll']:.2f}°, pitch={angle_packet['angle_pitch']:.2f}°, yaw={angle_packet['angle_yaw']:.2f}°")

        # Kiểm tra gói tin vận tốc góc (ANGULAR_VELOCITY)
        if PACKET_TYPE_GYRO in received_packets:
            gyro_packet = received_packets[PACKET_TYPE_GYRO]
            assert "gyro_x" in gyro_packet
            assert "gyro_y" in gyro_packet
            assert "gyro_z" in gyro_packet
            
            # Kiểm tra phạm vi giá trị hợp lý (phụ thuộc vào cấu hình của cảm biến)
            assert abs(gyro_packet["gyro_x"]) < 2000  # ±2000°/s là hợp lý
            assert abs(gyro_packet["gyro_y"]) < 2000
            assert abs(gyro_packet["gyro_z"]) < 2000
            
            print(f"Vận tốc góc: x={gyro_packet['gyro_x']:.2f}°/s, y={gyro_packet['gyro_y']:.2f}°/s, z={gyro_packet['gyro_z']:.2f}°/s")

    def test_continuous_reading(self, decoder_instance):
        """Kiểm tra đọc liên tục và tính toán tốc độ nhận dữ liệu."""
        packets = []
        start_time = time.time()
        duration = 3  # Thời gian đọc (giây)
        
        # Đọc trong khoảng thời gian định trước
        while time.time() - start_time < duration:
            packet = decoder_instance.read_one_packet()
            if packet is not None and "error" not in packet:
                packets.append(packet)
        
        # Tính toán tốc độ nhận dữ liệu
        total_time = time.time() - start_time
        packets_per_second = len(packets) / total_time if total_time > 0 else 0
        
        # Báo cáo kết quả
        print(f"\nĐã đọc {len(packets)} gói tin trong {total_time:.2f} giây")
        print(f"Tốc độ đọc: {packets_per_second:.1f} gói tin/giây")
        
        # Đếm số lượng mỗi loại gói tin nhận được
        packet_type_counts = {}
        for packet in packets:
            packet_type = packet.get("type_name", "UNKNOWN")
            if packet_type in packet_type_counts:
                packet_type_counts[packet_type] += 1
            else:
                packet_type_counts[packet_type] = 1
        
        # In phân phối loại gói tin
        print("\nPhân phối các loại gói tin:")
        for packet_type, count in packet_type_counts.items():
            print(f"  {packet_type}: {count} ({count/len(packets)*100:.1f}%)")
        
        # Kiểm tra đã nhận được ít nhất vài gói tin
        assert len(packets) > 0, "Không nhận được gói tin nào"


if __name__ == "__main__":
    # Kiểm tra xem cảm biến có được kết nối không
    if not is_sensor_connected():
        print(f"Cảm biến HWT905 không được kết nối ở {DEVICE_PORT}")
        sys.exit(1)
    
    print(f"Thử kết nối tới cảm biến HWT905 ở {DEVICE_PORT} với baudrate {DEVICE_BAUDRATE}...")
    
    # Tạo một instance decoder
    decoder = HWT905DataDecoder(
        port=DEVICE_PORT,
        baudrate=DEVICE_BAUDRATE,
        timeout=READ_TIMEOUT,
        debug=True
    )
    
    # Kết nối tới cảm biến
    if not decoder.connect():
        print(f"Không thể kết nối tới cảm biến ở {DEVICE_PORT}")
        sys.exit(1)
    
    print("Kết nối thành công!")
    
    try:
        # Đọc một số lượng gói tin để kiểm tra
        print("\nĐang đọc các gói tin từ cảm biến...")
        for i in range(30):  # Đọc 30 gói tin
            packet = decoder.read_one_packet()
            if packet is not None:
                if "error" in packet:
                    print(f"Lỗi: {packet['error']}")
                else:
                    print(f"Gói tin #{i+1}: {packet['type_name']} - ", end="")
                    if packet["type_name"] == "ACCELERATION":
                        print(f"x={packet['acc_x']:.3f}g, y={packet['acc_y']:.3f}g, z={packet['acc_z']:.3f}g")
                    elif packet["type_name"] == "ANGLE":
                        print(f"roll={packet['angle_roll']:.2f}°, pitch={packet['angle_pitch']:.2f}°, yaw={packet['angle_yaw']:.2f}°")
                    else:
                        print(f"(Kiểu dữ liệu: {packet['type']})")
            else:
                print(".", end="", flush=True)
            time.sleep(0.01)
        
    except KeyboardInterrupt:
        print("\nĐã ngừng đọc dữ liệu.")
    finally:
        # Đóng kết nối
        decoder.close()
        print("\nĐã đóng kết nối.")
