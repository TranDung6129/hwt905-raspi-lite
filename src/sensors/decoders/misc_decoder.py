"""
Decoder cho các packet khác
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import (
    PACKET_TYPE_PORT_STATUS, PACKET_TYPE_PRESSURE, PACKET_TYPE_READ_REGISTER,
    SCALE_GPS_ALTITUDE
)

class PortStatusPacketDecoder(BasePacketDecoder):
    """Decoder cho port status packet (0x55)"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_PORT_STATUS
    
    def get_packet_name(self) -> str:
        return "PORT_STATUS"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin trạng thái cổng (0x55)."""
        if len(payload) < 8:
            raise ValueError(f"Port status packet payload quá ngắn: {len(payload)} bytes")
            
        d0_status = self.bytes_to_short(payload[0], payload[1])
        d1_status = self.bytes_to_short(payload[2], payload[3])
        d2_status = self.bytes_to_short(payload[4], payload[5])
        d3_status = self.bytes_to_short(payload[6], payload[7])
        
        return {
            "d0_status": d0_status,
            "d1_status": d1_status,
            "d2_status": d2_status,
            "d3_status": d3_status
        }

class PressureHeightPacketDecoder(BasePacketDecoder):
    """Decoder cho pressure/height packet (0x56)"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_PRESSURE
    
    def get_packet_name(self) -> str:
        return "PRESSURE_HEIGHT"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin áp suất và độ cao (0x56)."""
        if len(payload) < 8:
            raise ValueError(f"Pressure height packet payload quá ngắn: {len(payload)} bytes")
            
        # Áp suất là 32-bit (P0 P1 P2 P3)
        pressure = self.bytes_to_uint32(payload[0], payload[1], payload[2], payload[3]) # (Pa)
        
        # Độ cao là 32-bit (H0 H1 H2 H3)
        height_raw = self.bytes_to_uint32(payload[4], payload[5], payload[6], payload[7])
        height = height_raw / SCALE_GPS_ALTITUDE # (cm / 10 = m)
        
        return {
            "pressure": pressure,
            "height": height
        }

class ReadRegisterPacketDecoder(BasePacketDecoder):
    """Decoder cho read register response packet (0x5F)"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_READ_REGISTER
    
    def get_packet_name(self) -> str:
        return "READ_REGISTER_RESPONSE"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """
        Giải mã gói tin phản hồi từ lệnh đọc thanh ghi (0x5F).
        Gói tin này chứa giá trị của 4 thanh ghi liên tiếp bắt đầu từ thanh ghi yêu cầu.
        Format: REG1L REG1H REG2L REG2H REG3L REG3H REG4L REG4H
        """
        if len(payload) < 8:
            raise ValueError(f"Read register packet payload quá ngắn: {len(payload)} bytes")
        
        reg1_value = self.bytes_to_short(payload[0], payload[1])
        reg2_value = self.bytes_to_short(payload[2], payload[3])
        reg3_value = self.bytes_to_short(payload[4], payload[5])
        reg4_value = self.bytes_to_short(payload[6], payload[7])

        return {
            "reg1_value": reg1_value,
            "reg2_value": reg2_value,
            "reg3_value": reg3_value,
            "reg4_value": reg4_value
        }
