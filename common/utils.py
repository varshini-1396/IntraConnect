"""
Utility functions shared between client and server
"""

import socket
import time
from datetime import datetime

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_timestamp():
    """Get current timestamp as formatted string"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def compress_frame(frame, quality=50):
    """Compress image frame for transmission"""
    import cv2
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    result, encoded_img = cv2.imencode('.jpg', frame, encode_param)
    return encoded_img.tobytes() if result else None

def decompress_frame(data):
    """Decompress received frame data"""
    import cv2
    import numpy as np
    nparr = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return frame