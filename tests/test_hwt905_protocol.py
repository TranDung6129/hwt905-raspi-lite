import pytest
import logging
import os
import sys
from pathlib import Path

# Thêm đường dẫn src vào PYTHONPATH để có thể import các module từ src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from sensors.hwt905_protocol import calculate_checksum, create_write_command, is_valid_data_packet
from sensors.hwt905_constants import COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2, DATA_HEADER_BYTE

logger = logging.getLogger(__name__)

# --- Test case cho calculate_checksum ---
def test_calculate_checksum():
    """Kiểm tra tính toán checksum cho gói dữ liệu."""
    test_data = bytes([0x55, 0x51, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]) # 10 bytes payload
    calculated_chksum = calculate_checksum(test_data)
    expected_chksum = (0x55 + 0x51 + 0x01 + 0x02 + 0x03 + 0x04 + 0x05 + 0x06 + 0x07 + 0x08) & 0xFF
    
    assert calculated_chksum == expected_chksum, f"Expected checksum {hex(expected_chksum)}, got {hex(calculated_chksum)}"

# --- Test cases cho create_write_command ---
def test_create_write_command_baud():
    """Kiểm tra tạo lệnh ghi cho thanh ghi BAUD."""
    reg_addr = 0x04 # BAUD register
    data_val = 0x0006 # 115200 baudrate
    cmd = create_write_command(reg_addr, data_val)
    expected_cmd = bytes([COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2, 0x04, 0x06, 0x00])
    
    assert cmd == expected_cmd, f"Expected command {expected_cmd.hex().upper()}, got {cmd.hex().upper()}"

def test_create_write_command_unlock():
    """Kiểm tra tạo lệnh ghi cho thanh ghi KEY."""
    reg_addr_unlock = 0x69 # KEY register
    data_val_unlock = 0xB588 # Unlock value
    cmd_unlock = create_write_command(reg_addr_unlock, data_val_unlock)
    expected_cmd_unlock = bytes([COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2, 0x69, 0x88, 0xB5])
    
    assert cmd_unlock == expected_cmd_unlock, f"Expected command {expected_cmd_unlock.hex().upper()}, got {cmd_unlock.hex().upper()}"

# --- Test cases cho is_valid_data_packet ---
def test_is_valid_data_packet_with_valid_packet():
    """Kiểm tra xác thực gói dữ liệu hợp lệ."""
    valid_packet_data = bytes([DATA_HEADER_BYTE, 0x51, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]) # Header + Type + Payload
    valid_checksum = calculate_checksum(valid_packet_data)
    valid_full_packet = valid_packet_data + bytes([valid_checksum]) # Thêm byte checksum
    
    assert is_valid_data_packet(valid_full_packet) == True, "Gói dữ liệu hợp lệ không được xác thực đúng"

def test_is_valid_data_packet_with_invalid_header():
    """Kiểm tra xác thực gói dữ liệu với header không hợp lệ."""
    valid_packet_data = bytes([DATA_HEADER_BYTE, 0x51, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    valid_checksum = calculate_checksum(valid_packet_data)
    
    # Tạo gói dữ liệu với header không hợp lệ
    invalid_header_packet = bytes([0x00, 0x51, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, valid_checksum])
    
    assert is_valid_data_packet(invalid_header_packet) == False, "Gói dữ liệu với header không hợp lệ không bị từ chối"

def test_is_valid_data_packet_with_invalid_length():
    """Kiểm tra xác thực gói dữ liệu với độ dài không hợp lệ."""
    # Tạo gói dữ liệu thiếu byte checksum
    invalid_length_packet = bytes([DATA_HEADER_BYTE, 0x51, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    
    assert is_valid_data_packet(invalid_length_packet) == False, "Gói dữ liệu với độ dài không hợp lệ không bị từ chối"

def test_is_valid_data_packet_with_invalid_checksum():
    """Kiểm tra xác thực gói dữ liệu với checksum không hợp lệ."""
    valid_packet_data = bytes([DATA_HEADER_BYTE, 0x51, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    valid_checksum = calculate_checksum(valid_packet_data)
    
    # Tạo gói dữ liệu với checksum sai
    invalid_checksum_packet = valid_packet_data + bytes([valid_checksum + 1])
    
    assert is_valid_data_packet(invalid_checksum_packet) == False, "Gói dữ liệu với checksum không hợp lệ không bị từ chối"

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    pytest.main(["-xvs", __file__])