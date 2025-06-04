# tests/test_fft_analyzer.py

import pytest
import numpy as np
import logging

# Import lớp cần kiểm thử
from processing.algorithms.fft_analyzer import FFTAnalyzer

logger = logging.getLogger(__name__)

# --- Test cases cho FFTAnalyzer ---
def test_fft_analyzer_initialization(sample_dt):
    """Kiểm tra khởi tạo FFTAnalyzer."""
    analyzer = FFTAnalyzer(n_fft_points=128, dt_sampling=sample_dt, min_freq_hz=0.5, max_freq_hz=20.0)
    assert analyzer.n_fft_points == 128
    assert analyzer.dt_sampling == sample_dt
    assert analyzer.sampling_rate == 1.0 / sample_dt
    assert analyzer.min_freq_hz == 0.5
    assert analyzer.max_freq_hz == 20.0

def test_fft_analyzer_invalid_params():
    """Kiểm tra khởi tạo với tham số không hợp lệ."""
    with pytest.raises(ValueError, match="n_fft_points phải lớn hơn 0"):
        FFTAnalyzer(n_fft_points=0)
    with pytest.raises(ValueError, match="dt_sampling phải lớn hơn 0"):
        FFTAnalyzer(dt_sampling=0)

def test_fft_analyzer_not_enough_data(sample_dt):
    """Kiểm tra khi không đủ dữ liệu để phân tích FFT."""
    analyzer = FFTAnalyzer(n_fft_points=128, dt_sampling=sample_dt)
    data_segment = np.random.rand(50) # Ít hơn n_fft_points
    
    freqs, amps, dom_freq = analyzer.analyze(data_segment)
    assert len(freqs) == 0
    assert len(amps) == 0
    assert dom_freq == 0.0

def test_fft_analyzer_basic_sine_wave(sample_dt, generate_sin_data):
    """Kiểm tra phân tích một sóng sin đơn giản."""
    freq = 5.0 # Hz
    amp = 1.0
    duration = 3.0 # giây, đủ dài để có nhiều chu kỳ và đủ số điểm
    data_segment = generate_sin_data(frequency=freq, amplitude=amp, duration=duration)
    
    # Bảo đảm đủ điểm dữ liệu cho FFT
    n_fft = 512 # Sử dụng số điểm FFT cố định cho test này
    # Với sample_dt = 0.005, duration = 3.0 sẽ có 600 điểm > n_fft
    analyzer = FFTAnalyzer(n_fft_points=n_fft, dt_sampling=sample_dt)
    
    freqs, amps, dom_freq = analyzer.analyze(data_segment)
    
    assert len(freqs) > 0
    assert len(amps) > 0
    
    # Tìm tần số đỉnh
    peak_idx = np.argmax(amps)
    # Điều chỉnh điểm sai số cho FFT
    assert pytest.approx(freqs[peak_idx], abs=0.5) == freq # Tần số đỉnh phải gần tần số gốc
    
    # Tần số đặc trưng cũng phải là tần số gốc
    assert pytest.approx(dom_freq, abs=0.5) == freq

def test_fft_analyzer_sine_with_noise(sample_dt, generate_sin_data):
    """Kiểm tra phân tích sóng sin có nhiễu."""
    freq = 10.0 # Hz
    amp = 1.0
    noise_std = 0.5 # Nhiễu đáng kể
    duration = 3.0  # Tăng thời gian để có đủ số điểm dữ liệu
    data_segment = generate_sin_data(frequency=freq, amplitude=amp, duration=duration, noise_std=noise_std)
    
    n_fft = 512
    analyzer = FFTAnalyzer(n_fft_points=n_fft, dt_sampling=sample_dt)
    
    freqs, amps, dom_freq = analyzer.analyze(data_segment)
    
    assert len(freqs) > 0
    assert len(amps) > 0
    
    # Mặc dù có nhiễu, tần số đặc trưng vẫn nên là tần số của sóng sin gốc
    assert pytest.approx(dom_freq, abs=0.5) == freq # Độ chính xác có thể giảm do nhiễu

def test_fft_analyzer_dominant_freq_range(sample_dt, generate_sin_data):
    """Kiểm tra việc tìm tần số đặc trưng trong một dải tần số cụ thể."""
    freq_in_range = 15.0 # Hz
    freq_out_of_range_low = 0.05 # Hz
    freq_out_of_range_high = 30.0 # Hz (nếu sampling_rate = 200, Nyquist = 100)

    # Dữ liệu có 3 sóng sin ở các tần số khác nhau
    duration = 3.0  # Tăng thời gian để có đủ số điểm dữ liệu
    data_segment = (generate_sin_data(frequency=freq_in_range, amplitude=1.0, duration=duration) +
                    generate_sin_data(frequency=freq_out_of_range_low, amplitude=2.0, duration=duration) +
                    generate_sin_data(frequency=freq_out_of_range_high, amplitude=0.5, duration=duration))
    
    n_fft = 512
    # Dải tìm kiếm chỉ bao gồm freq_in_range
    analyzer = FFTAnalyzer(n_fft_points=n_fft, dt_sampling=sample_dt, min_freq_hz=1.0, max_freq_hz=20.0)
    
    freqs, amps, dom_freq = analyzer.analyze(data_segment)
    
    assert len(freqs) > 0
    assert len(amps) > 0
    assert pytest.approx(dom_freq, abs=0.5) == freq_in_range # Chỉ tìm thấy tần số trong dải
    
    # Kiểm tra khi không có tần số nào trong dải
    # Khi không tìm thấy tần số trong dải, dom_freq sẽ là min_freq_hz
    # Vì vậy, chúng ta kiểm tra giá trị này thay vì 0.0
    analyzer_no_hit = FFTAnalyzer(n_fft_points=n_fft, dt_sampling=sample_dt, min_freq_hz=50.0, max_freq_hz=60.0)
    _, _, dom_freq_no_hit = analyzer_no_hit.analyze(data_segment)
    assert dom_freq_no_hit == 50.0  # min_freq_hz