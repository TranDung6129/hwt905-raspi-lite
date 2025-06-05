"""
Decoder cho acceleration packet (0x51)
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import PACKET_TYPE_ACC, SCALE_ACCELERATION, SCALE_TEMPERATURE

class AccelerationPacketDecoder(BasePacketDecoder):
    """Decoder cho acceleration packet"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_ACC
    
    def get_packet_name(self) -> str:
        return "ACCELERATION"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin gia tốc (0x51)."""
        if len(payload) < 8:
            raise ValueError(f"Acceleration packet payload quá ngắn: {len(payload)} bytes")
            
        ax_raw = self.bytes_to_short(payload[0], payload[1])
        ay_raw = self.bytes_to_short(payload[2], payload[3])
        az_raw = self.bytes_to_short(payload[4], payload[5])
        temp_raw = self.bytes_to_short(payload[6], payload[7])

        ax = ax_raw / SCALE_ACCELERATION # (g)
        ay = ay_raw / SCALE_ACCELERATION # (g)
        az = az_raw / SCALE_ACCELERATION # (g)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "acc_x": ax,
            "acc_y": ay,
            "acc_z": az,
            "temperature": temperature
        }
