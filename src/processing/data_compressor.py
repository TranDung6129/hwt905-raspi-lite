# src/processing/data_compressor.py

import json
import msgpack # Cần cài đặt: pip install msgpack
import zlib    # Thư viện nén tích hợp sẵn của Python
import logging
import numpy as np
from typing import Dict, Any, Union, List

logger = logging.getLogger(__name__)

class DataCompressor:
    """
    Lớp để nén và đóng gói dữ liệu cảm biến.
    Hỗ trợ JSON, MessagePack và tùy chọn nén Zlib.
    """
    def __init__(self, format: str = "msgpack", use_zlib: bool = False):
        """
        Khởi tạo bộ nén dữ liệu.

        Args:
            format (str): Định dạng đầu ra ('json' hoặc 'msgpack').
            use_zlib (bool): Có sử dụng nén Zlib sau khi đóng gói không. Chỉ áp dụng cho MessagePack.
        """
        if format not in ["json", "msgpack"]:
            raise ValueError("Định dạng không hợp lệ. Chỉ hỗ trợ 'json' hoặc 'msgpack'.")
        self.format = format
        self.use_zlib = use_zlib and (format == "msgpack") # Zlib chỉ nên dùng với msgpack để hiệu quả
        logger.info(f"Đã khởi tạo DataCompressor: format='{self.format}', use_zlib={self.use_zlib}.")

    def compress(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bytes:
        """
        Nén và đóng gói dữ liệu.

        Args:
            data (Union[Dict[str, Any], List[Dict[str, Any]]]): Dữ liệu đầu vào (một dict hoặc list of dicts).

        Returns:
            bytes: Dữ liệu đã được nén/đóng gói dưới dạng bytes.
        """
        serialized_data: bytes
        
        # Hàm chuyển đổi numpy array sang list cho JSON
        def numpy_encoder(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

        if self.format == "json":
            # json.dumps trả về string, cần encode thành bytes
            try:
                serialized_data = json.dumps(data, default=numpy_encoder).encode('utf-8')
            except TypeError as e:
                logger.error(f"Lỗi JSON serialization: {e}. Dữ liệu: {data}")
                raise
        elif self.format == "msgpack":
            # msgpack.packb trả về bytes
            # msgpack tự động xử lý numpy array tốt hơn json nếu dùng msgpack.ext.ndarray
            # hoặc đơn giản là chuyển sang list trước khi pack
            data_to_pack = data
            if isinstance(data, dict):
                data_to_pack = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in data.items()}
            elif isinstance(data, list):
                data_to_pack = [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in item.items()} for item in data]
            
            serialized_data = msgpack.packb(data_to_pack, use_bin_type=True)
        else:
            raise ValueError("Định dạng nén không được hỗ trợ.")

        if self.use_zlib:
            compressed_data = zlib.compress(serialized_data)
            logger.debug(f"Nén Zlib: Kích thước gốc {len(serialized_data)} bytes, nén {len(compressed_data)} bytes.")
            return compressed_data
        
        return serialized_data

    def decompress(self, data: bytes) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Giải nén và giải đóng gói dữ liệu.

        Args:
            data (bytes): Dữ liệu đã được nén/đóng gói dưới dạng bytes.

        Returns:
            Union[Dict[str, Any], List[Dict[str, Any]]]: Dữ liệu đã giải nén.
        """
        decompressed_data: bytes
        if self.use_zlib:
            try:
                decompressed_data = zlib.decompress(data)
            except zlib.error as e:
                logger.error(f"Lỗi giải nén Zlib: {e}")
                raise
        else:
            decompressed_data = data

        if self.format == "json":
            return json.loads(decompressed_data.decode('utf-8'))
        elif self.format == "msgpack":
            return msgpack.unpackb(decompressed_data, raw=False)
        else:
            raise ValueError("Định dạng giải nén không được hỗ trợ.")