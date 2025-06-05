"""
Module xử lý cấu trúc MQTT Message theo config
"""
import json
import time
import copy
from typing import Dict, List, Any, Optional
import logging

class MQTTMessageBuilder:
    """
    Lớp xây dựng message MQTT theo cấu trúc đã định nghĩa trong config
    """
    
    def __init__(self, config_file_path: str = "config/mqtt_message_config.json"):
        """
        Khởi tạo MessageBuilder với file config
        
        Args:
            config_file_path: Đường dẫn đến file config cấu trúc message
        """
        self.logger = logging.getLogger(__name__)
        self.config_file_path = config_file_path
        self.message_config = self._load_message_config()
        
    def _load_message_config(self) -> Dict[str, Any]:
        """Tải cấu hình cấu trúc message từ file JSON"""
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger.debug(f"Đã tải cấu hình message từ {self.config_file_path}")
                return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Lỗi tải cấu hình message: {e}")
            # Trả về cấu hình mặc định
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Trả về cấu hình mặc định nếu không tải được file config"""
        return {
            "message_templates": {
                "batch": {
                    "structure": {
                        "metadata": {
                            "source": "HWT905_RasPi",
                            "strategy": "batch",
                            "sample_count": 0,
                            "start_time": 0.0,
                            "end_time": 0.0
                        },
                        "data_points": []
                    }
                },
                "continuous": {
                    "structure": {
                        "metadata": {
                            "source": "HWT905_RasPi", 
                            "strategy": "continuous",
                            "sample_count": 1,
                            "start_time": 0.0,
                            "end_time": 0.0
                        },
                        "data_points": []
                    }
                },
                "batch_average": {
                    "structure": {
                        "metadata": {
                            "source": "HWT905_RasPi",
                            "strategy": "batch_average",
                            "original_sample_count": 0,
                            "start_time": 0.0,
                            "end_time": 0.0
                        },
                        "data_averaged": {}
                    }
                }
            }
        }
    
    def create_data_point(self, processed_results: Dict[str, Any], current_timestamp: float) -> Dict[str, Any]:
        """
        Tạo một data point từ kết quả xử lý
        
        Args:
            processed_results: Kết quả từ sensor_data_processor
            current_timestamp: Timestamp hiện tại
            
        Returns:
            Dict chứa data point đã được format
        """
        return {
            "ts": current_timestamp,
            "acc_x_filtered": processed_results["acc_x_filtered"][-1] if processed_results["acc_x_filtered"].size > 0 else 0,
            "acc_y_filtered": processed_results["acc_y_filtered"][-1] if processed_results["acc_y_filtered"].size > 0 else 0,
            "acc_z_filtered": processed_results["acc_z_filtered"][-1] if processed_results["acc_z_filtered"].size > 0 else 0,
            "vel_x": processed_results["vel_x"][-1] if processed_results["vel_x"].size > 0 else 0,
            "vel_y": processed_results["vel_y"][-1] if processed_results["vel_y"].size > 0 else 0,
            "vel_z": processed_results["vel_z"][-1] if processed_results["vel_z"].size > 0 else 0,
            "disp_x": processed_results["disp_x"][-1] if processed_results["disp_x"].size > 0 else 0,
            "disp_y": processed_results["disp_y"][-1] if processed_results["disp_y"].size > 0 else 0,
            "disp_z": processed_results["disp_z"][-1] if processed_results["disp_z"].size > 0 else 0,
            "dominant_freq_x": processed_results.get("dominant_freq_x", 0),
            "dominant_freq_y": processed_results.get("dominant_freq_y", 0),
            "dominant_freq_z": processed_results.get("dominant_freq_z", 0),
        }
    
    def build_batch_message(self, data_buffer: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Xây dựng message cho strategy 'batch'
        
        Args:
            data_buffer: List các data points
            
        Returns:
            Dict chứa message đã được format
        """
        if not data_buffer:
            return {}
            
        template = copy.deepcopy(self.message_config["message_templates"]["batch"]["structure"])
        
        template["metadata"]["sample_count"] = len(data_buffer)
        template["metadata"]["start_time"] = data_buffer[0]["ts"]
        template["metadata"]["end_time"] = data_buffer[-1]["ts"]
        template["data_points"] = list(data_buffer)
        
        return template
    
    def build_continuous_message(self, data_buffer: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Xây dựng message cho strategy 'continuous'
        
        Args:
            data_buffer: List các data points (thường chỉ có 1 phần tử)
            
        Returns:
            Dict chứa message đã được format
        """
        if not data_buffer:
            return {}
            
        template = copy.deepcopy(self.message_config["message_templates"]["continuous"]["structure"])
        
        template["metadata"]["sample_count"] = len(data_buffer)
        template["metadata"]["start_time"] = data_buffer[0]["ts"]
        template["metadata"]["end_time"] = data_buffer[-1]["ts"]
        template["data_points"] = list(data_buffer)
        
        return template
    
    def build_batch_average_message(self, data_buffer: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Xây dựng message cho strategy 'batch_average'
        
        Args:
            data_buffer: List các data points để tính trung bình
            
        Returns:
            Dict chứa message đã được format với dữ liệu trung bình
        """
        if not data_buffer:
            return {}
            
        template = copy.deepcopy(self.message_config["message_templates"]["batch_average"]["structure"])
        num_points = len(data_buffer)
        
        # Tính trung bình
        avg_data_point = {
            "ts": data_buffer[-1]["ts"],  # Timestamp của điểm cuối cùng
            "acc_x_filtered": sum(p["acc_x_filtered"] for p in data_buffer) / num_points,
            "acc_y_filtered": sum(p["acc_y_filtered"] for p in data_buffer) / num_points,
            "acc_z_filtered": sum(p["acc_z_filtered"] for p in data_buffer) / num_points,
            "vel_x": sum(p["vel_x"] for p in data_buffer) / num_points,
            "vel_y": sum(p["vel_y"] for p in data_buffer) / num_points,
            "vel_z": sum(p["vel_z"] for p in data_buffer) / num_points,
            "disp_x": sum(p["disp_x"] for p in data_buffer) / num_points,
            "disp_y": sum(p["disp_y"] for p in data_buffer) / num_points,
            "disp_z": sum(p["disp_z"] for p in data_buffer) / num_points,
            "dominant_freq_x": data_buffer[-1]["dominant_freq_x"],  # Lấy từ điểm cuối
            "dominant_freq_y": data_buffer[-1]["dominant_freq_y"],
            "dominant_freq_z": data_buffer[-1]["dominant_freq_z"],
        }
        
        template["metadata"]["original_sample_count"] = num_points
        template["metadata"]["start_time"] = data_buffer[0]["ts"]
        template["metadata"]["end_time"] = data_buffer[-1]["ts"]
        template["data_averaged"] = avg_data_point
        
        return template
    
    def build_message(self, strategy: str, data_buffer: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Xây dựng message theo strategy đã chọn
        
        Args:
            strategy: Chiến lược gửi ('batch', 'continuous', 'batch_average')
            data_buffer: List các data points
            
        Returns:
            Dict chứa message đã được format, hoặc None nếu có lỗi
        """
        try:
            if strategy == "batch":
                return self.build_batch_message(data_buffer)
            elif strategy == "continuous":
                return self.build_continuous_message(data_buffer)
            elif strategy == "batch_average":
                return self.build_batch_average_message(data_buffer)
            else:
                self.logger.warning(f"Strategy không hợp lệ: {strategy}, sử dụng 'batch' mặc định")
                return self.build_batch_message(data_buffer)
        except Exception as e:
            self.logger.error(f"Lỗi khi xây dựng message: {e}")
            return None
