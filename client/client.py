"""
Main Client Application
Manages connection and coordinates all client modules
"""

import socket
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox
import sys
sys.path.append('..')
from common.protocol import send_message, receive_message
from common.config import *
from common.utils import get_local_ip, decompress_frame
from video_capture import VideoCapture
from audio_capture import AudioCapture
from screen_capture import ScreenCapture
from chat_client import ChatClient
from file_client import FileClient
from client_gui import CollaborationGUI

class CollaborationClient:
    def __init__(self):
        self.username = None
        self.server_ip = None
        self.socket = None
        self.connected = False
        
        # Module instances
        self.video_capture = None
        self.audio_capture = None
        self.screen_capture = None
        self.chat_client = None
        self.file_client = None
        self.gui = None
        
        # State flags
        self.video_enabled = False
        self.audio_enabled = False
        self.screen_sharing = False
        
        # Shared screen from presenter
        self.shared_screen = None
        
        # Running flag
        self.running = False
    
    def connect(self, username, server_ip):
        """Connect to server"""
        try:
            self.username = username
            self.server_ip = server_ip
            
            # Create TCP socket for control messages
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, DEFAULT_PORT))
            
            # Send connection message
            send_message(self.socket, MSG_CONNECT, {'username': username})
            
            # Wait for response
            msg_type, data = receive_message(self.socket)
            if msg_type == MSG_USER_LIST:
                print(f"[CLIENT] Connected to server. Users online: {data['users']}")
                self.connected = True
                
                # Initialize modules
                self.video_capture = VideoCapture(username)
                self.audio_capture = AudioCapture(username)
                self.screen_capture = ScreenCapture()
                self.chat_client = ChatClient(self.socket, self.on_chat_message)
                self.file_client = FileClient(self.socket)
                
                # Start receiver thread
                self.running = True
                threading.Thread(target=self.receive_messages, daemon=True).start()
                
                return True
            else:
                print("[CLIENT] Connection failed")
                return False
                
        except Exception as e:
            print(f"[CLIENT] Connection error: {e}")
            return False
    
    def receive_messages(self):
        """Receive messages from server"""
        while self.running:
            try:
                msg_type, data = receive_message(self.socket)
                
                if not msg_type:
                    break
                
                # Route message to appropriate handler
                if msg_type == MSG_CHAT:
                    self.chat_client.handle_received_message(data)
                
                elif msg_type == MSG_USER_LIST:
                    users = data.get('users', [])
                    print(f"[CLIENT] Users online: {users}")
                
                elif msg_type == MSG_FILE_INFO:
                    file_id = data.get('file_id')
                    filename = data.get('filename')
                    size = data.get('size')
                    uploader = data.get('uploader')
                    
                    if self.gui:
                        self.gui.add_file_to_list(file_id, filename, size, uploader)
                
                elif msg_type == MSG_SCREEN_START:
                    presenter = data.get('presenter')
                    print(f"[CLIENT] {presenter} started screen sharing")
                
                elif msg_type == MSG_SCREEN_STOP:
                    presenter = data.get('presenter')
                    print(f"[CLIENT] {presenter} stopped screen sharing")
                    self.shared_screen = None
                
                elif msg_type == MSG_SCREEN_FRAME:
                    frame_data = data.get('frame')
                    if frame_data:
                        # Decompress and store frame
                        import base64
                        frame_bytes = base64.b64decode(frame_data)
                        frame = decompress_frame(frame_bytes)
                        self.shared_screen = frame
                
            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Receive error: {e}")
                break
        
        print("[CLIENT] Receive thread stopped")
    
    def enable_video(self):
        """Enable video streaming"""
        if not self.video_enabled:
            if self.video_capture.start_capture(self.server_ip):
                self.video_enabled = True
                print("[CLIENT] Video enabled")
    
    def disable_video(self):
        """Disable video streaming"""
        if self.video_enabled:
            self.video_capture.stop_capture()
            self.video_enabled = False
            print("[CLIENT] Video disabled")
    
    def enable_audio(self):
        """Enable audio streaming"""
        if not self.audio_enabled:
            if self.audio_capture.start_audio(self.server_ip):
                self.audio_enabled = True
                print("[CLIENT] Audio enabled")
    
    def disable_audio(self):
        """Disable audio streaming"""
        if self.audio_enabled:
            self.audio_capture.stop_audio()
            self.audio_enabled = False
            print("[CLIENT] Audio disabled")
    
    def start_screen_share(self):
        """Start screen sharing"""
        try:
            # Request to start sharing
            send_message(self.socket, MSG_SCREEN_START, {})
            
            # Wait for response
            msg_type, data = receive_message(self.socket)
            if msg_type == MSG_SCREEN_START and data.get('success'):
                self.screen_capture.start_capture()
                self.screen_sharing = True
                
                # Start sending frames
                threading.Thread(target=self.send_screen_frames, daemon=True).start()
                
                print("[CLIENT] Screen sharing started")
                return True
            else:
                print(f"[CLIENT] Screen sharing failed: {data.get('message')}")
                return False
                
        except Exception as e:
            print(f"[CLIENT] Screen share error: {e}")
            return False
    
    def send_screen_frames(self):
        """Send screen frames to server"""
        import base64
        
        while self.screen_sharing and self.running:
            try:
                compressed_frame = self.screen_capture.get_compressed_frame()
                if compressed_frame:
                    # Encode to base64 for JSON transmission
                    frame_b64 = base64.b64encode(compressed_frame).decode('utf-8')
                    send_message(self.socket, MSG_SCREEN_FRAME, {'frame': frame_b64})
                
                threading.Event().wait(0.1)  # 10 FPS
                
            except Exception as e:
                print(f"[CLIENT] Screen frame send error: {e}")
                break
    
    def stop_screen_share(self):
        """Stop screen sharing"""
        if self.screen_sharing:
            self.screen_sharing = False
            self.screen_capture.stop_capture()
            send_message(self.socket, MSG_SCREEN_STOP, {})
            print("[CLIENT] Screen sharing stopped")
    
    def send_chat_message(self, message):
        """Send chat message"""
        self.chat_client.send_message(message)
    
    def on_chat_message(self, username, message, timestamp):
        """Callback for received chat message"""
        if self.gui:
            self.gui.add_chat_message(username, message, timestamp)
    
    def upload_file(self, filepath):
        """Upload file to server"""
        success, message = self.file_client.upload_file(filepath)
        return success
    
    def download_file(self, file_id, save_path):
        """Download file from server"""
        return self.file_client.download_file(file_id, save_path)
    
    def disconnect(self):
        """Disconnect from server"""
        print("[CLIENT] Disconnecting...")
        self.running = False
        
        # Stop all modules
        if self.video_enabled:
            self.disable_video()
        if self.audio_enabled:
            self.disable_audio()
        if self.screen_sharing:
            self.stop_screen_share()
        
        # Send disconnect message
        try:
            send_message(self.socket, MSG_DISCONNECT, {})
        except:
            pass
        
        # Close socket
        if self.socket:
            self.socket.close()
        
        print("[CLIENT] Disconnected")

def main():
    # Create root window
    root = tk.Tk()
    root.withdraw()  # Hide main window initially
    
    # Get username
    username = simpledialog.askstring("Username", "Enter your username:", parent=root)
    if not username:
        return
    
    # Get server IP
    default_ip = get_local_ip()
    server_ip = simpledialog.askstring(
        "Server IP",
        f"Enter server IP address:",
        initialvalue=default_ip,
        parent=root
    )
    if not server_ip:
        return
    
    # Create client and connect
    client = CollaborationClient()
    
    if client.connect(username, server_ip):
        # Show main window
        root.deiconify()
        
        # Create GUI
        gui = CollaborationGUI(root, client)
        client.gui = gui
        
        # Auto-enable video and audio
        client.enable_video()
        client.enable_audio()
        
        # Start GUI
        root.protocol("WM_DELETE_WINDOW", lambda: gui.disconnect())
        root.mainloop()
    else:
        messagebox.showerror("Connection Failed", "Could not connect to server")

if __name__ == "__main__":
    main()
