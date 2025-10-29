"""
Audio Handler - Manages audio streaming and mixing using UDP
"""

import socket
import threading
import struct
import numpy as np
from common.config import AUDIO_PORT, BUFFER_SIZE

class AudioHandler:
    def __init__(self, session_manager, host='0.0.0.0'):
        self.session_manager = session_manager
        self.host = host
        self.audio_socket = None
        self.running = False
        self.audio_buffers = {}  # {username: latest_audio_data}
        self.lock = threading.Lock()
        
    def start(self):
        """Start audio handler"""
        try:
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.audio_socket.bind((self.host, AUDIO_PORT))
            self.running = True
            
            # Start receiver thread
            threading.Thread(target=self.receive_audio, daemon=True).start()
            # Start mixer/broadcaster thread
            threading.Thread(target=self.mix_and_broadcast, daemon=True).start()
            
            print(f"[AUDIO] Handler started on port {AUDIO_PORT}")
            return True
        except Exception as e:
            print(f"[AUDIO] Failed to start: {e}")
            return False
    
    def receive_audio(self):
        """Receive audio chunks from clients"""
        while self.running:
            try:
                data, _ = self.audio_socket.recvfrom(BUFFER_SIZE)
                
                # Check if packet is long enough to have header
                if len(data) < 4:
                    continue
                
                try:
                    # Extract username and audio data
                    # Format: [username_length:4bytes][username][audio_data]
                    username_len = struct.unpack('!I', data[:4])[0]
                    
                    # Validate username length is reasonable
                    if username_len > 100 or username_len < 0 or 4 + username_len > len(data):
                        continue
                    
                    username = data[4:4+username_len].decode('utf-8')
                    audio_data = data[4+username_len:]
                    
                    if audio_data:  # Only store if there's actual audio data
                        with self.lock:
                            self.audio_buffers[username] = audio_data
                            
                except (struct.error, UnicodeDecodeError):
                    # Skip invalid packets (likely not audio data or corrupted)
                    continue
                    
            except Exception as e:
                if self.running:
                    # Don't print errors for every invalid packet
                    pass
    
    def mix_and_broadcast(self):
        """Mix audio from all sources and broadcast to all clients"""
        while self.running:
            try:
                with self.lock:
                    if len(self.audio_buffers) == 0:
                        threading.Event().wait(0.02)
                        continue
                    
                    # Mix audio from all users
                    # mixed_audio = self.mix_audio_streams() # Not used in broadcast logic
                    
                    # Get all user addresses
                    users = self.session_manager.get_user_list()
                    
                    for username in users:
                        user_data = self.session_manager.users.get(username)
                        if not user_data:
                            continue
                        
                        client_addr = user_data['address']
                        
                        # Send mixed audio (excluding user's own voice for echo cancellation)
                        user_mixed = self.mix_audio_except(username)
                        if user_mixed is not None:
                            try:
                                self.audio_socket.sendto(user_mixed, (client_addr[0], AUDIO_PORT))
                            except Exception:
                                pass
                
                threading.Event().wait(0.02)  # 50Hz broadcast rate
                
            except Exception as e:
                if self.running:
                    print(f"[AUDIO] Mix/broadcast error: {e}")
    
    def mix_audio_streams(self):
        """Mix all audio streams together"""
        try:
            if not self.audio_buffers:
                return None
            
            # Convert all audio data to numpy arrays
            audio_arrays = []
            for _, audio_data in self.audio_buffers.items():
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                audio_arrays.append(audio_array)
            
            if not audio_arrays:
                return None
            
            # Find minimum length
            min_length = min(len(arr) for arr in audio_arrays)
            
            # Trim all arrays to same length and sum
            trimmed_arrays = [arr[:min_length] for arr in audio_arrays]
            # Simple average for mixing
            mixed = np.sum(trimmed_arrays, axis=0) / len(trimmed_arrays)
            
            # Convert back to int16
            mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
            return mixed.tobytes()
            
        except Exception as e:
            print(f"[AUDIO] Mix error: {e}")
            return None
    
    def mix_audio_except(self, except_username):
        """Mix audio excluding specific user (for echo cancellation)"""
        try:
            audio_arrays = []
            for username, audio_data in self.audio_buffers.items():
                if username != except_username:
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    audio_arrays.append(audio_array)
            
            if not audio_arrays:
                return None
            
            # Find minimum length
            min_length = min(len(arr) for arr in audio_arrays)
            
            # Trim all arrays to same length and sum
            trimmed_arrays = [arr[:min_length] for arr in audio_arrays]
            mixed = np.sum(trimmed_arrays, axis=0) / len(trimmed_arrays)
            
            # Convert back to int16
            mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
            return mixed.tobytes()
            
        except Exception:
            return None

    def remove_stream(self, username):
        """Remove audio stream for a disconnected user (Fix for stuck stream)"""
        with self.lock:
            self.audio_buffers.pop(username, None)
            print(f"[AUDIO] Stream for {username} removed.")
    
    def stop(self):
        """Stop audio handler"""
        self.running = False
        if self.audio_socket:
            self.audio_socket.close()
        print("[AUDIO] Handler stopped")