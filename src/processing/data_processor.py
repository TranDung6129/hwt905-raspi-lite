# src/processing/data_processor.py

import numpy as np
import logging
import time
from collections import deque
from typing import Dict, Any, Optional

from .algorithms.rls_integrator import RLSIntegrator
from .algorithms.fft_analyzer import FFTAnalyzer
from .data_filter import MovingAverageFilter, LowPassFilter

logger = logging.getLogger(__name__)

class SensorDataProcessor:
    """
    Lớp điều phối việc xử lý dữ liệu gia tốc từ cảm biến với khả năng lưu trữ.
    Bao gồm tiền xử lý, lọc (data_filter), tích hợp gia tốc (algorithm/rls_integrator),
    phân tích FFT (algorithm/fft_analyzer), và lưu trữ dữ liệu.
    Tách biệt việc tính toán và truyền dữ liệu để hỗ trợ môi trường kết nối gián đoạn.
    """
    
    def __init__(self, dt_sensor: float, gravity_g: float,
                 acc_filter_type: Optional[str] = None, acc_filter_param: Optional[Any] = None,
                 rls_sample_frame_size: int = 20, rls_calc_frame_multiplier: int = 100,
                 rls_filter_q: float = 0.9825,
                 fft_n_points: int = 512, fft_min_freq_hz: float = 0.1, fft_max_freq_hz: float = None):
        """
        Khởi tạo SensorDataProcessor.
        
        Args:
            dt_sensor (float): Khoảng thời gian lấy mẫu của cảm biến (giây).
            gravity_g (float): Giá trị gia tốc trọng trường (m/s^2) để chuyển đổi từ g.
            acc_filter_type (str): Loại bộ lọc gia tốc ban đầu ('moving_average', 'low_pass', None).
            acc_filter_param (Any): Tham số cho bộ lọc gia tốc (window_size cho MA, alpha cho LP).
            rls_sample_frame_size (int): Số mẫu cho mỗi frame xử lý của RLS.
            rls_calc_frame_multiplier (int): Bội số frame cho buffer RLS.
            rls_filter_q (float): Hệ số quên RLS.
            fft_n_points (int): Số điểm cho mỗi lần tính FFT.
            fft_min_freq_hz (float): Tần số thấp nhất cho FFT.
            fft_max_freq_hz (float): Tần số cao nhất cho FFT.
        """
        self.dt_sensor = dt_sensor
        self.gravity_g = gravity_g

        # Khởi tạo bộ lọc gia tốc ban đầu (nếu có)
        self.acc_filters = {
            'x': self._create_acc_filter(acc_filter_type, acc_filter_param),
            'y': self._create_acc_filter(acc_filter_type, acc_filter_param),
            'z': self._create_acc_filter(acc_filter_type, acc_filter_param)
        }
        
        # Khởi tạo các bộ tích hợp RLS cho mỗi trục
        self.integrator_x = RLSIntegrator(
            sample_frame_size=rls_sample_frame_size,
            calc_frame_multiplier=rls_calc_frame_multiplier,
            dt=self.dt_sensor,
            filter_q=rls_filter_q
        )
        self.integrator_y = RLSIntegrator(
            sample_frame_size=rls_sample_frame_size,
            calc_frame_multiplier=rls_calc_frame_multiplier,
            dt=self.dt_sensor,
            filter_q=rls_filter_q
        )
        self.integrator_z = RLSIntegrator(
            sample_frame_size=rls_sample_frame_size,
            calc_frame_multiplier=rls_calc_frame_multiplier,
            dt=self.dt_sensor,
            filter_q=rls_filter_q
        )

        # Khởi tạo bộ phân tích FFT
        self.fft_analyzer = FFTAnalyzer(
            n_fft_points=fft_n_points,
            dt_sampling=self.dt_sensor,
            min_freq_hz=fft_min_freq_hz,
            max_freq_hz=fft_max_freq_hz
        )

        # Buffer cho dữ liệu gia tốc thô (đã chuyển đổi sang m/s^2) để cấp cho RLS và FFT
        # Maxlen đủ lớn để chứa dữ liệu cho FFT và RLS buffers
        max_buffer_len = max(
            fft_n_points * 2, # Cho FFT (thường cần 2*N_FFT để xử lý chồng lấp)
            rls_sample_frame_size * rls_calc_frame_multiplier # Cho RLS
        )
        self.acc_raw_buffer_x = deque(maxlen=max_buffer_len)
        self.acc_raw_buffer_y = deque(maxlen=max_buffer_len)
        self.acc_raw_buffer_z = deque(maxlen=max_buffer_len)

        self.rls_sample_frame_size = rls_sample_frame_size # Kích thước frame RLS cho process_new_sample
        
        logger.info(f"SensorDataProcessor đã khởi tạo với dt_sensor={self.dt_sensor}, gravity_g={self.gravity_g}.")

    def _create_acc_filter(self, filter_type: Optional[str], filter_param: Optional[Any]):
        """Hàm trợ giúp để tạo instance bộ lọc."""
        if filter_type == "moving_average":
            return MovingAverageFilter(window_size=filter_param)
        elif filter_type == "low_pass":
            return LowPassFilter(alpha=filter_param)
        return None # Không có bộ lọc

    def reset(self):
        """Đặt lại tất cả các bộ tích hợp, bộ lọc và buffer."""
        for filter_instance in self.acc_filters.values():
            if filter_instance:
                filter_instance.reset()
        self.integrator_x.reset()
        self.integrator_y.reset()
        self.integrator_z.reset()
        self.acc_raw_buffer_x.clear()
        self.acc_raw_buffer_y.clear()
        self.acc_raw_buffer_z.clear()
        logger.info("SensorDataProcessor đã được reset.")

    def process_new_sample(self, acc_x_g: float, acc_y_g: float, acc_z_g: float) -> Optional[Dict[str, Any]]:
        """
        Xử lý một mẫu gia tốc mới (đã nhận từ cảm biến) với khả năng lưu trữ.
        
        Args:
            acc_x_g (float): Gia tốc trục X (đơn vị g).
            acc_y_g (float): Gia tốc trục Y (đơn vị g).
            acc_z_g (float): Gia tốc trục Z (đơn vị g).
            
        Returns:
            Optional[Dict[str, Any]]: Một dictionary chứa dữ liệu đã xử lý
            (gia tốc lọc, vận tốc, li độ) và kết quả FFT nếu đủ dữ liệu.
            Trả về dữ liệu để truyền ngay (nếu immediate_transmission=True),
            None nếu chỉ lưu trữ mà không truyền ngay hoặc chưa đủ dữ liệu để xử lý.
        """
        # 1. Tiền xử lý dữ liệu gia tốc thô và áp dụng bộ lọc ban đầu
        acc_x_ms2_raw = acc_x_g * self.gravity_g
        acc_y_ms2_raw = acc_y_g * self.gravity_g
        # Hiệu chỉnh offset Z cơ bản (trừ đi 1g trọng lực khi cảm biến đứng yên)
        acc_z_ms2_raw = (acc_z_g - 1.0) * self.gravity_g 

        # Áp dụng bộ lọc sơ bộ nếu có
        acc_x_filtered_pre = self.acc_filters['x'].process(acc_x_ms2_raw) if self.acc_filters['x'] else acc_x_ms2_raw
        acc_y_filtered_pre = self.acc_filters['y'].process(acc_y_ms2_raw) if self.acc_filters['y'] else acc_y_ms2_raw
        acc_z_filtered_pre = self.acc_filters['z'].process(acc_z_ms2_raw) if self.acc_filters['z'] else acc_z_ms2_raw

        # Thêm mẫu đã lọc sơ bộ vào các buffer thô để cấp cho RLS và FFT
        self.acc_raw_buffer_x.append(acc_x_filtered_pre)
        self.acc_raw_buffer_y.append(acc_y_filtered_pre)
        self.acc_raw_buffer_z.append(acc_z_filtered_pre)
        
        processed_output = None
        
        # 2. Xử lý tích hợp RLS khi đủ một frame (batch) gia tốc
        if len(self.acc_raw_buffer_x) >= self.rls_sample_frame_size:
            # Lấy một frame gia tốc để xử lý (chính xác là từ cuối buffer)
            frame_x = np.array(list(self.acc_raw_buffer_x)[-self.rls_sample_frame_size:])
            frame_y = np.array(list(self.acc_raw_buffer_y)[-self.rls_sample_frame_size:])
            frame_z = np.array(list(self.acc_raw_buffer_z)[-self.rls_sample_frame_size:])
            
            # Xử lý frame gia tốc qua các bộ tích hợp RLS
            disp_x_array, vel_x_array, acc_x_rls_output = self.integrator_x.process_frame(frame_x)
            disp_y_array, vel_y_array, acc_y_rls_output = self.integrator_y.process_frame(frame_y)
            disp_z_array, vel_z_array, acc_z_rls_output = self.integrator_z.process_frame(frame_z)

            # Lấy giá trị cuối cùng (scalar) từ arrays để lưu trữ
            disp_x = float(disp_x_array[-1]) if len(disp_x_array) > 0 else 0.0
            disp_y = float(disp_y_array[-1]) if len(disp_y_array) > 0 else 0.0
            disp_z = float(disp_z_array[-1]) if len(disp_z_array) > 0 else 0.0
            
            vel_x = float(vel_x_array[-1]) if len(vel_x_array) > 0 else 0.0
            vel_y = float(vel_y_array[-1]) if len(vel_y_array) > 0 else 0.0
            vel_z = float(vel_z_array[-1]) if len(vel_z_array) > 0 else 0.0

            # Kiểm tra xem RLS đã đủ làm ấm chưa
            rls_warmed_up = self.integrator_x.frame_count >= self.integrator_x.warmup_frames

            processed_output = {
                # Chỉ lấy giá trị gia tốc cuối cùng tương ứng với thời điểm tính toán
                "acc_x_filtered": float(acc_x_rls_output[-1]) if len(acc_x_rls_output) > 0 else 0.0,
                "acc_y_filtered": float(acc_y_rls_output[-1]) if len(acc_y_rls_output) > 0 else 0.0,
                "acc_z_filtered": float(acc_z_rls_output[-1]) if len(acc_z_rls_output) > 0 else 0.0,
                "vel_x": vel_x,
                "vel_y": vel_y,
                "vel_z": vel_z,
                "disp_x": disp_x,
                "disp_y": disp_y,
                "disp_z": disp_z,
                "rls_warmed_up": rls_warmed_up
            }

            # 3. Phân tích FFT khi có đủ dữ liệu trong buffer thô
            # acc_raw_buffer_x.maxlen là đủ lớn cho FFT (ví dụ 2*N_FFT_POINTS)
            if len(self.acc_raw_buffer_x) >= self.fft_analyzer.n_fft_points:
                # Lấy dữ liệu để tính FFT (toàn bộ buffer hiện có)
                fft_segment_x = np.array(list(self.acc_raw_buffer_x))
                fft_segment_y = np.array(list(self.acc_raw_buffer_y))
                fft_segment_z = np.array(list(self.acc_raw_buffer_z))

                # Thực hiện phân tích FFT
                freqs_x, amps_x, dom_freq_x = self.fft_analyzer.analyze(fft_segment_x)
                freqs_y, amps_y, dom_freq_y = self.fft_analyzer.analyze(fft_segment_y)
                freqs_z, amps_z, dom_freq_z = self.fft_analyzer.analyze(fft_segment_z)

                # Chỉ cập nhật các giá trị tần số chủ đạo, không gửi toàn bộ mảng FFT
                processed_output.update({
                    "dominant_freq_x": dom_freq_x,
                    "dominant_freq_y": dom_freq_y,
                    "dominant_freq_z": dom_freq_z
                })
            else:
                # Nếu không đủ dữ liệu FFT, trả về giá trị mặc định
                processed_output.update({
                    "dominant_freq_x": 0.0,
                    "dominant_freq_y": 0.0,
                    "dominant_freq_z": 0.0
                })
                logger.debug(f"Chưa đủ dữ liệu cho FFT ({len(self.acc_raw_buffer_x)}/{self.fft_analyzer.n_fft_points} mẫu).")
        else:
            logger.debug(f"Chưa đủ dữ liệu cho RLS Integrator ({len(self.acc_raw_buffer_x)}/{self.rls_sample_frame_size} mẫu).")

        # Enhanced processing: Add storage capabilities and prepare for transmission
        if processed_output is not None:
            # Thêm thông tin gia tốc gốc vào kết quả
            processed_output.update({
                'acc_x': acc_x_g,
                'acc_y': acc_y_g,
                'acc_z': acc_z_g,
                'displacement_magnitude': self._calculate_displacement_magnitude(processed_output),
                'overall_dominant_frequency': self._calculate_overall_dominant_frequency(processed_output)
            })
            
            return processed_output

        return None

    def _calculate_displacement_magnitude(self, processed_data: Dict[str, Any]) -> float:
        """Tính độ lớn tổng hợp của displacement."""
        disp_x = processed_data.get('disp_x', 0)
        disp_y = processed_data.get('disp_y', 0)
        disp_z = processed_data.get('disp_z', 0)
        
        # Đảm bảo là scalar values
        if hasattr(disp_x, '__len__') and len(disp_x) > 0:
            disp_x = float(disp_x[-1]) if len(disp_x) > 0 else 0.0
        elif hasattr(disp_x, '__len__'):
            disp_x = 0.0
        else:
            disp_x = float(disp_x)
            
        if hasattr(disp_y, '__len__') and len(disp_y) > 0:
            disp_y = float(disp_y[-1]) if len(disp_y) > 0 else 0.0
        elif hasattr(disp_y, '__len__'):
            disp_y = 0.0
        else:
            disp_y = float(disp_y)
            
        if hasattr(disp_z, '__len__') and len(disp_z) > 0:
            disp_z = float(disp_z[-1]) if len(disp_z) > 0 else 0.0
        elif hasattr(disp_z, '__len__'):
            disp_z = 0.0
        else:
            disp_z = float(disp_z)
        
        return np.sqrt(disp_x**2 + disp_y**2 + disp_z**2)
    
    def _calculate_overall_dominant_frequency(self, processed_data: Dict[str, Any]) -> float:
        """Tính tần số trội chung."""
        dom_freq_x = processed_data.get('dominant_freq_x', 0)
        dom_freq_y = processed_data.get('dominant_freq_y', 0)
        dom_freq_z = processed_data.get('dominant_freq_z', 0)
        return max(dom_freq_x, dom_freq_y, dom_freq_z)

    def close(self):
        """Dọn dẹp tài nguyên khi đóng."""
        logger.info("Closing SensorDataProcessor.")
        # Không cần làm gì thêm ở đây trừ khi có tài nguyên cần giải phóng
        pass