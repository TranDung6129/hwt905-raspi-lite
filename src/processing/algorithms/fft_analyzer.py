import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import windows
import logging

logger = logging.getLogger(__name__)

class FFTAnalyzer:
    """
    Lớp để thực hiện phân tích FFT trên dữ liệu gia tốc
    và tìm tần số đặc trưng.
    """
    def __init__(self, n_fft_points: int = 512, dt_sampling: float = 0.005,
                 min_freq_hz: float = 0.1, max_freq_hz: float = None):
        """
        Khởi tạo bộ phân tích FFT.
        
        Args:
            n_fft_points (int): Số điểm dữ liệu dùng cho mỗi lần tính FFT (nên là lũy thừa của 2).
            dt_sampling (float): Khoảng thời gian lấy mẫu (giây) của dữ liệu đầu vào.
            min_freq_hz (float): Tần số thấp nhất để xem xét khi tìm tần số đặc trưng.
            max_freq_hz (float): Tần số cao nhất để xem xét. Mặc định là tần số Nyquist.
        """
        if not n_fft_points > 0:
            raise ValueError("n_fft_points phải lớn hơn 0.")
        if not dt_sampling > 0:
            raise ValueError("dt_sampling phải lớn hơn 0.")

        self.n_fft_points = n_fft_points
        self.dt_sampling = dt_sampling
        self.sampling_rate = 1.0 / dt_sampling
        self.min_freq_hz = min_freq_hz
        self.max_freq_hz = max_freq_hz if max_freq_hz is not None else (self.sampling_rate / 2.0)
        
        # Kiểm tra tính hợp lệ của dải tần số tìm kiếm
        if self.min_freq_hz >= self.max_freq_hz:
            logger.warning("min_freq_hz lớn hơn hoặc bằng max_freq_hz. Tần số đặc trưng có thể không chính xác.")
        
        logger.info(f"Đã khởi tạo FFTAnalyzer: N_FFT={n_fft_points}, Fs={self.sampling_rate:.2f} Hz, "
                   f"Dải tìm kiếm tần số: [{self.min_freq_hz:.2f} Hz, {self.max_freq_hz:.2f} Hz]")

    def analyze(self, data_segment: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        """
        Thực hiện FFT trên một đoạn dữ liệu và tìm tần số đặc trưng.
        
        Args:
            data_segment (np.ndarray): Đoạn dữ liệu gia tốc (1D array) để phân tích.
                                       Kích thước nên >= self.n_fft_points.
        Returns:
            tuple[np.ndarray, np.ndarray, float]:
                - freqs: Mảng tần số tương ứng.
                - amplitudes: Mảng biên độ phổ.
                - dominant_freq_hz: Tần số có biên độ lớn nhất trong dải cho phép.
                                    Trả về 0.0 nếu không tìm thấy hoặc không đủ dữ liệu.
        """
        if len(data_segment) < self.n_fft_points:
            logger.warning(f"Không đủ dữ liệu cho FFT: {len(data_segment)} mẫu, cần {self.n_fft_points}.")
            return np.array([]), np.array([]), 0.0

        # Lấy N_FFT_POINTS mẫu gần nhất
        segment_for_fft = data_segment[-self.n_fft_points:]

        # Áp dụng cửa sổ Hanning để giảm rò rỉ phổ (spectral leakage)
        hanning_window = windows.hann(self.n_fft_points)
        segment_windowed = segment_for_fft * hanning_window

        # Tính FFT cho tín hiệu thực (Real FFT)
        yf = rfft(segment_windowed)
        # Tính các tần số tương ứng với các bin FFT
        xf = rfftfreq(self.n_fft_points, self.dt_sampling)

        # Tính biên độ phổ (loại bỏ thành phần DC ở xf[0] = 0 Hz)
        # Và chỉ xem xét các tần số dương
        if len(xf) > 1 and len(yf) > 1:
            amplitude_spectrum = np.abs(yf[1:])
            freq_axis = xf[1:]
        else:
            return np.array([]), np.array([]), 0.0

        dominant_freq_hz = 0.0
        if amplitude_spectrum.size > 0:
            # Lọc tần số trong dải cho phép
            valid_indices = np.where((freq_axis >= self.min_freq_hz) & 
                                     (freq_axis <= self.max_freq_hz))
            
            if valid_indices[0].size > 0:
                filtered_amplitudes = amplitude_spectrum[valid_indices]
                filtered_freqs = freq_axis[valid_indices]
                
                if filtered_amplitudes.size > 0:
                    peak_idx_in_filtered = np.argmax(filtered_amplitudes)
                    dominant_freq_hz = filtered_freqs[peak_idx_in_filtered]
                else:
                    logger.debug("Không tìm thấy biên độ nào trong dải tần số hợp lệ.")
            else:
                logger.debug("Không tìm thấy tần số nào trong dải tìm kiếm.")
        else:
            logger.debug("Phổ biên độ trống.")

        return freq_axis, amplitude_spectrum, dominant_freq_hz