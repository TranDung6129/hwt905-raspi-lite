import json
import os
from pathlib import Path

def load_config(file_path: str) -> dict:
    """
    Tải cấu hình từ một file JSON.

    Args:
        file_path (str): Đường dẫn đến file cấu hình JSON.

    Returns:
        dict: Một dictionary chứa dữ liệu cấu hình.

    Raises:
        FileNotFoundError: Nếu file cấu hình không tìm thấy.
        json.JSONDecodeError: Nếu file JSON không hợp lệ.
        Exception: Các lỗi khác trong quá trình đọc file.
    """
    full_path = Path(file_path)
    if not full_path.exists():
        raise FileNotFoundError(f"File cấu hình không tìm thấy: {full_path}")
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Lỗi cú pháp JSON trong file {full_path}: {e.msg} (at line {e.lineno}, column {e.colno})", e.doc, e.pos)
    except Exception as e:
        raise Exception(f"Lỗi khi tải file cấu hình {full_path}: {e}")

def ensure_directory_exists(path: str):
    """
    Đảm bảo thư mục tồn tại. Nếu không, nó sẽ được tạo ra.

    Args:
        path (str): Đường dẫn thư mục cần kiểm tra/tạo.
    """
    Path(path).mkdir(parents=True, exist_ok=True)

def bytes_to_hex_string(data_bytes: bytes) -> str:
    """
    Chuyển đổi một chuỗi bytes thành chuỗi hex.

    Args:
        data_bytes (bytes): Chuỗi bytes đầu vào.

    Returns:
        str: Chuỗi hex tương ứng.
    """
    return data_bytes.hex().upper()

def hex_string_to_bytes(hex_str: str) -> bytes:
    """
    Chuyển đổi một chuỗi hex thành chuỗi bytes.

    Args:
        hex_str (str): Chuỗi hex đầu vào.

    Returns:
        bytes: Chuỗi bytes tương ứng.
    """
    return bytes.fromhex(hex_str)