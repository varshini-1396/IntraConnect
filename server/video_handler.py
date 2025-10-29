"""
Video Handler - FIXED with detailed logging
Key fix: Ensure ALL users receive ALL video streams
"""

import socket
import threading
import struct
import time
import cv2
import numpy as np
from common.config import VIDEO_PORT

# UDP Streaming Configuration
CHUNK_SIZE = 60000
FRAME_TIMEOUT = 2.0
JPEG_QUALITY = 70

# Packet header format
HDR_BASE_FMT = "!QIIH"
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
        self.frame_count = {}  # Track frames received per user
        
    def start(self):
        """Start video handler"""
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.video_socket.bind((self.host, VIDEO_PORT))
            self.video_socket.settimeout(0.5)
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
        """Receive UDP packets from clients"""
        
        while self.running:
            try:
                try:
                    packet, _sender_addr = self.video_socket.recvfrom(CHUNK_SIZE + HDR_BASE_SIZE + 64)
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
                with self.lock:
                    if username not in self.frames_in_progress:
                        self.frames_in_progress[username] = {}
                        self.frame_count[username] = 0
                        
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
                                self.frame_count[username] += 1
                                
                                # Debug logging
                                if self.frame_count[username] % 60 == 1:
                                    print(f"[VIDEO] ✓ Received frame #{self.frame_count[username]} from '{username}'")
                                    print(f"[VIDEO] Current streams: {list(self.video_streams.keys())}")
                        except Exception as e:
                            print(f"[VIDEO] Decode error: {e}")
                        # Remove completed frame
                        frames.pop(frame_id, None)
                    
            except Exception as e:
                if self.running:
                    print(f"[VIDEO] Receive error: {e}")
    
    def broadcast_video(self):
        """Broadcast all video streams to all clients"""
        frame_ids = {}
        broadcast_count = 0
        
        while self.running:
            try:
                with self.lock:
                    if not self.video_streams:
                        time.sleep(0.1)
                        continue
                    
                    # Get all connected users
                    users = self.session_manager.get_user_list()
                    
                    if not users:
                        time.sleep(0.1)
                        continue
                    
                    broadcast_count += 1
                    
                    # Debug logging every 5 seconds (150 frames at 30fps)
                    if broadcast_count % 150 == 1:
                        print("\n[VIDEO] === BROADCAST STATUS ===")
                        print(f"[VIDEO] Streams available: {list(self.video_streams.keys())}")
                        print(f"[VIDEO] Connected users: {users}")
                        print("[VIDEO] Will send each stream to each user")
                    
                    # For each receiving user
                    for receiver_username in users:
                        user_data = self.session_manager.users.get(receiver_username)
                        if not user_data:
                            continue
                        
                        client_addr = user_data['address']
                        
                        # Send ALL video streams to this user
                        # IMPORTANT: Each client receives ALL streams (including their own)
                        # The CLIENT will filter out their own username
                        for sender_username, frame in self.video_streams.items():
                            frame_key = f"{sender_username}-{receiver_username}"
                            
                            if frame_key not in frame_ids:
                                frame_ids[frame_key] = 0
                            
                            try:
                                # Encode frame
                                ok, enc = cv2.imencode('.jpg', frame, 
                                                      [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                                if not ok:
                                    continue
                                
                                payload = enc.tobytes()
                                total_len = len(payload)
                                total_pkts = (total_len + CHUNK_SIZE - 1) // CHUNK_SIZE
                                offset = 0
                                frame_id = frame_ids[frame_key]
                                
                                # Send chunks
                                for pkt_idx in range(total_pkts):
                                    chunk = payload[offset:offset+CHUNK_SIZE]
                                    offset += CHUNK_SIZE
                                    hdr = struct.pack(HDR_BASE_FMT, frame_id, total_pkts, pkt_idx, len(chunk))
                                    
                                    # Prepend sender username to packet
                                    username_bytes = sender_username.encode('utf-8')
                                    username_header = struct.pack('!H', len(username_bytes)) + username_bytes
                                    packet = username_header + hdr + chunk
                                    
                                    try:
                                        self.video_socket.sendto(packet, (client_addr[0], VIDEO_PORT))
                                    except Exception as e:
                                        if broadcast_count % 150 == 1:
                                            print(f"[VIDEO] Send error ({sender_username} → {receiver_username}): {e}")
                                
                                frame_ids[frame_key] = (frame_ids[frame_key] + 1) & 0xFFFFFFFFFFFFFFFF
                                
                                # Debug logging
                                if broadcast_count % 150 == 1:
                                    print(f"[VIDEO] ✓ Sent {sender_username}'s video → {receiver_username} at {client_addr[0]}")
                                
                            except Exception as e:
                                print(f"[VIDEO] Encode error: {e}")
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                if self.running:
                    print(f"[VIDEO] Broadcast error: {e}")

    def remove_stream(self, username):
        """Remove video stream for a disconnected user (Fix for stuck video)"""
        with self.lock:
            self.video_streams.pop(username, None)
            self.frames_in_progress.pop(username, None)
            self.frame_count.pop(username, None)
            print(f"[VIDEO] Stream for {username} removed.")

    def stop(self):
        """Stop video handler"""
        self.running = False
        if self.video_socket:
            self.video_socket.close()
        print("[VIDEO] Handler stopped")