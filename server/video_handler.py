"""
Video Handler - Manages video streaming using UDP with frame splitting
"""

import socket
import threading
import struct
import time
import cv2
import numpy as np
from common.config import VIDEO_PORT

# UDP Streaming Configuration (matching video_capture.py)
CHUNK_SIZE = 60000            # chunk payload size (safe < UDP limit)
FRAME_TIMEOUT = 2.0           # seconds to wait for missing packets before dropping frame
JPEG_QUALITY = 70             # encoding quality 0-100

# Packet header format: username_len (H), username (str), frame_id (Q), total_pkts (I), pkt_idx (I), payload_len (H)
HDR_BASE_FMT = "!QIIH"  # frame_id (Q), total_pkts (I), pkt_idx (I), payload_len (H)
HDR_BASE_SIZE = struct.calcsize(HDR_BASE_FMT)

class VideoHandler:
    def __init__(self, session_manager, host='0.0.0.0'):
        self.session_manager = session_manager
        self.host = host
        self.video_socket = None
        self.running = False
        self.video_streams = {}  # {username: latest_frame_data}
        self.frames_in_progress = {}  # {username: {frame_id: {...}}}
        self.lock = threading.Lock()
        
    def start(self):
        """Start video handler"""
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.video_socket.bind((self.host, VIDEO_PORT))
            self.video_socket.settimeout(0.5)  # For frame timeout cleanup
            self.running = True
            
            # Start receiver thread
            threading.Thread(target=self.receive_video, daemon=True).start()
            # Start broadcaster thread
            threading.Thread(target=self.broadcast_video, daemon=True).start()
            
            print(f"[VIDEO] Handler started on port {VIDEO_PORT}")
            return True
        except Exception as e:
            print(f"[VIDEO] Failed to start: {e}")
            return False
    
    def receive_video(self):
        """Receive UDP packets with frame splitting, reassemble frames"""
        
        while self.running:
            try:
                try:
                    packet, _ = self.video_socket.recvfrom(CHUNK_SIZE + HDR_BASE_SIZE + 64)
                except socket.timeout:
                    # Cleanup stale frames
                    now = time.time()
                    with self.lock:
                        for frames in self.frames_in_progress.values():
                            stale_ids = [fid for fid, info in frames.items() 
                                       if now - info['last_time'] > FRAME_TIMEOUT]
                            for fid in stale_ids:
                                frames.pop(fid, None)
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[VIDEO] Receive error: {e}")
                    break
                
                if len(packet) < HDR_BASE_SIZE + 2:
                    continue
                
                # Extract username length and username
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
                with self.lock:
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
                                # Store complete frame
                                self.video_streams[username] = frame
                        except Exception as e:
                            print(f"[VIDEO] Decode error: {e}")
                        # Remove completed frame
                        frames.pop(frame_id, None)
                    
            except Exception as e:
                if self.running:
                    print(f"[VIDEO] Receive error: {e}")
    
    def broadcast_video(self):
        """Broadcast all video streams to all clients with frame splitting"""
        frame_ids = {}  # Track frame IDs per sender-receiver pair
        
        while self.running:
            try:
                with self.lock:
                    if not self.video_streams:
                        threading.Event().wait(0.1)
                        continue
                    
                    # Get all user addresses
                    users = self.session_manager.get_user_list()
                    
                    for username in users:
                        user_data = self.session_manager.users.get(username)
                        if not user_data:
                            continue
                        
                        client_addr = user_data['address']
                        
                        # Send all video streams except user's own
                        for stream_user, frame in self.video_streams.items():
                            if stream_user != username:
                                # Create unique key for sender-receiver pair
                                frame_key = f"{stream_user}-{username}"
                                
                                # Initialize frame ID counter for this sender-receiver pair
                                if frame_key not in frame_ids:
                                    frame_ids[frame_key] = 0
                                
                                try:
                                    # Encode frame to JPEG
                                    ok, enc = cv2.imencode('.jpg', frame, 
                                                          [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                                    if not ok:
                                        continue
                                    
                                    payload = enc.tobytes()
                                    total_len = len(payload)
                                    
                                    # Split into chunks
                                    total_pkts = (total_len + CHUNK_SIZE - 1) // CHUNK_SIZE
                                    offset = 0
                                    frame_id = frame_ids[frame_key]
                                    
                                    for pkt_idx in range(total_pkts):
                                        chunk = payload[offset:offset+CHUNK_SIZE]
                                        offset += CHUNK_SIZE
                                        hdr = struct.pack(HDR_BASE_FMT, frame_id, total_pkts, pkt_idx, len(chunk))
                                        # Prepend username to packet: [username_len:2bytes][username][header][data]
                                        username_bytes = stream_user.encode('utf-8')
                                        username_header = struct.pack('!H', len(username_bytes)) + username_bytes
                                        packet = username_header + hdr + chunk
                                        
                                        try:
                                            self.video_socket.sendto(packet, (client_addr[0], VIDEO_PORT))
                                        except Exception as e:
                                            print(f"[VIDEO] Sendto error: {e}")
                                    
                                    frame_ids[frame_key] = (frame_ids[frame_key] + 1) & 0xFFFFFFFFFFFFFFFF
                                    
                                except Exception as e:
                                    print(f"[VIDEO] Broadcast encode error: {e}")
                
                threading.Event().wait(0.033)  # ~30 FPS broadcast rate
                
            except Exception as e:
                if self.running:
                    print(f"[VIDEO] Broadcast error: {e}")
    
    def stop(self):
        """Stop video handler"""
        self.running = False
        if self.video_socket:
            self.video_socket.close()
        print("[VIDEO] Handler stopped")