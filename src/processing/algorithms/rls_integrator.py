import numpy as np
import logging

logger = logging.getLogger(__name__)

class RLSIntegrator:
    """
    Tích hợp gia tốc thành vận tốc và vị trí trong thời gian thực
    sử dụng bộ lọc recursive least squares (RLS) để khử nhiễu và trôi dữ liệu.
    Lớp này được thiết kế để xử lý dữ liệu cho MỘT TRỤC.
    """
    
    def __init__(self, sample_frame_size: int = 20, calc_frame_multiplier: int = 100,
                 dt: float = 0.005, filter_q: float = 0.9825):
        """
        Khởi tạo bộ tích hợp gia tốc RLS.
        
        Tham số:
        * sample_frame_size: Số mẫu trong một frame xử lý (batch size cho mỗi lần gọi process_frame).
        * calc_frame_multiplier: Bội số frame tính toán so với sample_frame 
                                 (sử dụng cho buffer nội bộ lớn hơn, nơi RLS áp dụng).
        * dt: Khoảng thời gian giữa các mẫu gia tốc (giây).
        * filter_q: Hệ số quên (forgetting factor) cho bộ lọc RLS, giá trị gần 1 
                   sẽ giảm khả năng phản ứng nhưng tăng độ bền nhiễu.
        """
        if not (0 < filter_q <= 1):
            raise ValueError("filter_q (hệ số quên) phải nằm trong khoảng (0, 1].")
        if dt <= 0:
            raise ValueError("dt (khoảng thời gian giữa các mẫu) phải lớn hơn 0.")
        if sample_frame_size <= 0:
            raise ValueError("sample_frame_size phải lớn hơn 0.")
        if calc_frame_multiplier <= 0:
            raise ValueError("calc_frame_multiplier phải lớn hơn 0.")

        self.sample_frame_size = sample_frame_size
        self.calc_frame_multiplier = calc_frame_multiplier
        self.calc_frame_size = sample_frame_size * calc_frame_multiplier
        self.dt = dt
        self.filter_q = filter_q
        
        # Khởi tạo các buffer tính toán chính 
        self.acc_buffer = np.zeros(self.calc_frame_size)
        self.vel_buffer = np.zeros(self.calc_frame_size)
        self.disp_buffer = np.zeros(self.calc_frame_size)
        
        # Các biến theo dõi trạng thái
        self.frame_count = 0
        
        # Ma trận hiệp phương sai ban đầu cho RLS
        # P0 thường là một ma trận đường chéo lớn để thể hiện sự không chắc chắn ban đầu
        self.P = np.eye(2) * 1000 
        # Bộ lọc ước lượng ban đầu (hệ số a và b trong mô hình y = a*t + b)
        # theta = [slope, intercept]
        self.theta = np.zeros(2) # [0, 0]
        
        # Số lượng frame cần để khởi động
        self.warmup_frames = 5
        
        logger.info(f"Đã khởi tạo RLSIntegrator: dt={dt}, frame_size={sample_frame_size}, "
                   f"calc_buffer_size={self.calc_frame_size}, q={filter_q}")
    
    def reset(self):
        """Đặt lại trạng thái của bộ tích hợp về ban đầu."""
        self.acc_buffer = np.zeros(self.calc_frame_size)
        self.vel_buffer = np.zeros(self.calc_frame_size)
        self.disp_buffer = np.zeros(self.calc_frame_size)
        self.frame_count = 0
        self.P = np.eye(2) * 1000
        self.theta = np.zeros(2)
        logger.info("RLSIntegrator đã được reset.")
        
    def _remove_linear_trend_rls(self, data: np.ndarray, t: np.ndarray) -> np.ndarray:
        """
        Áp dụng bộ lọc RLS để loại bỏ xu hướng tuyến tính khỏi mảng dữ liệu.
        Phương pháp này cập nhật theta và P của đối tượng.
        Args:
            data (np.ndarray): Mảng dữ liệu đầu vào.
            t (np.ndarray): Mảng thời gian tương ứng.
        Returns:
            np.ndarray: Dữ liệu đã được khử xu hướng.
        """
        n = len(data)
        # Tạo bản sao của P và theta để cập nhật nội bộ trong hàm này,
        # sau đó gán lại cho self nếu cần.
        # Hoặc cập nhật trực tiếp self.P, self.theta như ban đầu.
        # Giữ lại cập nhật trực tiếp như cách bạn đã làm.

        # Đảm bảo t và data có cùng kích thước
        if n != len(t):
            raise ValueError("Kích thước mảng data và t phải khớp.")

        # Cập nhật RLS cho từng điểm dữ liệu trong frame hiện tại
        for i in range(n):
            # Tạo vector đầu vào phi: [t, 1] - mô hình tuyến tính y = a*t + b
            phi = np.array([t[i], 1.0])
            
            # Dự đoán giá trị với các thông số hiện tại
            y_pred = np.dot(self.theta, phi)
            
            # Tính toán sai số dự đoán
            e = data[i] - y_pred
            
            # Cập nhật gain vector k
            # k = P*phi / (q + phi^T * P * phi)
            P_phi = np.dot(self.P, phi)
            denom = self.filter_q + np.dot(phi, P_phi)
            
            # Tránh chia cho 0 hoặc giá trị rất nhỏ
            if denom == 0:
                logger.warning("RLS: Mẫu số bằng 0. Bỏ qua cập nhật RLS cho điểm này.")
                continue
            k = P_phi / denom
            
            # Cập nhật các tham số theta
            # theta = theta + k * e
            self.theta = self.theta + k * e
            
            # Cập nhật ma trận hiệp phương sai P
            # P = (P - k*phi^T*P) / q
            self.P = (self.P - np.outer(k, np.dot(phi, self.P))) / self.filter_q
        
        # Tính toán xu hướng dựa trên theta cuối cùng của frame
        trend = np.zeros_like(data)
        for i in range(n):
            trend[i] = np.dot(self.theta, [t[i], 1.0])
        
        return data - trend # Trả về tín hiệu đã khử xu hướng
    
    def process_frame(self, acc_frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Xử lý một frame gia tốc mới và trả về vị trí, vận tốc và gia tốc đã lọc.
        Dữ liệu trả về chỉ tương ứng với frame đầu vào.

        Args:
            acc_frame (np.ndarray): Mảng gia tốc 1D cho frame hiện tại.

        Returns:
            tuple[np.ndarray, np.ndarray, np.ndarray]: (disp_filtered, vel_filtered, acc_filtered)
            Các mảng numpy chứa li độ, vận tốc và gia tốc đã được lọc/tích hợp,
            tương ứng với kích thước của acc_frame đầu vào.
        """
        frame_len = len(acc_frame)
        if frame_len == 0:
            return np.array([]), np.array([]), np.array([])
            
        if frame_len > self.sample_frame_size:
            logger.warning(f"Kích thước frame ({frame_len}) lớn hơn sample_frame_size ({self.sample_frame_size}). Sẽ cắt bớt.")
            acc_frame = acc_frame[:self.sample_frame_size]
            frame_len = self.sample_frame_size
            
        self.frame_count += 1
            
        # Cập nhật buffer gia tốc chung
        self.acc_buffer = np.roll(self.acc_buffer, -frame_len) # Dịch buffer
        self.acc_buffer[-frame_len:] = acc_frame # Thêm dữ liệu mới vào cuối
        
        # Chỉ xử lý khi có đủ dữ liệu để "làm ấm" bộ lọc RLS
        # Để đảm bảo P và theta hội tụ đủ tốt trước khi tin cậy kết quả
        if self.frame_count < self.warmup_frames:
            logger.debug(f"RLS Integrator đang làm ấm: Frame {self.frame_count}/{self.warmup_frames}")
            # Trong giai đoạn làm ấm, trả về 0 hoặc NaN
            return np.zeros(frame_len), np.zeros(frame_len), np.zeros(frame_len) # Trả về 0 để không ảnh hưởng plot ban đầu

        # Tính toán thời gian cho toàn bộ buffer tính toán
        t_buffer = np.arange(0, self.calc_frame_size * self.dt, self.dt)
        
        # Tích phân gia tốc thô từ buffer thành vận tốc
        # (initial velocity is implicitly 0 at start of buffer)
        vel_raw_buffer = np.zeros_like(self.acc_buffer)
        for i in range(1, self.calc_frame_size):
            vel_raw_buffer[i] = vel_raw_buffer[i-1] + (self.acc_buffer[i-1] + self.acc_buffer[i]) * self.dt / 2
        
        # Loại bỏ xu hướng tuyến tính khỏi vận tốc bằng RLS
        vel_detrended_buffer = self._remove_linear_trend_rls(vel_raw_buffer, t_buffer)
        
        # Tích phân vận tốc đã khử xu hướng thành vị trí
        disp_raw_buffer = np.zeros_like(vel_detrended_buffer)
        for i in range(1, self.calc_frame_size):
            disp_raw_buffer[i] = disp_raw_buffer[i-1] + (vel_detrended_buffer[i-1] + vel_detrended_buffer[i]) * self.dt / 2
        
        # Loại bỏ xu hướng tuyến tính khỏi vị trí bằng RLS
        disp_detrended_buffer = self._remove_linear_trend_rls(disp_raw_buffer, t_buffer)
        
        # Gia tốc đã lọc (nếu có cần) có thể là gia tốc đã khử DC/drift ban đầu
        # Trong RLS, gia tốc thường không được lọc trực tiếp mà thông qua việc khử xu hướng trên vel/disp
        # Để đơn giản, ta có thể coi gia tốc "lọc" là gia tốc thô trừ đi offset/trend trung bình
        # Hoặc giữ acc_frame ban đầu là acc_filtered nếu không áp dụng lọc trực tiếp trên acc.
        # Ở đây, tôi sẽ trả về acc_frame ban đầu vì RLS tập trung vào vel/disp.
        # Nếu muốn lọc acc, cần thêm một bước lọc riêng biệt trước RLS.
        acc_filtered = acc_frame # Coi gia tốc đầu vào là gia tốc đã "lọc"
        
        # Trả về chỉ phần dữ liệu mới nhất tương ứng với frame đầu vào
        return disp_detrended_buffer[-frame_len:], \
               vel_detrended_buffer[-frame_len:], \
               acc_filtered