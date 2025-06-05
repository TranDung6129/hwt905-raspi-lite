"""
Decoder factory và registry cho HWT905 packet decoders
"""
from typing import Dict, Type, Optional
import logging
from .base_decoder import BasePacketDecoder
from .time_decoder import TimePacketDecoder
from .acceleration_decoder import AccelerationPacketDecoder
from .angular_velocity_decoder import AngularVelocityPacketDecoder
from .angle_decoder import AnglePacketDecoder
from .magnetic_field_decoder import MagneticFieldPacketDecoder
from .quaternion_decoder import QuaternionPacketDecoder
from .gps_decoder import GPSLonLatPacketDecoder, GPSSpeedPacketDecoder, GPSAccuracyPacketDecoder
from .misc_decoder import PortStatusPacketDecoder, PressureHeightPacketDecoder, ReadRegisterPacketDecoder

logger = logging.getLogger(__name__)

class PacketDecoderFactory:
    """
    Factory class để tạo và quản lý các packet decoder
    """
    
    def __init__(self):
        self._decoders: Dict[int, BasePacketDecoder] = {}
        self._register_default_decoders()
    
    def _register_default_decoders(self):
        """Đăng ký các decoder mặc định"""
        default_decoders = [
            TimePacketDecoder(),
            AccelerationPacketDecoder(),
            AngularVelocityPacketDecoder(),
            AnglePacketDecoder(),
            MagneticFieldPacketDecoder(),
            QuaternionPacketDecoder(),
            GPSLonLatPacketDecoder(),
            GPSSpeedPacketDecoder(),
            GPSAccuracyPacketDecoder(),
            PortStatusPacketDecoder(),
            PressureHeightPacketDecoder(),
            ReadRegisterPacketDecoder()
        ]
        
        for decoder in default_decoders:
            self.register_decoder(decoder)
    
    def register_decoder(self, decoder: BasePacketDecoder):
        """
        Đăng ký một decoder cho packet type cụ thể
        
        Args:
            decoder: Instance của decoder
        """
        packet_type = decoder.get_packet_type()
        self._decoders[packet_type] = decoder
        logger.debug(f"Đã đăng ký decoder cho packet type 0x{packet_type:02X} ({decoder.get_packet_name()})")
    
    def get_decoder(self, packet_type: int) -> Optional[BasePacketDecoder]:
        """
        Lấy decoder cho packet type
        
        Args:
            packet_type: Loại packet cần decode
            
        Returns:
            Decoder instance hoặc None nếu không tìm thấy
        """
        return self._decoders.get(packet_type)
    
    def decode_packet(self, packet_type: int, payload: bytes) -> Dict:
        """
        Decode packet với type và payload cho trước
        
        Args:
            packet_type: Loại packet
            payload: Payload data (8 bytes)
            
        Returns:
            Dict chứa dữ liệu đã decode hoặc error info
        """
        decoder = self.get_decoder(packet_type)
        if not decoder:
            logger.warning(f"Không tìm thấy decoder cho packet type 0x{packet_type:02X}")
            return {"error": "no_decoder_found", "packet_type": packet_type}
        
        try:
            return decoder.decode(payload)
        except Exception as e:
            logger.error(f"Lỗi khi decode packet type 0x{packet_type:02X}: {e}")
            return {"error": "decode_error", "message": str(e), "packet_type": packet_type}
    
    def get_packet_type_name(self, packet_type: int) -> str:
        """
        Lấy tên packet type
        
        Args:
            packet_type: Loại packet
            
        Returns:
            Tên packet hoặc "UNKNOWN"
        """
        decoder = self.get_decoder(packet_type)
        if decoder:
            return decoder.get_packet_name()
        return "UNKNOWN"
    
    def list_supported_types(self) -> Dict[int, str]:
        """
        Liệt kê tất cả packet types được hỗ trợ
        
        Returns:
            Dict mapping packet_type -> packet_name
        """
        return {
            packet_type: decoder.get_packet_name()
            for packet_type, decoder in self._decoders.items()
        }
    
    def get_registered_types(self) -> set:
        """
        Lấy tập hợp các packet types đã đăng ký
        
        Returns:
            Set của các packet types đã đăng ký
        """
        return set(self._decoders.keys())
