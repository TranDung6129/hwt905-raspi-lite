"""
Decoder cho quaternion packet (0x59)
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import PACKET_TYPE_QUATERNION, SCALE_QUATERNION

class QuaternionPacketDecoder(BasePacketDecoder):
    """Decoder cho quaternion packet"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_QUATERNION
    
    def get_packet_name(self) -> str:
        return "QUATERNION"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin Quaternion (0x59)."""
        if len(payload) < 8:
            raise ValueError(f"Quaternion packet payload quá ngắn: {len(payload)} bytes")
            
        q0_raw = self.bytes_to_short(payload[0], payload[1])
        q1_raw = self.bytes_to_short(payload[2], payload[3])
        q2_raw = self.bytes_to_short(payload[4], payload[5])
        q3_raw = self.bytes_to_short(payload[6], payload[7])

        q0 = q0_raw / SCALE_QUATERNION
        q1 = q1_raw / SCALE_QUATERNION
        q2 = q2_raw / SCALE_QUATERNION
        q3 = q3_raw / SCALE_QUATERNION

        return {
            "q0": q0,
            "q1": q1,
            "q2": q2,
            "q3": q3
        }
