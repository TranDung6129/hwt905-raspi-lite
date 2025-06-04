# tests/test_data_filter.py

import pytest
import numpy as np
import logging

# Import các lớp cần kiểm thử
from processing.data_filter import MovingAverageFilter, LowPassFilter

logger = logging.getLogger(__name__)

# --- Test cases cho MovingAverageFilter ---
def test_moving_average_filter_initialization():
    """Kiểm tra khởi tạo bộ lọc MA."""
    ma_filter = MovingAverageFilter(window_size=3)
    assert ma_filter.window_size == 3
    assert len(ma_filter.buffer) == 0

def test_moving_average_filter_invalid_window_size():
    """Kiểm tra khởi tạo với window_size không hợp lệ."""
    with pytest.raises(ValueError, match="Kích thước cửa sổ .* phải là số nguyên dương"):
        MovingAverageFilter(window_size=0)
    with pytest.raises(ValueError, match="Kích thước cửa sổ .* phải là số nguyên dương"):
        MovingAverageFilter(window_size=-1)
    with pytest.raises(ValueError, match="Kích thước cửa sổ .* phải là số nguyên dương"):
        MovingAverageFilter(window_size=3.5)

def test_moving_average_filter_process_basic():
    """Kiểm tra quá trình lọc cơ bản."""
    ma_filter = MovingAverageFilter(window_size=3)
    
    # Buffer chưa đầy
    assert ma_filter.process(1.0) == 1.0
    assert ma_filter.process(2.0) == 1.5
    
    # Buffer đầy
    assert ma_filter.process(3.0) == 2.0 # (1+2+3)/3
    assert ma_filter.process(4.0) == 3.0 # (2+3+4)/3
    assert ma_filter.process(5.0) == 4.0 # (3+4+5)/3

def test_moving_average_filter_process_with_noise():
    """Kiểm tra làm mịn nhiễu."""
    ma_filter = MovingAverageFilter(window_size=5)
    data = [1.0, 1.1, 0.9, 1.2, 0.8, 2.0, 2.1, 1.9, 2.2, 1.8]
    filtered_data = [ma_filter.process(x) for x in data]
    
    # Kết quả mong đợi (tính toán thủ công cho vài điểm đầu và cuối)
    assert pytest.approx(filtered_data[0]) == 1.0
    assert pytest.approx(filtered_data[1]) == 1.05
    assert pytest.approx(filtered_data[4]) == (1.0+1.1+0.9+1.2+0.8)/5 # 1.0
    assert pytest.approx(filtered_data[9]) == (2.1+1.9+2.2+1.8)/4 # (8.0/4 = 2.0)

    # Dữ liệu ổn định, trung bình phải gần giá trị thực
    steady_data = [10.0, 10.1, 9.9, 10.2, 9.8] # sum = 50.0
    for x in steady_data:
        ma_filter.process(x)
    assert pytest.approx(ma_filter.process(10.0)) == 10.0 # (10.1+9.9+10.2+9.8+10)/5 = 10.0

def test_moving_average_filter_reset():
    """Kiểm tra reset bộ lọc."""
    ma_filter = MovingAverageFilter(window_size=3)
    ma_filter.process(1.0)
    ma_filter.process(2.0)
    assert len(ma_filter.buffer) == 2
    ma_filter.reset()
    assert len(ma_filter.buffer) == 0
    assert ma_filter.process(10.0) == 10.0

# --- Test cases cho LowPassFilter ---
def test_low_pass_filter_initialization():
    """Kiểm tra khởi tạo bộ lọc LP."""
    lp_filter = LowPassFilter(alpha=0.5)
    assert lp_filter.alpha == 0.5
    assert lp_filter.last_filtered_value == 0.0
    assert not lp_filter.is_initialized

def test_low_pass_filter_invalid_alpha():
    """Kiểm tra khởi tạo với alpha không hợp lệ."""
    with pytest.raises(ValueError, match="Hệ số alpha phải nằm trong khoảng \\[0, 1\\]"):
        LowPassFilter(alpha=-0.1)
    with pytest.raises(ValueError, match="Hệ số alpha phải nằm trong khoảng \\[0, 1\\]"):
        LowPassFilter(alpha=1.1)

def test_low_pass_filter_process_basic():
    """Kiểm tra quá trình lọc cơ bản."""
    lp_filter = LowPassFilter(alpha=0.5) # y_n = 0.5*x_n + 0.5*y_{n-1}
    
    assert lp_filter.process(10.0) == 10.0 # Mẫu đầu tiên
    assert lp_filter.is_initialized
    assert lp_filter.process(0.0) == 5.0 # 0.5*0 + 0.5*10 = 5
    assert lp_filter.process(10.0) == 7.5 # 0.5*10 + 0.5*5 = 7.5
    assert lp_filter.process(0.0) == 3.75 # 0.5*0 + 0.5*7.5 = 3.75

def test_low_pass_filter_process_alpha_extremes():
    """Kiểm tra với alpha = 0 và alpha = 1."""
    # alpha = 0: Output luôn giữ nguyên giá trị đầu tiên
    lp_filter_0 = LowPassFilter(alpha=0.0)
    assert lp_filter_0.process(100.0) == 100.0
    assert lp_filter_0.process(0.0) == 100.0
    assert lp_filter_0.process(500.0) == 100.0

    # alpha = 1: Output luôn bằng mẫu gốc (không lọc)
    lp_filter_1 = LowPassFilter(alpha=1.0)
    assert lp_filter_1.process(100.0) == 100.0
    assert lp_filter_1.process(0.0) == 0.0
    assert lp_filter_1.process(500.0) == 500.0

def test_low_pass_filter_reset():
    """Kiểm tra reset bộ lọc."""
    lp_filter = LowPassFilter(alpha=0.5)
    lp_filter.process(10.0)
    lp_filter.process(0.0)
    assert lp_filter.last_filtered_value == 5.0
    lp_filter.reset()
    assert lp_filter.last_filtered_value == 0.0
    assert not lp_filter.is_initialized
    assert lp_filter.process(20.0) == 20.0 # Mẫu đầu tiên sau reset