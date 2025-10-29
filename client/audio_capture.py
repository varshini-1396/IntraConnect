"""
Audio Capture Module - FIXED
Working audio with proper error handling
"""

import pyaudio
import threading
import socket
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(_file_))))

from common.config import AUDIO_PORT, AUDIO_CHUNK, AUDIO_FORMAT, AUDIO_CHANNELS, AUDIO_RATE, BUFFER_SIZE

class AudioCapture:
    def _init_(self, username):
        self.username = username
        self.audio = None
        self.stream_in = None
        self.stream_out = None
        self.running = False
        self.audio_socket = None
        self.server_address = None
        
    def start_audio(self, server_ip):
        """Start audio"""
        try:
            self.audio = pyaudio.PyAudio()
            
            # Check for available devices
            info = self.audio.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            
            input_device = None
            output_device = None
            
            for i in range(0, numdevices):
                device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels') > 0:
                    input_device = i
                if device_info.get('maxOutputChannels') > 0:
                    output_device = i
            
            if input_device is None:
                print("[AUDIO] No input device found")
                return False
            
            if output_device is None:
                print("[AUDIO] No output device found")
                return False
            
            # Input stream
            self.stream_in = self.audio.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RATE,
                input=True,
                input_device_index=input_device,
                frames_per_buffer=AUDIO_CHUNK
            )
            
            # Output stream
            self.stream_out = self.audio.open(
                format=AUDIO_FORMAT,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_RATE,
                output=True,
                output_device_index=output_device,
                frames_per_buffer=AUDIO_CHUNK
            )
            
            # UDP socket
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.audio_socket.bind(('0.0.0.0', AUDIO_PORT))
            self.server_address = (server_ip, AUDIO_PORT)
            
            self.running = True
            
            # Start threads
            threading.Thread(target=self.send_audio, daemon=True).start()
            threading.Thread(target=self.receive_audio, daemon=True).start()
            
            print("[AUDIO] Audio started successfully")
            return True
            
        except Exception as e:
            print(f"[AUDIO] Failed to start: {e}")
            self.stop_audio()
            return False
    
    def send_audio(self):
        """Send audio"""
        while self.running:
            try:
                # Read audio
                audio_data = self.stream_in.read(AUDIO_CHUNK, exception_on_overflow=False)
                
                # Format packet
                username_bytes = self.username.encode('utf-8')
                username_len = struct.pack('!I', len(username_bytes))
                packet = username_len + username_bytes + audio_data
                
                # Send to server
                self.audio_socket.sendto(packet, self.server_address)
                
            except Exception as e:
                if self.running:
                    print(f"[AUDIO] Send error: {e}")
                    break
    
    def receive_audio(self):
        """Receive audio"""
        self.audio_socket.settimeout(0.5)
        
        while self.running:
            try:
                # Receive audio
                data, _ = self.audio_socket.recvfrom(BUFFER_SIZE)
                
                # Validate
                if len(data) > 0 and len(data) < 50000:
                    # Play audio
                    try:
                        self.stream_out.write(data)
                    except Exception as e:
                        # Ignore playback errors
                        pass
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    pass
    
    def stop_audio(self):
        """Stop audio"""
        self.running = False
        
        if self.stream_in:
            try:
                self.stream_in.stop_stream()
                self.stream_in.close()
            except:
                pass
        
        if self.stream_out:
            try:
                self.stream_out.stop_stream()
                self.stream_out.close()
            except:
                pass
        
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
        
        if self.audio_socket:
            try:
                self.audio_socket.close()
            except:
                pass
        
        print("[AUDIO] Audio stopped")