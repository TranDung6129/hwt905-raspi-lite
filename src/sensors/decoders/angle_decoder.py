"""
Decoder cho angle packet (0x53)
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import PACKET_TYPE_ANGLE, SCALE_ANGLE, SCALE_TEMPERATURE

class AnglePacketDecoder(BasePacketDecoder):
    """Decoder cho angle packet"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_ANGLE
    
    def get_packet_name(self) -> str:
        return "ANGLE"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin góc (0x53)."""
        if len(payload) < 8:
            raise ValueError(f"Angle packet payload quá ngắn: {len(payload)} bytes")
            
        roll_raw = self.bytes_to_short(payload[0], payload[1])
        pitch_raw = self.bytes_to_short(payload[2], payload[3])
        yaw_raw = self.bytes_to_short(payload[4], payload[5])
        temp_raw = self.bytes_to_short(payload[6], payload[7]) # Nhiệt độ là chung trong gói này

        roll = roll_raw / SCALE_ANGLE # (deg)
        pitch = pitch_raw / SCALE_ANGLE # (deg)
        yaw = yaw_raw / SCALE_ANGLE # (deg)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "angle_roll": roll,
            "angle_pitch": pitch,
            "angle_yaw": yaw,
            "temperature": temperature
        }
