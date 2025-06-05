"""
Decoder cho GPS related packets
"""
from typing import Dict, Any
from .base_decoder import BasePacketDecoder
from ..hwt905_constants import (
    PACKET_TYPE_GPS_LONLAT, PACKET_TYPE_GPS_SPEED, PACKET_TYPE_GPS_ACCURACY,
    SCALE_GPS_SPEED, SCALE_GPS_ALTITUDE, SCALE_GPS_ACCURACY
)

class GPSLonLatPacketDecoder(BasePacketDecoder):
    """Decoder cho GPS longitude/latitude packet (0x57)"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_GPS_LONLAT
    
    def get_packet_name(self) -> str:
        return "GPS_LON_LAT"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin vĩ độ và kinh độ GPS (0x57)."""
        if len(payload) < 8:
            raise ValueError(f"GPS LonLat packet payload quá ngắn: {len(payload)} bytes")
            
        # Kinh độ là 32-bit (Lon0 Lon1 Lon2 Lon3)
        longitude_raw = self.bytes_to_uint32(payload[0], payload[1], payload[2], payload[3])
        # Vĩ độ là 32-bit (Lat0 Lat1 Lat2 Lat3)
        latitude_raw = self.bytes_to_uint32(payload[4], payload[5], payload[6], payload[7])
        
        # WitMotion thường dùng định dạng decimal degrees * 10^7
        longitude = longitude_raw / 10_000_000.0
        latitude = latitude_raw / 10_000_000.0

        return {
            "gps_longitude": longitude,
            "gps_latitude": latitude
        }

class GPSSpeedPacketDecoder(BasePacketDecoder):
    """Decoder cho GPS speed packet (0x58)"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_GPS_SPEED
    
    def get_packet_name(self) -> str:
        return "GPS_SPEED"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin tốc độ GPS (0x58)."""
        if len(payload) < 8:
            raise ValueError(f"GPS Speed packet payload quá ngắn: {len(payload)} bytes")
            
        # Tốc độ mặt đất là 32-bit (GPSV0 GPSV1 GPSV2 GPSV3)
        gps_ground_speed_raw = self.bytes_to_uint32(payload[0], payload[1], payload[2], payload[3])
        gps_ground_speed = gps_ground_speed_raw / SCALE_GPS_SPEED # (km/h)
        
        # GPS Altitude (m)
        gps_altitude_raw = self.bytes_to_short(payload[4], payload[5])
        gps_altitude = gps_altitude_raw / SCALE_GPS_ALTITUDE # (m)
        
        # GPS Heading (deg)
        gps_heading_raw = self.bytes_to_short(payload[6], payload[7])
        gps_heading = gps_heading_raw / 100.0 # Divide by 100 for heading
        
        return {
            "gps_ground_speed": gps_ground_speed,
            "gps_altitude": gps_altitude,
            "gps_heading": gps_heading
        }

class GPSAccuracyPacketDecoder(BasePacketDecoder):
    """Decoder cho GPS accuracy packet (0x5A)"""
    
    def get_packet_type(self) -> int:
        return PACKET_TYPE_GPS_ACCURACY
    
    def get_packet_name(self) -> str:
        return "GPS_ACCURACY"
    
    def decode(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin độ chính xác GPS (0x5A)."""
        if len(payload) < 8:
            raise ValueError(f"GPS Accuracy packet payload quá ngắn: {len(payload)} bytes")
            
        num_satellites = self.bytes_to_short(payload[0], payload[1]) # SVNUM
        pdop_raw = self.bytes_to_short(payload[2], payload[3]) # PDOP
        hdop_raw = self.bytes_to_short(payload[4], payload[5]) # HDOP
        vdop_raw = self.bytes_to_short(payload[6], payload[7]) # VDOP

        pdop = pdop_raw / SCALE_GPS_ACCURACY
        hdop = hdop_raw / SCALE_GPS_ACCURACY
        vdop = vdop_raw / SCALE_GPS_ACCURACY

        return {
            "gps_num_satellites": num_satellites,
            "gps_pdop": pdop,
            "gps_hdop": hdop,
            "gps_vdop": vdop
        }
