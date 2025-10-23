"""
Video Capture Module
Handles webcam capture and video display
"""

import cv2
import threading
import socket
import struct
import numpy as np
from tkinter import Canvas
from PIL import Image, ImageTk
import sys
sys.path.append('..')
from common.config import VIDEO_PORT, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_QUALITY, BUFFER_SIZE
from common.utils import compress_frame, decompress_frame

class VideoCapture:
    def __init__(self, username):
        self.username = username
        self.capture = None
        self.running = False
        self.video_socket = None
        self.server_address = None
        self.local_frame = None
        self.remote_frames = {}  # {username: frame}
        self.lock = threading.Lock()
        
    def start_capture(self, server_ip):
        """Start capturing and sending video"""
        try:
            self.capture = cv2.VideoCapture(0)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
            self.capture.set(cv2.CAP_PROP_FPS, VIDEO_FPS)
            
            # Create UDP socket for video
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.video_socket.bind(('0.0.0.0', VIDEO_PORT))
            self.server_address = (server_ip, VIDEO_PORT)
            
            self.running = True
            
            # Start capture thread
            threading.Thread(target=self.capture_thread, daemon=True).start()
            # Start receive thread
            threading.Thread(target=self.receive_thread, daemon=True).start()
            
            print("[VIDEO] Video capture started")
            return True
            
        except Exception as e:
            print(f"[VIDEO] Failed to start capture: {e}")
            return False
    
    def capture_thread(self):
        """Capture and send video frames"""
        while self.running:
            try:
                ret, frame = self.capture.read()
                if not ret:
                    continue
                
                # Store local frame for display
                with self.lock:
                    self.local_frame = frame.copy()
                
                # Compress and send frame
                compressed = compress_frame(frame, VIDEO_QUALITY)
                if compressed:
                    # Format: [username_length:4bytes][username][frame_data]
                    username_bytes = self.username.encode('utf-8')
                    username_len = struct.pack('!I', len(username_bytes))
                    packet = username_len + username_bytes + compressed
                    
                    self.video_socket.sendto(packet, self.server_address)
                
                # Control frame rate
                threading.Event().wait(1.0 / VIDEO_FPS)
                
            except Exception as e:
                if self.running:
                    print(f"[VIDEO] Capture error: {e}")
    
    def receive_thread(self):
        """Receive video frames from server"""
        while self.running:
            try:
                data, addr = self.video_socket.recvfrom(BUFFER_SIZE)
                
                # Extract username and frame data
                username_len = struct.unpack('!I', data[:4])[0]
                username = data[4:4+username_len].decode('utf-8')
                frame_data = data[4+username_len:]
                
                # Decompress frame
                frame = decompress_frame(frame_data)
                if frame is not None:
                    with self.lock:
                        self.remote_frames[username] = frame
                
            except Exception as e:
                if self.running:
                    print(f"[VIDEO] Receive error: {e}")
    
    def get_local_frame(self):
        """Get local camera frame"""
        with self.lock:
            return self.local_frame.copy() if self.local_frame is not None else None
    
    def get_remote_frames(self):
        """Get all remote video frames"""
        with self.lock:
            return self.remote_frames.copy()
    
    def stop_capture(self):
        """Stop video capture"""
        self.running = False
        if self.capture:
            self.capture.release()
        if self.video_socket:
            self.video_socket.close()
        print("[VIDEO] Video capture stopped")