# src/processing/data_processor.py

import numpy as np
import logging
import time
from collections import deque
from typing import Dict, Any, Optional

from .algorithms.rls_integrator import RLSIntegrator
from .algorithms.fft_analyzer import FFTAnalyzer
from .data_filter import MovingAverageFilter, LowPassFilter
from .data_storage import StorageManager

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
                 fft_n_points: int = 512, fft_min_freq_hz: float = 0.1, fft_max_freq_hz: float = None,
                 storage_config: Optional[Dict[str, Any]] = None):
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
            storage_config (Dict): Cấu hình cho hệ thống lưu trữ dữ liệu.
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
        
        # Khởi tạo storage manager
        if storage_config is None:
            storage_config = {"enabled": False}
        
        self.storage_manager = StorageManager(storage_config)
        
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
            disp_x, vel_x, acc_x_rls_output = self.integrator_x.process_frame(frame_x)
            disp_y, vel_y, acc_y_rls_output = self.integrator_y.process_frame(frame_y)
            disp_z, vel_z, acc_z_rls_output = self.integrator_z.process_frame(frame_z)

            # Kiểm tra xem RLS đã đủ làm ấm chưa
            rls_warmed_up = self.integrator_x.frame_count >= self.integrator_x.warmup_frames

            processed_output = {
                "acc_x_filtered": acc_x_rls_output, # Đây là acc_frame đã được truyền vào RLS
                "acc_y_filtered": acc_y_rls_output,
                "acc_z_filtered": acc_z_rls_output,
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

                processed_output.update({
                    "fft_x_freqs": freqs_x, "fft_x_amps": amps_x, "dominant_freq_x": dom_freq_x,
                    "fft_y_freqs": freqs_y, "fft_y_amps": amps_y, "dominant_freq_y": dom_freq_y,
                    "fft_z_freqs": freqs_z, "fft_z_amps": amps_z, "dominant_freq_z": dom_freq_z
                })
            else:
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
            
            # Lưu trữ và chuẩn bị dữ liệu để truyền
            current_timestamp = time.time()
            transmission_data = self.storage_manager.store_and_prepare_for_transmission(
                processed_output, current_timestamp
            )
            
            return transmission_data

        return processed_output

    def _calculate_displacement_magnitude(self, processed_data: Dict[str, Any]) -> float:
        """Tính độ lớn tổng hợp của displacement."""
        disp_x = processed_data.get('disp_x', 0)
        disp_y = processed_data.get('disp_y', 0)
        disp_z = processed_data.get('disp_z', 0)
        
        return (disp_x**2 + disp_y**2 + disp_z**2)**0.5
    
    def _calculate_overall_dominant_frequency(self, processed_data: Dict[str, Any]) -> float:
        """Tính tần số dominant tổng hợp từ 3 trục."""
        freq_x = processed_data.get('dominant_freq_x', 0)
        freq_y = processed_data.get('dominant_freq_y', 0)
        freq_z = processed_data.get('dominant_freq_z', 0)
        
        # Trả về tần số có giá trị lớn nhất (có thể cải thiện thuật toán này)
        return max(freq_x, freq_y, freq_z)
    
    def get_batch_for_transmission(self) -> list:
        """
        Lấy một batch dữ liệu từ storage để truyền đi trong trường hợp kết nối gián đoạn.
        
        Returns:
            Danh sách dữ liệu cần truyền
        """
        return self.storage_manager.get_batch_for_transmission()
    
    def close(self):
        """Đóng processor và dọn dẹp tài nguyên."""
        self.storage_manager.close()
        logger.info("SensorDataProcessor closed")