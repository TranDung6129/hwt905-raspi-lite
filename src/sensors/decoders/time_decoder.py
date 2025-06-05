"""
Decoder cho time packet (0x50)
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import PACKET_TYPE_TIME

class TimePacketDecoder(BasePacketDecoder):
    """Decoder cho time packet"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_TIME
    
    def get_packet_name(self) -> str:
        return "TIME"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin thời gian (0x50)."""
        if len(payload) < 8:
            raise ValueError(f"Time packet payload quá ngắn: {len(payload)} bytes")
            
        yy = payload[0]  # Year (20YY)
        mm = payload[1]  # Month
        dd = payload[2]  # Day
        hh = payload[3]  # Hour
        mn = payload[4]  # Minute
        ss = payload[5]  # Second
        ms = self.bytes_to_short(payload[6], payload[7]) # Millisecond (msL, msH)
        
        return {
            "year": 2000 + yy,
            "month": mm,
            "day": dd,
            "hour": hh,
            "minute": mn,
            "second": ss,
            "millisecond": ms
        }
