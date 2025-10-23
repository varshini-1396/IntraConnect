"""
Video Handler - Manages video streaming using UDP
"""

import socket
import threading
import struct
from common.config import VIDEO_PORT, BUFFER_SIZE

class VideoHandler:
    def __init__(self, session_manager, host='0.0.0.0'):
        self.session_manager = session_manager
        self.host = host
        self.video_socket = None
        self.running = False
        self.video_streams = {}  # {username: latest_frame_data}
        self.lock = threading.Lock()
        
    def start(self):
        """Start video handler"""
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.video_socket.bind((self.host, VIDEO_PORT))
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
        """Receive video frames from clients"""
        while self.running:
            try:
                data, addr = self.video_socket.recvfrom(BUFFER_SIZE)
                
                # Extract username and frame data
                # Format: [username_length:4bytes][username][frame_data]
                username_len = struct.unpack('!I', data[:4])[0]
                username = data[4:4+username_len].decode('utf-8')
                frame_data = data[4+username_len:]
                
                with self.lock:
                    self.video_streams[username] = frame_data
                    
            except Exception as e:
                if self.running:
                    print(f"[VIDEO] Receive error: {e}")
    
    def broadcast_video(self):
        """Broadcast all video streams to all clients"""
        while self.running:
            try:
                with self.lock:
                    if not self.video_streams:
                        continue
                    
                    # Get all user addresses
                    users = self.session_manager.get_user_list()
                    
                    for username in users:
                        user_data = self.session_manager.users.get(username)
                        if not user_data:
                            continue
                        
                        client_addr = user_data['address']
                        
                        # Send all video streams except user's own
                        for stream_user, frame_data in self.video_streams.items():
                            if stream_user != username:
                                # Format: [username_length:4bytes][username][frame_data]
                                username_bytes = stream_user.encode('utf-8')
                                username_len = struct.pack('!I', len(username_bytes))
                                packet = username_len + username_bytes + frame_data
                                
                                try:
                                    self.video_socket.sendto(packet, (client_addr[0], VIDEO_PORT))
                                except:
                                    pass
                
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