"""
Chứa các hàm để mã hóa (tạo) các gói lệnh gửi đến cảm biến
và xử lý checksum cho cả gói lệnh và gói dữ liệu.
"""
import logging

from src.sensors.hwt905_constants import (
    COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2,
    DATA_HEADER_BYTE,
    COMMAND_PACKET_LENGTH, DATA_PACKET_LENGTH
)

logger = logging.getLogger(__name__)

def calculate_checksum(data_bytes: bytes) -> int:
    """
    Tính toán checksum cho một chuỗi byte theo quy tắc của WitMotion:
    Tổng tất cả các byte trong gói tin (trừ byte checksum cuối cùng), lấy byte thấp (AND 0xFF).
    Args:
        data_bytes (bytes): Chuỗi byte của gói tin (đã bao gồm header và payload, nhưng CHƯA bao gồm checksum cuối cùng).
    Returns:
        int: Giá trị checksum (0-255).
    """
    checksum = sum(data_bytes) & 0xFF
    return checksum

def create_write_command(register_address: int, data_value: int) -> bytes:
    """
    Tạo một gói lệnh ghi thanh ghi theo định dạng FF AA ADDR DATAL DATAH.
    Lệnh ghi không có checksum theo tài liệu, nhưng một số tài liệu khác
    (hoặc ví dụ trong phần mềm PC) lại gán DATAH là checksum.
    Tuy nhiên, theo PDF, lệnh ghi chỉ có 5 bytes.

    Args:
        register_address (int): Địa chỉ thanh ghi (0x00 - 0xFF).
        data_value (int): Giá trị 16-bit cần ghi vào thanh ghi.

    Returns:
        bytes: Gói lệnh ghi đã được mã hóa.
    """
    data_low = data_value & 0xFF
    data_high = (data_value >> 8) & 0xFF

    command = bytes([
        COMMAND_HEADER_BYTE1,
        COMMAND_HEADER_BYTE2,
        register_address & 0xFF,
        data_low,
        data_high
    ])
    
    if len(command) != COMMAND_PACKET_LENGTH:
        logger.error(f"Lỗi tạo lệnh ghi: Độ dài không khớp. Mong đợi {COMMAND_PACKET_LENGTH}, nhận được {len(command)}")
    
    logger.debug(f"Đã tạo lệnh ghi: {command.hex().upper()} cho REG {hex(register_address)} với giá trị {hex(data_value)}")
    return command

def is_valid_data_packet(packet_bytes: bytes) -> bool:
    """
    Kiểm tra xem một chuỗi byte có phải là gói dữ liệu hợp lệ không.
    Kiểm tra header, độ dài, và checksum.
    Args:
        packet_bytes (bytes): Chuỗi byte nhận được từ serial.
    Returns:
        bool: True nếu gói tin hợp lệ, False nếu không.
    """
    if len(packet_bytes) != DATA_PACKET_LENGTH:
        return False
    
    if packet_bytes[0] != DATA_HEADER_BYTE:
        return False
    
    # Tính checksum của gói tin (trừ byte checksum cuối cùng)
    calculated_checksum = calculate_checksum(packet_bytes[:-1])
    
    # So sánh với checksum nhận được
    if calculated_checksum != packet_bytes[-1]:
        logger.debug(f"Lỗi checksum: Tính toán {hex(calculated_checksum)}, nhận được {hex(packet_bytes[-1])}. Gói: {packet_bytes.hex()}")
        return False
        
    return True