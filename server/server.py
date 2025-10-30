# server.py
"""
IntraConnect Server
Handles all client connections and data relay for video, audio, chat, screen sharing, and file transfer
"""

import socket
import threading
import struct
import json
import time
import os
from datetime import datetime

class IntraConnectServer:
    def __init__(self, host='0.0.0.0', tcp_port=5555, udp_video_port=5556, udp_audio_port=5557):
        self.host = host
        self.tcp_port = tcp_port
        self.udp_video_port = udp_video_port
        self.udp_audio_port = udp_audio_port
        
        # TCP socket for reliable data (chat, files, screen sharing, control)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((self.host, self.tcp_port))
        self.tcp_socket.listen(50)
        
        # UDP sockets for streaming
        self.udp_video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_video_socket.bind((self.host, self.udp_video_port))
        
        self.udp_audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_audio_socket.bind((self.host, self.udp_audio_port))
        
        # Client management
        self.clients = {}  # {username: {'tcp': socket, 'addr': (ip, port), 'udp': (ip, port)}}
        self.client_lock = threading.Lock()
        
        # Screen sharing
        self.presenter = None
        
        # File storage
        self.files = {}  # {filename: data}
        
        # Running flag
        self.running = True
        
        self.print_banner()
    
    def print_banner(self):
        """Print server startup banner"""
        local_ip = self.get_local_ip()
        print("\n" + "="*70)
        print(" "*20 + "🌐 IntraConnect Server")
        print("="*70)
        print(f"\n✓ Server started successfully!")
        print(f"\n📡 Network Configuration:")
        print(f"   • Server IP:      {local_ip}")
        print(f"   • TCP Port:       {self.tcp_port} (Chat, Files, Screen)")
        print(f"   • UDP Video:      {self.udp_video_port}")
        print(f"   • UDP Audio:      {self.udp_audio_port}")
        print(f"\n💡 Clients should connect to: {local_ip}:{self.tcp_port}")
        print(f"\n⏳ Waiting for connections...")
        print("="*70 + "\n")
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def encode_message(self, msg_type, data):
        """Encode message with length prefix"""
        try:
            message = {'type': msg_type, 'data': data}
            msg_json = json.dumps(message)
            msg_bytes = msg_json.encode('utf-8')
            length = struct.pack('>I', len(msg_bytes))
            return length + msg_bytes
        except Exception as e:
            print(f"[ERROR] Encode: {e}")
            return None
    
    def decode_message(self, msg_bytes):
        """Decode message"""
        try:
            msg_json = msg_bytes.decode('utf-8')
            message = json.loads(msg_json)
            return message['type'], message['data']
        except Exception as e:
            print(f"[ERROR] Decode: {e}")
            return None, None
    
    def broadcast_tcp(self, message, exclude_user=None):
        """Broadcast TCP message to all clients"""
        with self.client_lock:
            for username, info in list(self.clients.items()):
                if username != exclude_user:
                    try:
                        info['tcp'].sendall(message)
                    except Exception as e:
                        print(f"[ERROR] Failed to send to {username}: {e}")
    
    def broadcast_users(self):
        """Broadcast user list to all clients"""
        with self.client_lock:
            users = list(self.clients.keys())
        msg = self.encode_message('USER_LIST', {'users': users})
        self.broadcast_tcp(msg)
    
    def handle_client(self, client_socket, address):
        """Handle TCP client connection"""
        username = None
        try:
            # Receive connection message
            length_data = client_socket.recv(4)
            if not length_data:
                return
            
            msg_length = struct.unpack('>I', length_data)[0]
            msg_data = client_socket.recv(msg_length)
            msg_type, data = self.decode_message(msg_data)
            
            if msg_type == 'CONNECT':
                username = data['username']
                udp_port = data.get('udp_port', 0)
                
                with self.client_lock:
                    self.clients[username] = {
                        'tcp': client_socket,
                        'addr': address,
                        'udp': (address[0], udp_port)
                    }
                
                print(f"[+] {username} connected from {address[0]}")
                self.broadcast_users()
            
            # Main message loop
            while self.running:
                length_data = client_socket.recv(4)
                if not length_data:
                    break
                
                msg_length = struct.unpack('>I', length_data)[0]
                msg_data = b''
                while len(msg_data) < msg_length:
                    chunk = client_socket.recv(min(msg_length - len(msg_data), 4096))
                    if not chunk:
                        break
                    msg_data += chunk
                
                if len(msg_data) != msg_length:
                    continue
                
                msg_type, data = self.decode_message(msg_data)
                self.process_message(msg_type, data, username)
        
        except Exception as e:
            print(f"[ERROR] Client {username}: {e}")
        finally:
            if username:
                with self.client_lock:
                    if username in self.clients:
                        del self.clients[username]
                if self.presenter == username:
                    self.presenter = None
                    self.broadcast_tcp(self.encode_message('SCREEN_STOP', {}))
                print(f"[-] {username} disconnected")
                self.broadcast_users()
            try:
                client_socket.close()
            except:
                pass
    
    def process_message(self, msg_type, data, sender):
        """Process incoming TCP messages"""
        if msg_type == 'CHAT':
            print(f"[CHAT] {sender}: {data['message']}")
            msg = self.encode_message('CHAT', {
                'username': sender,
                'message': data['message'],
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
            self.broadcast_tcp(msg, exclude_user=sender)
        
        elif msg_type == 'FILE_INFO':
            filename = data['filename']
            filesize = data['size']
            print(f"[FILE] {sender} uploading: {filename}")
            self.files[filename] = {'data': b'', 'size': filesize, 'uploader': sender}
        
        elif msg_type == 'FILE_CHUNK':
            filename = data['filename']
            chunk = data['chunk'].encode('latin-1')
            if filename in self.files:
                self.files[filename]['data'] += chunk
                if len(self.files[filename]['data']) >= self.files[filename]['size']:
                    msg = self.encode_message('FILE_INFO', {
                        'filename': filename,
                        'size': self.files[filename]['size'],
                        'uploader': self.files[filename]['uploader']
                    })
                    self.broadcast_tcp(msg, exclude_user=sender)
                    print(f"[FILE] {filename} upload complete")
        
        elif msg_type == 'FILE_REQUEST':
            filename = data['filename']
            if filename in self.files:
                with self.client_lock:
                    if sender in self.clients:
                        try:
                            msg = self.encode_message('FILE_CHUNK', {
                                'filename': filename,
                                'chunk': self.files[filename]['data'].decode('latin-1')
                            })
                            self.clients[sender]['tcp'].sendall(msg)
                        except Exception as e:
                            print(f"[ERROR] File send: {e}")
        
        elif msg_type == 'SCREEN_START':
            self.presenter = sender
            print(f"[SCREEN] {sender} started presenting")
            msg = self.encode_message('SCREEN_START', {'presenter': sender})
            self.broadcast_tcp(msg, exclude_user=sender)
        
        elif msg_type == 'SCREEN_STOP':
            if self.presenter == sender:
                self.presenter = None
                print(f"[SCREEN] {sender} stopped presenting")
                msg = self.encode_message('SCREEN_STOP', {})
                self.broadcast_tcp(msg)
        
        elif msg_type == 'SCREEN_FRAME':
            if self.presenter == sender:
                msg = self.encode_message('SCREEN_FRAME', {'frame': data['frame']})
                self.broadcast_tcp(msg, exclude_user=sender)
        
        elif msg_type == 'VIDEO_STOP':
            print(f"[VIDEO] {sender} stopped video")
            msg = self.encode_message('VIDEO_STOP', {'username': sender})
            self.broadcast_tcp(msg, exclude_user=sender)
        
        elif msg_type == 'SPEAKING_STATUS':
            msg = self.encode_message('SPEAKING_STATUS', {
                'username': sender,
                'speaking': data['speaking']
            })
            self.broadcast_tcp(msg, exclude_user=sender)
    
    def handle_udp_video(self):
        """Handle UDP video streams"""
        print("[UDP] Video handler started")
        while self.running:
            try:
                data, addr = self.udp_video_socket.recvfrom(65536)
                
                # Extract username from packet
                parts = data.split(b':', 2)
                if len(parts) < 3:
                    continue
                
                username = parts[1].decode('utf-8')
                
                # Update UDP address
                with self.client_lock:
                    if username in self.clients:
                        self.clients[username]['udp'] = addr
                        
                        # Broadcast to all except sender
                        for user, info in self.clients.items():
                            if user != username and info['udp'][1] > 0:
                                try:
                                    self.udp_video_socket.sendto(data, info['udp'])
                                except:
                                    pass
            except:
                pass
    
    def handle_udp_audio(self):
        """Handle UDP audio streams"""
        print("[UDP] Audio handler started")
        while self.running:
            try:
                data, addr = self.udp_audio_socket.recvfrom(65536)
                
                # Extract username
                parts = data.split(b':', 2)
                if len(parts) < 3:
                    continue
                
                username = parts[1].decode('utf-8')
                
                # Update UDP address
                with self.client_lock:
                    if username in self.clients:
                        self.clients[username]['udp'] = addr
                        
                        # Broadcast to all except sender
                        for user, info in self.clients.items():
                            if user != username and info['udp'][1] > 0:
                                try:
                                    self.udp_audio_socket.sendto(data, info['udp'])
                                except:
                                    pass
            except:
                pass
    
    def start(self):
        """Start the server"""
        # Start UDP handlers
        threading.Thread(target=self.handle_udp_video, daemon=True).start()
        threading.Thread(target=self.handle_udp_audio, daemon=True).start()
        
        # Accept TCP connections
        while self.running:
            try:
                client_socket, address = self.tcp_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket, address), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"[ERROR] Accept: {e}")
                break
    
    def stop(self):
        """Stop the server"""
        self.running = False
        try:
            self.tcp_socket.close()
            self.udp_video_socket.close()
            self.udp_audio_socket.close()
        except:
            pass
        print("\n[✓] Server stopped")

if __name__ == "__main__":
    server = IntraConnectServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[!] Server interrupted by user")
        server.stop()
    except Exception as e:
        print(f"[ERROR] {e}")
        server.stop()