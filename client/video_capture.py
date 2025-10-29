"""
Video Capture Module - UDP Streaming Integration
FIXED: Zoom-like video where you see everyone except yourself
"""

import cv2
import numpy as np
import threading
import socket
import struct
import time
import queue
import sys
sys.path.append('..')
from common.config import VIDEO_PORT, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS

# UDP Streaming Configuration
CHUNK_SIZE = 60000
FRAME_TIMEOUT = 2.0
JPEG_QUALITY = 70

# Packet header format
HDR_BASE_FMT = "!QIIH"
HDR_BASE_SIZE = struct.calcsize(HDR_BASE_FMT)

class VideoCapture:
    def __init__(self, username):
        self.username = username
        self.capture = None
        self.running = False
        self.server_address = None
        self.local_frame = None  # For preview only
        self.remote_frames = {}  # {username: frame} - OTHER users only
        self.lock = threading.Lock()
        
        # UDP streaming
        self.frame_id = 0
        self.received_frame_count = 0
        self.frames_in_progress = {}  # {username: {frame_id: {...}}}
        
    def start_capture(self, server_ip):
        """Start capturing and sending video using UDP streaming"""
        try:
            self.capture = cv2.VideoCapture(0)
            if not self.capture.isOpened():
                print("[VIDEO] Could not open camera")
                return False
                
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
            self.capture.set(cv2.CAP_PROP_FPS, VIDEO_FPS)
            
            self.server_address = (server_ip, VIDEO_PORT)
            self.running = True
            
            # Start sender (sends to server)
            threading.Thread(target=self.udp_sender_thread, daemon=True).start()
            # Start receiver (receives from server)
            threading.Thread(target=self.udp_receiver_thread, daemon=True).start()
            
            print(f"[VIDEO] Started - sending to {self.server_address}")
            return True
            
        except Exception as e:
            print(f"[VIDEO] Failed to start: {e}")
            return False
    
    def udp_sender_thread(self):
        """Capture and send video to server"""
        if not self.capture.isOpened():
            print("[VIDEO] Cannot open webcam")
            self.running = False
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        frame_id = 0
        
        try:
            while self.running:
                ret, frame = self.capture.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                # Store local frame for preview
                with self.lock:
                    self.local_frame = frame.copy()

                # Encode JPEG
                ok, enc = cv2.imencode('.jpg', frame, 
                                      [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                if not ok:
                    continue
                    
                payload = enc.tobytes()
                total_len = len(payload)
                total_pkts = (total_len + CHUNK_SIZE - 1) // CHUNK_SIZE
                offset = 0
                
                # Send chunks
                for pkt_idx in range(total_pkts):
                    chunk = payload[offset:offset+CHUNK_SIZE]
                    offset += CHUNK_SIZE
                    hdr = struct.pack(HDR_BASE_FMT, frame_id, total_pkts, pkt_idx, len(chunk))
                    
                    # Prepend username
                    username_bytes = self.username.encode('utf-8')
                    username_header = struct.pack('!H', len(username_bytes)) + username_bytes
                    packet = username_header + hdr + chunk
                    
                    try:
                        sock.sendto(packet, self.server_address)
                    except Exception as e:
                        print(f"[VIDEO] Send error: {e}")
                
                frame_id = (frame_id + 1) & 0xFFFFFFFFFFFFFFFF
                time.sleep(0.033)  # ~30 FPS
                
        except Exception as e:
            print(f"[VIDEO] Sender error: {e}")
        finally:
            sock.close()
    
    def udp_receiver_thread(self):
        """Receive video from server (all other users)"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', VIDEO_PORT))
        sock.settimeout(0.5)
        print("[VIDEO] Receiver listening on port", VIDEO_PORT)

        try:
            while self.running:
                try:
                    packet, _ = sock.recvfrom(CHUNK_SIZE + HDR_BASE_SIZE + 64)
                except socket.timeout:
                    # Cleanup stale frames
                    now = time.time()
                    for frames in self.frames_in_progress.values():
                        stale_fids = [fid for fid, info in frames.items() 
                                     if now - info['last_time'] > FRAME_TIMEOUT]
                        for fid in stale_fids:
                            frames.pop(fid, None)
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[VIDEO] Receive error: {e}")
                    break

                if len(packet) < HDR_BASE_SIZE + 2:
                    continue
                
                # Extract username
                username_len = struct.unpack('!H', packet[:2])[0]
                if len(packet) < 2 + username_len + HDR_BASE_SIZE:
                    continue
                    
                username = packet[2:2+username_len].decode('utf-8')
                
                # CRITICAL: Skip our own video feed (Zoom behavior)
                if username == self.username:
                    continue
                
                hdr = packet[2+username_len:2+username_len+HDR_BASE_SIZE]
                try:
                    frame_id, total_pkts, pkt_idx, payload_len = struct.unpack(HDR_BASE_FMT, hdr)
                except Exception:
                    continue
                    
                chunk = packet[2+username_len+HDR_BASE_SIZE:2+username_len+HDR_BASE_SIZE+payload_len]

                # Track frame assembly
                if username not in self.frames_in_progress:
                    self.frames_in_progress[username] = {}
                    
                frames = self.frames_in_progress[username]
                if frame_id not in frames:
                    frames[frame_id] = {
                        'total': total_pkts,
                        'parts': {},
                        'received': 0,
                        'last_time': time.time()
                    }
                    
                info = frames[frame_id]
                if pkt_idx not in info['parts']:
                    info['parts'][pkt_idx] = chunk
                    info['received'] += 1
                    info['last_time'] = time.time()

                # Complete frame?
                if info['received'] == info['total']:
                    parts = [info['parts'].get(i, b'') for i in range(info['total'])]
                    payload = b''.join(parts)
                    try:
                        nparr = np.frombuffer(payload, dtype=np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            with self.lock:
                                self.remote_frames[username] = frame
                                self.received_frame_count += 1
                                # Debug print
                                if self.received_frame_count % 60 == 1:
                                    print(f"[VIDEO CLIENT] ✓ Received frame from '{username}'")
                                    print(f"[VIDEO CLIENT] Total frames received: {self.received_frame_count}")
                                    print(f"[VIDEO CLIENT] Remote users visible: {list(self.remote_frames.keys())}")
                                    print(f"[VIDEO CLIENT] My username (filtered): '{self.username}'")
                    except Exception as e:
                        print(f"[VIDEO] Decode error: {e}")
                    frames.pop(frame_id, None)
                    
        except Exception as e:
            print(f"[VIDEO] Receiver error: {e}")
        finally:
            sock.close()
    
    def get_local_frame(self):
        """Get local camera preview"""
        with self.lock:
            if self.local_frame is not None:
                return self.local_frame.copy()
            return None
    
    def get_remote_frames(self):
        """Get all remote video frames (other users only)"""
        with self.lock:
            return self.remote_frames.copy()
    
    def stop_capture(self):
        """Stop video capture"""
        self.running = False
        if self.capture:
            self.capture.release()
        print("[VIDEO] Stopped")