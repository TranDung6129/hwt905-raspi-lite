"""
Decoder cho magnetic field packet (0x54)
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import PACKET_TYPE_MAG, SCALE_TEMPERATURE

class MagneticFieldPacketDecoder(BasePacketDecoder):
    """Decoder cho magnetic field packet"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_MAG
    
    def get_packet_name(self) -> str:
        return "MAGNETIC_FIELD"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin từ trường (0x54)."""
        if len(payload) < 8:
            raise ValueError(f"Magnetic field packet payload quá ngắn: {len(payload)} bytes")
            
        hx_raw = self.bytes_to_short(payload[0], payload[1])
        hy_raw = self.bytes_to_short(payload[2], payload[3])
        hz_raw = self.bytes_to_short(payload[4], payload[5])
        temp_raw = self.bytes_to_short(payload[6], payload[7]) # Nhiệt độ là chung trong gói này

        hx = hx_raw # (LSB)
        hy = hy_raw # (LSB)
        hz = hz_raw # (LSB)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "mag_x": hx,
            "mag_y": hy,
            "mag_z": hz,
            "temperature": temperature
        }
