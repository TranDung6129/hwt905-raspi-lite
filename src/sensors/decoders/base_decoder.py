"""
Base decoder class cho các packet decoder của HWT905
"""
import logging
from typing import Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BasePacketDecoder(ABC):
    """Base class cho tất cả packet decoders"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @staticmethod
    def bytes_to_short(low_byte: int, high_byte: int) -> int:
        """Chuyển đổi 2 byte thành giá trị short (signed 16-bit integer)."""
        val = (high_byte << 8) | low_byte
        if val & 0x8000:  # Kiểm tra bit dấu (most significant bit)
            val = val - 0x10000 # Chuyển đổi sang số âm nếu là số bù 2
        return val
    
    @staticmethod
    def bytes_to_uint32(byte0: int, byte1: int, byte2: int, byte3: int) -> int:
        """Chuyển đổi 4 byte thành uint32"""
        return (byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0
    
    @abstractmethod
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """
        Decode payload thành dictionary chứa dữ liệu
        
        Args:
            payload: 8 bytes payload data
            
        Returns:
            Dict chứa dữ liệu đã decode
        """
        pass
    
    @abstractmethod
    def get_packet_type(self) -> int:
        """Trả về packet type mà decoder này xử lý"""
        pass
    
    @abstractmethod
    def get_packet_name(self) -> str:
        """Trả về tên packet type"""
        pass
