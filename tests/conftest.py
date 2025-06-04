# tests/conftest.py

import pytest
import numpy as np
import logging
import sys
import os

# Đảm bảo có thể import các module từ src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Thiết lập logging cho các test (có thể tùy chỉnh)
# Điều này sẽ áp dụng cho tất cả các test file sử dụng conftest.py
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Fixtures dùng chung cho dữ liệu giả lập ---
@pytest.fixture(scope="module")
def sample_dt():
    """Khoảng thời gian lấy mẫu (giây)."""
    return 0.005 # Tương đương 200 Hz

@pytest.fixture(scope="module")
def generate_sin_data(sample_dt):
    """
    Tạo dữ liệu sóng sin để kiểm thử các bộ lọc và FFT.
    Args:
        frequency (float): Tần số của sóng sin.
        amplitude (float): Biên độ của sóng sin.
        duration (float): Thời lượng của tín hiệu (giây).
        noise_std (float): Độ lệch chuẩn của nhiễu Gaussian.
    Returns:
        np.ndarray: Mảng dữ liệu sóng sin có nhiễu.
    """
    def _generate(frequency: float, amplitude: float, duration: float, noise_std: float = 0.0):
        t = np.arange(0, duration, sample_dt)
        signal = amplitude * np.sin(2 * np.pi * frequency * t)
        if noise_std > 0:
            noise = np.random.normal(0, noise_std, len(t))
            signal += noise
        return signal
    return _generate

@pytest.fixture(scope="module")
def generate_linear_trend_data(sample_dt):
    """
    Tạo dữ liệu với xu hướng tuyến tính.
    Args:
        slope (float): Độ dốc của xu hướng.
        intercept (float): Hệ số chặn.
        duration (float): Thời lượng của tín hiệu (giây).
        noise_std (float): Độ lệch chuẩn của nhiễu.
    Returns:
        np.ndarray: Mảng dữ liệu với xu hướng tuyến tính và nhiễu.
    """
    def _generate(slope: float, intercept: float, duration: float, noise_std: float = 0.0):
        t = np.arange(0, duration, sample_dt)
        trend = slope * t + intercept
        if noise_std > 0:
            noise = np.random.normal(0, noise_std, len(t))
            trend += noise
        return trend
    return _generate

@pytest.fixture(scope="module")
def generate_accel_data(sample_dt):
    """
    Tạo dữ liệu gia tốc giả lập cho việc kiểm thử tích hợp RLS.
    Giả lập một sự kiện gia tốc, sau đó quay về 0g.
    """
    def _generate(duration: float = 5.0, peak_accel: float = 1.0, event_duration: float = 0.5):
        t = np.arange(0, duration, sample_dt)
        accel_data = np.zeros_like(t)
        
        # Một sự kiện gia tốc hình sin trong khoảng thời gian nhất định
        start_idx = int(len(t) * 0.2)
        end_idx = start_idx + int(event_duration / sample_dt)
        
        if end_idx > len(t):
            end_idx = len(t)
        
        if start_idx < end_idx:
            event_t = np.arange(0, event_duration, sample_dt)[:end_idx - start_idx]
            if len(event_t) > 0:
                accel_data[start_idx:end_idx] = peak_accel * np.sin(np.pi * event_t / event_duration)
        
        # Thêm nhiễu trắng nhỏ
        accel_data += np.random.normal(0, 0.005, len(t)) # 0.005g noise
        
        return accel_data
    return _generate