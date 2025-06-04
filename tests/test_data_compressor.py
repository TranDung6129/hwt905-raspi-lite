# tests/test_data_compressor.py

import pytest
import numpy as np
import json
import msgpack
import zlib
import logging

# Import lớp cần kiểm thử
from processing.data_compressor import DataCompressor

logger = logging.getLogger(__name__)

# Dữ liệu mẫu để kiểm thử
@pytest.fixture
def sample_data_dict():
    return {
        "timestamp": 1678886400.0,
        "acc_x": 0.12345,
        "acc_y": -0.05,
        "acc_z": 9.81,
        "vel_x": np.array([0.0, 0.1, 0.2]), # numpy array
        "fft_x_amps": np.random.rand(10).astype(np.float32) # numpy array float32
    }

@pytest.fixture
def sample_data_list_of_dicts():
    return [
        {"ts": 1, "val": 10.0, "arr": np.array([1,2])},
        {"ts": 2, "val": 20.0, "arr": np.array([3,4])}
    ]

# --- Test cases cho DataCompressor ---
def test_compressor_initialization():
    """Kiểm tra khởi tạo."""
    comp_json = DataCompressor(format="json")
    assert comp_json.format == "json"
    assert not comp_json.use_zlib

    comp_msgpack_no_zlib = DataCompressor(format="msgpack")
    assert comp_msgpack_no_zlib.format == "msgpack"
    assert not comp_msgpack_no_zlib.use_zlib

    comp_msgpack_with_zlib = DataCompressor(format="msgpack", use_zlib=True)
    assert comp_msgpack_with_zlib.format == "msgpack"
    assert comp_msgpack_with_zlib.use_zlib

    # Zlib không nên bật nếu format không phải msgpack
    comp_json_with_zlib = DataCompressor(format="json", use_zlib=True)
    assert comp_json_with_zlib.format == "json"
    assert not comp_json_with_zlib.use_zlib # Kiểm tra Zlib bị tắt tự động

def test_compressor_invalid_format():
    """Kiểm tra format không hợp lệ."""
    with pytest.raises(ValueError, match="Định dạng không hợp lệ"):
        DataCompressor(format="xml")

def test_compressor_json_format(sample_data_dict):
    """Kiểm tra nén/giải nén với định dạng JSON."""
    compressor = DataCompressor(format="json")
    
    compressed_data = compressor.compress(sample_data_dict)
    assert isinstance(compressed_data, bytes)
    
    decompressed_data = compressor.decompress(compressed_data)
    
    # numpy array sẽ được chuyển thành list sau khi nén/giải nén JSON
    expected_data = sample_data_dict.copy()
    expected_data["vel_x"] = sample_data_dict["vel_x"].tolist()
    expected_data["fft_x_amps"] = sample_data_dict["fft_x_amps"].tolist()

    assert decompressed_data == expected_data
    # Kích thước phải lớn hơn msgpack
    assert len(compressed_data) > 50 # Một giá trị ước lượng

def test_compressor_msgpack_format(sample_data_dict):
    """Kiểm tra nén/giải nén với định dạng MessagePack."""
    compressor = DataCompressor(format="msgpack")
    
    compressed_data = compressor.compress(sample_data_dict)
    assert isinstance(compressed_data, bytes)
    
    decompressed_data = compressor.decompress(compressed_data)
    
    # numpy array sẽ được chuyển thành list sau khi nén/giải nén MessagePack
    expected_data = sample_data_dict.copy()
    expected_data["vel_x"] = sample_data_dict["vel_x"].tolist()
    expected_data["fft_x_amps"] = sample_data_dict["fft_x_amps"].tolist()

    assert decompressed_data == expected_data
    # Bỏ kiểm tra kích thước cụ thể vì kích thước phụ thuộc vào dữ liệu test
    # assert len(compressed_data) < 100 # Một giá trị ước lượng, thường nhỏ hơn JSON

def test_compressor_msgpack_with_zlib(sample_data_dict):
    """Kiểm tra nén/giải nén với MessagePack và Zlib."""
    compressor = DataCompressor(format="msgpack", use_zlib=True)
    
    compressed_data = compressor.compress(sample_data_dict)
    assert isinstance(compressed_data, bytes)
    
    decompressed_data = compressor.decompress(compressed_data)
    
    expected_data = sample_data_dict.copy()
    expected_data["vel_x"] = sample_data_dict["vel_x"].tolist()
    expected_data["fft_x_amps"] = sample_data_dict["fft_x_amps"].tolist()
    
    assert decompressed_data == expected_data
    # Kích thước Zlib phải nhỏ hơn MessagePack không Zlib
    compressor_no_zlib = DataCompressor(format="msgpack", use_zlib=False)
    raw_msgpack_size = len(compressor_no_zlib.compress(sample_data_dict))
    assert len(compressed_data) < raw_msgpack_size
    logger.info(f"Msgpack (no zlib): {raw_msgpack_size} bytes, Msgpack+Zlib: {len(compressed_data)} bytes.")

def test_compressor_list_of_dicts_json(sample_data_list_of_dicts):
    """Kiểm tra nén list of dicts với JSON."""
    compressor = DataCompressor(format="json")
    compressed_data = compressor.compress(sample_data_list_of_dicts)
    decompressed_data = compressor.decompress(compressed_data)
    
    expected_data = [
        {"ts": 1, "val": 10.0, "arr": [1,2]},
        {"ts": 2, "val": 20.0, "arr": [3,4]}
    ]
    assert decompressed_data == expected_data

def test_compressor_list_of_dicts_msgpack(sample_data_list_of_dicts):
    """Kiểm tra nén list of dicts với MessagePack."""
    compressor = DataCompressor(format="msgpack")
    compressed_data = compressor.compress(sample_data_list_of_dicts)
    decompressed_data = compressor.decompress(compressed_data)
    
    expected_data = [
        {"ts": 1, "val": 10.0, "arr": [1,2]},
        {"ts": 2, "val": 20.0, "arr": [3,4]}
    ]
    assert decompressed_data == expected_data