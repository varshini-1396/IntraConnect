"""
Video Capture Module - UDP Streaming Integration
Handles webcam capture using efficient UDP streaming like your friend's app
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
CHUNK_SIZE = 60000            # chunk payload size (safe < UDP limit)
FRAME_TIMEOUT = 2.0           # seconds to wait for missing packets before dropping frame
JPEG_QUALITY = 70             # encoding quality 0-100

# Packet header format: username_len (H), username (str), frame_id (Q), total_pkts (I), pkt_idx (I), payload_len (H)
HDR_BASE_FMT = "!QIIH"  # frame_id (Q), total_pkts (I), pkt_idx (I), payload_len (H)
HDR_BASE_SIZE = struct.calcsize(HDR_BASE_FMT)

class VideoCapture:
    def __init__(self, username):
        self.username = username
        self.capture = None
        self.running = False
        self.server_address = None
        self.client_video_port = None # Port this client listens on
        self.local_frame = None
        self.remote_frames = {}  # {username: frame}
        self.lock = threading.Lock()
        
        # UDP streaming
        self.frame_id = 0
        self.received_frame_count = 0  # Track received frames for debugging
        self.frames_in_progress = {}  # {username: {frame_id: {...}}}
        self.local_frame_q = queue.Queue(maxsize=2)
        self.remote_frame_q = queue.Queue(maxsize=2)
        
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
            
            # Server address for sending
            self.server_address = (server_ip, VIDEO_PORT)
            
            self.running = True
            
            # Start UDP sender thread (sends to server)
            threading.Thread(target=self.udp_sender_thread, daemon=True).start()
            # Start UDP receiver thread (receives from server)
            threading.Thread(target=self.udp_receiver_thread, daemon=True).start()
            
            print(f"[VIDEO] UDP video capture started - sending to {self.server_address}, receiving on port {VIDEO_PORT}")
            return True
            
        except Exception as e:
            print(f"[VIDEO] Failed to start capture: {e}")
            return False
    
    def udp_sender_thread(self):
        """Continuously capture frames, encode, split, and send via UDP"""
        print("[VIDEO] Starting UDP sender to", self.server_address)
        
        if not self.capture.isOpened():
            print("[-] Cannot open webcam")
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

                # Store local frame for display
                with self.lock:
                    self.local_frame = frame.copy()

                # Encode JPEG
                ok, enc = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                if not ok:
                    continue
                payload = enc.tobytes()
                total_len = len(payload)

                # Split into chunks
                total_pkts = (total_len + CHUNK_SIZE - 1) // CHUNK_SIZE
                offset = 0
                # Uncomment for detailed debugging:
                # if frame_id % 30 == 0:
                #     print(f"[VIDEO] Sending frame {frame_id} to server ({total_pkts} packets)")
                for pkt_idx in range(total_pkts):
                    chunk = payload[offset: offset+CHUNK_SIZE]
                    offset += CHUNK_SIZE
                    hdr = struct.pack(HDR_BASE_FMT, frame_id, total_pkts, pkt_idx, len(chunk))
                    # Prepend username to packet
                    username_bytes = self.username.encode('utf-8')
                    username_header = struct.pack('!H', len(username_bytes)) + username_bytes
                    packet = username_header + hdr + chunk
                    try:
                        sock.sendto(packet, self.server_address)
                    except Exception as e:
                        print(f"[VIDEO] Send error: {e}")
                
                frame_id = (frame_id + 1) & 0xFFFFFFFFFFFFFFFF
                time.sleep(0.01)  # Small throttle
                
        except Exception as e:
            print(f"[VIDEO] Sender error: {e}")
        finally:
            sock.close()
            print("[VIDEO] UDP sender thread exiting")
    
    def udp_receiver_thread(self):
        """Receive UDP packets, reassemble frames, store in remote_frames"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', VIDEO_PORT))
        sock.bind(('0.0.0.0', 0))  # Bind to a random available port
        self.client_video_port = sock.getsockname()[1] # Get the assigned port
        sock.settimeout(0.5)
        print("[VIDEO] UDP receiver listening on port", VIDEO_PORT)
        print(f"[VIDEO] UDP receiver listening on port {self.client_video_port}")

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
                    print(f"[VIDEO] Receive error: {e}")
                    break

                if len(packet) < HDR_BASE_SIZE + 2:
                    continue
                
                # Extract username
                username_len = struct.unpack('!H', packet[:2])[0]
                if len(packet) < 2 + username_len + HDR_BASE_SIZE:
                    continue
                    
                username_bytes = packet[2:2+username_len]
                username = username_bytes.decode('utf-8')
                    
                hdr = packet[2+username_len:2+username_len+HDR_BASE_SIZE]
                try:
                    frame_id, total_pkts, pkt_idx, payload_len = struct.unpack(HDR_BASE_FMT, hdr)
                except Exception:
                    continue
                    
                chunk = packet[2+username_len+HDR_BASE_SIZE:2+username_len+HDR_BASE_SIZE+payload_len]

                # Initialize frame tracking for user
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

                # If complete frame
                if info['received'] == info['total']:
                    # Reassemble
                    parts = [info['parts'].get(i, b'') for i in range(info['total'])]
                    payload = b''.join(parts)
                    try:
                        # Decode JPEG
                        nparr = np.frombuffer(payload, dtype=np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            # Store in remote frames using actual username
                            with self.lock:
                                self.remote_frames[username] = frame
                                self.received_frame_count += 1
                                if self.received_frame_count % 60 == 1 or len(self.remote_frames) != 1:  # Print first frame or when user count changes
                                    print(f"[VIDEO] ✓ Total frames received: {self.received_frame_count}, Users visible: {list(self.remote_frames.keys())}")
                    except Exception as e:
                        print(f"[VIDEO] Decode error: {e}")
                    # Remove completed frame
                    frames.pop(frame_id, None)
                    
        except Exception as e:
            print(f"[VIDEO] Receiver error: {e}")
        finally:
            sock.close()
            print("[VIDEO] UDP receiver thread exiting")
    
    
    def get_local_frame(self):
        """Get local camera frame"""
        with self.lock:
            if self.local_frame is not None:
                return self.local_frame.copy()
            return None
    
    def get_remote_frames(self):
        """Get all remote video frames"""
        with self.lock:
            return self.remote_frames.copy()
    
    def stop_capture(self):
        """Stop video capture"""
        self.running = False
        if self.capture:
            self.capture.release()
        print("[VIDEO] Video capture stopped")