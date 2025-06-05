# src/processing/data_filter.py

import numpy as np
import logging
from collections import deque
from typing import Union, List

logger = logging.getLogger(__name__)

class MovingAverageFilter:
    """
    Bộ lọc trung bình động (Moving Average Filter) để làm mịn dữ liệu.
    """
    def __init__(self, window_size: int):
        """
        Khởi tạo bộ lọc trung bình động.

        Args:
            window_size (int): Kích thước cửa sổ (số lượng mẫu) để tính trung bình.
                               Phải lớn hơn 0.
        """
        if not isinstance(window_size, int) or window_size <= 0:
            raise ValueError("Kích thước cửa sổ (window_size) phải là số nguyên dương.")
        self.window_size = window_size
        self.buffer = deque(maxlen=window_size)
        logger.info(f"Đã khởi tạo MovingAverageFilter với window_size={window_size}.")

    def process(self, new_sample: float) -> float:
        """
        Thêm một mẫu mới và trả về giá trị đã lọc (trung bình động).
        Nếu buffer chưa đủ đầy, trả về mẫu gốc hoặc 0 tùy thuộc vào yêu cầu.
        Ở đây, ta sẽ trả về trung bình của các mẫu hiện có trong buffer.

        Args:
            new_sample (float): Mẫu dữ liệu mới.

        Returns:
            float: Giá trị đã được lọc.
        """
        self.buffer.append(new_sample)
        # Tính trung bình của các phần tử hiện có trong buffer
        return sum(self.buffer) / len(self.buffer)

    def reset(self):
        """Xóa bộ đệm của bộ lọc."""
        self.buffer.clear()
        logger.info("MovingAverageFilter đã được reset.")

class LowPassFilter:
    """
    Bộ lọc thông thấp đơn giản (RC Low Pass Filter).
    Thích hợp cho việc làm mịn dữ liệu cảm biến thời gian thực.
    """
    def __init__(self, alpha: float):
        """
        Khởi tạo bộ lọc thông thấp.

        Args:
            alpha (float): Hệ số làm mịn (smoothing factor), nằm trong khoảng [0, 1].
                           alpha càng gần 1, bộ lọc càng ít làm mịn (giữ gần mẫu gốc).
                           alpha càng gần 0, bộ lọc càng làm mịn nhiều (phản ứng chậm với thay đổi).
                           alpha = dt / (RC + dt)
                           RC = time_constant (seconds)
        """
        if not (0 <= alpha <= 1):
            raise ValueError("Hệ số alpha phải nằm trong khoảng [0, 1].")
        self.alpha = alpha
        self.last_filtered_value = 0.0 # Giá trị lọc ban đầu
        self.is_initialized = False
        logger.info(f"Đã khởi tạo LowPassFilter với alpha={alpha}.")

    def process(self, new_sample: float) -> float:
        """
        Thêm một mẫu mới và trả về giá trị đã lọc.

        Args:
            new_sample (float): Mẫu dữ liệu mới.

        Returns:
            float: Giá trị đã được lọc.
        """
        if not self.is_initialized:
            self.last_filtered_value = new_sample
            self.is_initialized = True
        else:
            self.last_filtered_value = self.alpha * new_sample + (1 - self.alpha) * self.last_filtered_value
        return self.last_filtered_value

    def reset(self):
        """Đặt lại trạng thái của bộ lọc."""
        self.last_filtered_value = 0.0
        self.is_initialized = False
        logger.info("LowPassFilter đã được reset.")
