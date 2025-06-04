import pytest
import os
import shutil
import json
from pathlib import Path

# Thêm đường dẫn src vào PYTHONPATH để có thể import các module từ src
# Đảm bảo bạn chạy pytest từ thư mục gốc của dự án (your_project_root/)
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.common import load_config, ensure_directory_exists, bytes_to_hex_string, hex_string_to_bytes

# --- Fixtures (Code hỗ trợ kiểm thử) ---
@pytest.fixture
def temp_config_file(tmp_path):
    """
    Tạo một file cấu hình tạm thời cho các bài kiểm thử.
    `tmp_path` là fixture có sẵn của pytest để tạo thư mục tạm.
    """
    file_path = tmp_path / "temp_test_config.json"
    yield file_path # Cung cấp đường dẫn file cho test
    # Code sau yield sẽ chạy sau khi test hoàn tất (dọn dẹp)
    if file_path.exists():
        file_path.unlink()

@pytest.fixture
def temp_test_dir(tmp_path):
    """
    Tạo một thư mục tạm thời cho các bài kiểm thử thư mục.
    """
    test_dir = tmp_path / "test_logs_dir/subdir"
    yield test_dir
    if test_dir.parent.exists():
        shutil.rmtree(test_dir.parent)

# --- Test cases cho load_config ---
def test_load_config_valid_json(temp_config_file):
    """Kiểm tra tải file JSON hợp lệ."""
    valid_json_content = """{"test_key": "test_value", "number": 123}"""
    temp_config_file.write_text(valid_json_content)
    
    config = load_config(str(temp_config_file))
    assert config["test_key"] == "test_value"
    assert config["number"] == 123

def test_load_config_file_not_found():
    """Kiểm tra tải file không tồn tại."""
    with pytest.raises(FileNotFoundError, match="File cấu hình không tìm thấy"):
        load_config("non_existent_config.json")

def test_load_config_invalid_json(temp_config_file):
    """Kiểm tra tải file JSON không hợp lệ."""
    invalid_json_content = """{"test_key": "test_value" "number": 123}""" # Thiếu dấu phẩy
    temp_config_file.write_text(invalid_json_content)

    with pytest.raises(json.JSONDecodeError):
        load_config(str(temp_config_file))

# --- Test cases cho ensure_directory_exists ---
def test_ensure_directory_exists_creates_new_dir(temp_test_dir):
    """Kiểm tra tạo thư mục mới."""
    ensure_directory_exists(str(temp_test_dir))
    assert Path(temp_test_dir).is_dir()

def test_ensure_directory_exists_dir_already_exists(temp_test_dir):
    """Kiểm tra khi thư mục đã tồn tại."""
    Path(temp_test_dir).mkdir(parents=True) # Tạo thủ công trước
    ensure_directory_exists(str(temp_test_dir))
    assert Path(temp_test_dir).is_dir() # Vẫn phải tồn tại và không lỗi

# --- Test cases cho bytes_to_hex_string và hex_string_to_bytes ---
def test_bytes_to_hex_conversion():
    """Kiểm tra chuyển đổi bytes sang hex string."""
    test_bytes = b'\x01\x0A\xFF\x00'
    hex_str = bytes_to_hex_string(test_bytes)
    assert hex_str == "010AFF00"

def test_hex_to_bytes_conversion():
    """Kiểm tra chuyển đổi hex string sang bytes."""
    hex_str = "010AFF00"
    expected_bytes = b'\x01\x0A\xFF\x00'
    decoded_bytes = hex_string_to_bytes(hex_str)
    assert decoded_bytes == expected_bytes

def test_hex_to_bytes_invalid_input():
    """Kiểm tra chuyển đổi hex string không hợp lệ."""
    with pytest.raises(ValueError):
        hex_string_to_bytes("010AGH") # Chứa ký tự 'G' không phải hex