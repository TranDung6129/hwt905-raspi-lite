"""
Decoder cho angular velocity packet (0x52)
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import PACKET_TYPE_GYRO, SCALE_ANGULAR_VELOCITY, SCALE_TEMPERATURE

class AngularVelocityPacketDecoder(BasePacketDecoder):
    """Decoder cho angular velocity packet"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_GYRO
    
    def get_packet_name(self) -> str:
        return "ANGULAR_VELOCITY"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin vận tốc góc (0x52)."""
        if len(payload) < 8:
            raise ValueError(f"Angular velocity packet payload quá ngắn: {len(payload)} bytes")
            
        gx_raw = self.bytes_to_short(payload[0], payload[1])
        gy_raw = self.bytes_to_short(payload[2], payload[3])
        gz_raw = self.bytes_to_short(payload[4], payload[5])
        temp_raw = self.bytes_to_short(payload[6], payload[7]) # Nhiệt độ là chung trong gói này

        gx = gx_raw / SCALE_ANGULAR_VELOCITY # (deg/s)
        gy = gy_raw / SCALE_ANGULAR_VELOCITY # (deg/s)
        gz = gz_raw / SCALE_ANGULAR_VELOCITY # (deg/s)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "gyro_x": gx,
            "gyro_y": gy,
            "gyro_z": gz,
            "temperature": temperature
        }
