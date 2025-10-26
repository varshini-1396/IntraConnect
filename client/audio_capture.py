"""
Audio Capture Module
Handles microphone capture and audio playback
"""

import pyaudio
import threading
import socket
import struct
import sys
sys.path.append('..')
from common.config import AUDIO_PORT, AUDIO_CHUNK, AUDIO_FORMAT, AUDIO_CHANNELS, AUDIO_RATE, BUFFER_SIZE

class AudioCapture:
    def __init__(self, username):
        self.username = username
        self.audio = None
        self.stream_in = None
        self.stream_out = None
        self.running = False
        self.audio_socket = None
        self.server_address = None
        
    def start_audio(self, server_ip):
        """Start audio capture and playback"""
        try:
            self.audio = pyaudio.PyAudio()
            
            # Input stream (microphone)
            self.stream_in = self.audio.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RATE,
                input=True,
                frames_per_buffer=AUDIO_CHUNK
            )
            
            # Output stream (speakers)
            self.stream_out = self.audio.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RATE,
                output=True,
                frames_per_buffer=AUDIO_CHUNK
            )
            
            # Create UDP socket for audio
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.audio_socket.bind(('0.0.0.0', AUDIO_PORT))
            self.server_address = (server_ip, AUDIO_PORT)
            
            self.running = True
            
            # Start threads
            threading.Thread(target=self.send_audio, daemon=True).start()
            threading.Thread(target=self.receive_audio, daemon=True).start()
            
            print("[AUDIO] Audio started")
            return True
            
        except Exception as e:
            print(f"[AUDIO] Failed to start: {e}")
            return False
    
    def send_audio(self):
        """Capture and send audio to server"""
        while self.running:
            try:
                # Read audio from microphone
                audio_data = self.stream_in.read(AUDIO_CHUNK, exception_on_overflow=False)
                
                # Format: [username_length:4bytes][username][audio_data]
                username_bytes = self.username.encode('utf-8')
                username_len = struct.pack('!I', len(username_bytes))
                packet = username_len + username_bytes + audio_data
                
                # Send to server
                self.audio_socket.sendto(packet, self.server_address)
                
            except Exception as e:
                if self.running:
                    print(f"[AUDIO] Send error: {e}")
    
    def receive_audio(self):
        """Receive and play mixed audio from server"""
        while self.running:
            try:
                # Receive mixed audio
                data, _ = self.audio_socket.recvfrom(BUFFER_SIZE)
                
                # Validate audio data is reasonable length
                if len(data) > 0 and len(data) < 50000:  # Max ~50KB per chunk
                    # Play audio
                    self.stream_out.write(data)
                
            except Exception:
                if self.running:
                    # Don't spam error messages for audio issues
                    pass
    
    def stop_audio(self):
        """Stop audio capture and playback"""
        self.running = False
        
        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()
        
        if self.stream_out:
            self.stream_out.stop_stream()
            self.stream_out.close()
        
        if self.audio:
            self.audio.terminate()
        
        if self.audio_socket:
            self.audio_socket.close()
        
        print("[AUDIO] Audio stopped")