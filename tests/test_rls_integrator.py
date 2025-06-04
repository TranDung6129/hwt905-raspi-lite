# tests/test_rls_integrator.py

import pytest
import numpy as np
import logging

# Import lớp cần kiểm thử
from processing.algorithms.rls_integrator import RLSIntegrator

logger = logging.getLogger(__name__)

# --- Test cases cho RLSIntegrator ---
def test_rls_integrator_initialization(sample_dt):
    """Kiểm tra khởi tạo RLSIntegrator."""
    integrator = RLSIntegrator(sample_frame_size=20, calc_frame_multiplier=50, dt=sample_dt, filter_q=0.99)
    assert integrator.sample_frame_size == 20
    assert integrator.calc_frame_multiplier == 50
    assert integrator.calc_frame_size == 1000
    assert integrator.dt == sample_dt
    assert integrator.filter_q == 0.99
    assert np.all(integrator.acc_buffer == 0)
    assert integrator.frame_count == 0

def test_rls_integrator_invalid_params():
    """Kiểm tra khởi tạo với tham số không hợp lệ."""
    with pytest.raises(ValueError, match="dt .* phải lớn hơn 0"):
        RLSIntegrator(dt=0)
    with pytest.raises(ValueError, match="sample_frame_size phải lớn hơn 0"):
        RLSIntegrator(sample_frame_size=0)
    with pytest.raises(ValueError, match="calc_frame_multiplier phải lớn hơn 0"):
        RLSIntegrator(calc_frame_multiplier=0)
    with pytest.raises(ValueError, match="filter_q .* phải nằm trong khoảng"):
        RLSIntegrator(filter_q=0)
    with pytest.raises(ValueError, match="filter_q .* phải nằm trong khoảng"):
        RLSIntegrator(filter_q=1.1)

def test_rls_integrator_warmup(sample_dt):
    """Kiểm tra giai đoạn làm ấm."""
    integrator = RLSIntegrator(sample_frame_size=10, dt=sample_dt)
    integrator.warmup_frames = 3 # Giảm để test nhanh
    
    # Giai đoạn làm ấm, output là 0
    for i in range(integrator.warmup_frames - 1):
        disp, vel, acc_filtered = integrator.process_frame(np.ones(10))
        assert np.all(disp == 0)
        assert np.all(vel == 0)
        # acc_filtered là mảng 0 trong giai đoạn làm ấm chứ không phải acc_frame đầu vào
        assert np.all(acc_filtered == 0)
        assert integrator.frame_count == i + 1

    # Sau khi làm ấm, output sẽ có giá trị
    disp, vel, acc_filtered = integrator.process_frame(np.ones(10))
    assert integrator.frame_count == integrator.warmup_frames
    assert not np.all(disp == 0) # disp và vel phải có giá trị khác 0

def test_rls_integrator_reset(sample_dt):
    """Kiểm tra reset bộ tích hợp."""
    integrator = RLSIntegrator(sample_frame_size=10, dt=sample_dt)
    integrator.process_frame(np.random.rand(10)) # Chạy vài lần
    integrator.process_frame(np.random.rand(10))
    
    assert integrator.frame_count > 0
    assert not np.all(integrator.acc_buffer == 0) # Buffer đã có dữ liệu

    integrator.reset()
    assert integrator.frame_count == 0
    assert np.all(integrator.acc_buffer == 0)
    assert np.all(integrator.theta == 0) # Theta cũng phải reset
    assert np.all(integrator.P == np.eye(2) * 1000) # P cũng reset

def test_rls_integrator_process_static_accel(sample_dt):
    """
    Kiểm tra xử lý gia tốc tĩnh (vd: 0g) sau khi làm ấm.
    Vận tốc và vị trí phải trở về 0 sau khi khử xu hướng.
    """
    integrator = RLSIntegrator(sample_frame_size=20, calc_frame_multiplier=50, dt=sample_dt, filter_q=0.999)
    
    num_frames = integrator.warmup_frames + 20 # Đủ để làm ấm và ổn định
    static_accel_frame = np.zeros(integrator.sample_frame_size) # Giả lập 0g
    
    all_vel = []
    all_disp = []

    for _ in range(num_frames):
        disp, vel, acc_filtered = integrator.process_frame(static_accel_frame)
        if integrator.frame_count >= integrator.warmup_frames:
            all_vel.extend(vel.tolist())
            all_disp.extend(disp.tolist())
            
    # Sau một thời gian, vận tốc và vị trí phải gần 0
    # Sử dụng np.isclose để so sánh số thực
    assert np.all(np.isclose(all_vel[-50:], 0, atol=1e-3)), "Vận tốc không về 0"
    assert np.all(np.isclose(all_disp[-50:], 0, atol=1e-3)), "Vị trí không về 0"

def test_rls_integrator_process_constant_offset_accel(sample_dt):
    """
    Kiểm tra xử lý gia tốc với offset tĩnh (vd: 1g) sau khi làm ấm.
    Vận tốc và vị trí phải vẫn trở về 0 vì RLS khử xu hướng.
    """
    integrator = RLSIntegrator(sample_frame_size=20, calc_frame_multiplier=50, dt=sample_dt, filter_q=0.95)
    
    num_frames = integrator.warmup_frames + 30 # Tăng số lượng frame để có đủ thời gian hội tụ
    # Gia tốc có offset 1g (như trục Z khi đứng yên)
    offset_accel_frame = np.full(integrator.sample_frame_size, 9.80665) 
    
    all_vel = []
    all_disp = []

    for _ in range(num_frames):
        disp, vel, acc_filtered = integrator.process_frame(offset_accel_frame)
        if integrator.frame_count >= integrator.warmup_frames:
            all_vel.extend(vel.tolist())
            all_disp.extend(disp.tolist())
            
    # RLS phải khử được offset này, đưa vận tốc và vị trí về 0
    assert np.all(np.isclose(all_vel[-50:], 0, atol=1e-3)), "Vận tốc không về 0 với offset"
    assert np.all(np.isclose(all_disp[-50:], 0, atol=1e-3)), "Vị trí không về 0 với offset"

def test_rls_integrator_process_event_accel(sample_dt, generate_accel_data):
    """
    Kiểm tra xử lý một sự kiện gia tốc ngắn.
    Vận tốc và vị trí phải thể hiện sự chuyển động tạm thời, sau đó trở về 0.
    """
    integrator = RLSIntegrator(sample_frame_size=20, calc_frame_multiplier=100, dt=sample_dt, filter_q=0.99)
    
    # Tạo dữ liệu gia tốc có một sự kiện
    total_accel_data = generate_accel_data(duration=10.0, peak_accel=5.0, event_duration=1.0) # 10 giây dữ liệu
    
    num_frames = len(total_accel_data) // integrator.sample_frame_size
    
    all_vel = []
    all_disp = []

    for i in range(num_frames):
        start_idx = i * integrator.sample_frame_size
        end_idx = start_idx + integrator.sample_frame_size
        frame = total_accel_data[start_idx:end_idx]
        
        disp, vel, acc_filtered = integrator.process_frame(frame)
        if integrator.frame_count >= integrator.warmup_frames:
            all_vel.extend(vel.tolist())
            all_disp.extend(disp.tolist())
    
    # Vận tốc và vị trí nên có dao động lớn trong sự kiện, sau đó giảm về gần 0
    # Kiểm tra rằng có sự chuyển động đáng kể
    assert np.max(np.abs(all_vel)) > 0.01 # Phải có vận tốc đáng kể
    assert np.max(np.abs(all_disp)) > 0.001 # Phải có li độ đáng kể

    # Kiểm tra rằng vận tốc và vị trí về gần 0 sau sự kiện (cuối dữ liệu)
    # RLS sẽ cố gắng khử xu hướng, đưa chúng về 0
    assert np.all(np.isclose(all_vel[-50:], 0, atol=0.01)), "Vận tốc không về 0 sau sự kiện"
    assert np.all(np.isclose(all_disp[-50:], 0, atol=0.01)), "Vị trí không về 0 sau sự kiện"