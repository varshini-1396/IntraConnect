"""
Main Client Application
Manages connection and coordinates all client modules
FIXED: File transfer blocking and threading issues
"""

import socket
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox
import sys
sys.path.append('..')
from common.protocol import send_message, receive_message
from common.config import (
    DEFAULT_PORT,
    MSG_CONNECT,
    MSG_USER_LIST,
    MSG_CHAT,
    MSG_FILE_INFO,
    MSG_SCREEN_START,
    MSG_SCREEN_STOP,
    MSG_SCREEN_FRAME,
    MSG_DISCONNECT,
)
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
        
        # Lock for socket operations
        self.socket_lock = threading.Lock()
        # Flag to pause generic receiver during file transfers
        self._in_file_transfer = threading.Event()
    
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
                # Adopt server-assigned unique username (prevents name collisions in media)
                assigned = data.get('username')
                if assigned and assigned != self.username:
                    print(f"[CLIENT] Assigned username from server: {assigned}")
                    self.username = assigned
                print(f"[CLIENT] Connected to server. Users online: {data['users']}")
                self.connected = True
                
                # Initialize modules with the final assigned username
                self.video_capture = VideoCapture(self.username)
                self.audio_capture = AudioCapture(self.username)
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
            import traceback
            traceback.print_exc()
            return False
    
    def receive_messages(self):
        """Receive messages from server"""
        while self.running:
            try:
                # If a file transfer is in progress, yield to it
                if self._in_file_transfer.is_set():
                    threading.Event().wait(0.05)
                    continue
                
                msg_type, data = receive_message(self.socket)
                
                if not msg_type:
                    break
                
                # Route message to appropriate handler
                if msg_type == MSG_CHAT:
                    self.chat_client.handle_received_message(data)
                
                elif msg_type == MSG_USER_LIST:
                    users = data.get('users', [])
                    # Update assigned username if server adjusted it
                    assigned = data.get('username')
                    if assigned and assigned != self.username:
                        print(f"[CLIENT] Assigned username: {assigned}")
                        self.username = assigned
                        # Propagate to media modules and GUI
                        try:
                            if self.video_capture:
                                self.video_capture.set_username(assigned)
                            if self.audio_capture:
                                self.audio_capture.set_username(assigned)
                            if self.gui:
                                self.gui.update_username(assigned)
                        except Exception:
                            pass
                    print(f"[CLIENT] Users online: {users}")
                    # Prune any stale remote videos immediately on user list update
                    if self.video_capture:
                        try:
                            allowed = set(users)
                            if self.username in allowed:
                                allowed.remove(self.username)
                            self.video_capture.prune_users(allowed)
                        except Exception:
                            pass
                
                elif msg_type == MSG_FILE_INFO:
                    # Check if it's an error or file availability notification
                    if 'error' in data:
                        print(f"[CLIENT] File error: {data['error']}")
                    else:
                        file_id = data.get('file_id')
                        filename = data.get('filename')
                        size = data.get('size')
                        uploader = data.get('uploader')
                        
                        if file_id and filename and size and uploader:
                            if self.gui:
                                # Update chat with a clickable file message and keep list in sync
                                self.gui.root.after(0, lambda: self.gui.add_file_message(file_id, filename, size, uploader))
                                self.gui.root.after(0, lambda: self.gui.add_file_to_list(file_id, filename, size, uploader))
                
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
                        try:
                            # Decompress and store frame in separate thread
                            threading.Thread(
                                target=self._decode_screen_frame,
                                args=(frame_data,),
                                daemon=True
                            ).start()
                        except Exception as e:
                            print(f"[CLIENT] Screen frame decode error: {e}")
                
            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Receive error: {e}")
                break
        
        print("[CLIENT] Receive thread stopped")
    
    def _decode_screen_frame(self, frame_data):
        """Decode screen frame in separate thread"""
        try:
            import base64
            frame_bytes = base64.b64decode(frame_data)
            frame = decompress_frame(frame_bytes)
            if frame is not None:
                self.shared_screen = frame
        except Exception as e:
            print(f"[CLIENT] Frame decode error: {e}")
    
    def enable_video(self):
        """Enable video streaming"""
        if not self.video_enabled:
            if self.video_capture.start_capture(self.server_ip):
                self.video_enabled = True
                print("[CLIENT] Video enabled")
                return True
        return False
    
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
                return True
        return False
    
    def disable_audio(self):
        """Disable audio streaming"""
        if self.audio_enabled:
            self.audio_capture.stop_audio()
            self.audio_enabled = False
            print("[CLIENT] Audio disabled")
    
    def start_screen_share(self):
        """Start screen sharing - Non-blocking"""
        try:
            print("[CLIENT] Requesting screen share...")
            
            # Request to start sharing
            with self.socket_lock:
                if not send_message(self.socket, MSG_SCREEN_START, {}):
                    print("[CLIENT] Failed to send screen start message")
                    return False
                
                # Wait for response with timeout
                self.socket.settimeout(5.0)
                try:
                    msg_type, data = receive_message(self.socket)
                finally:
                    self.socket.settimeout(None)
                
                if msg_type == MSG_SCREEN_START and data.get('success'):
                    print("[CLIENT] Screen share request approved")
                    
                    # Start capturing
                    if self.screen_capture.start_capture():
                        self.screen_sharing = True
                        
                        # Start sending frames
                        threading.Thread(target=self.send_screen_frames, daemon=True).start()
                        
                        print("[CLIENT] Screen sharing started")
                        return True
                    else:
                        print("[CLIENT] Failed to start screen capture")
                        return False
                else:
                    message = data.get('message', 'Unknown error') if data else 'No response'
                    print(f"[CLIENT] Screen sharing request denied: {message}")
                    return False
                
        except socket.timeout:
            print("[CLIENT] Screen share request timeout")
            return False
        except Exception as e:
            print(f"[CLIENT] Screen share error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def send_screen_frames(self):
        """Send screen frames to server"""
        import base64
        frame_count = 0
        
        while self.screen_sharing and self.running:
            try:
                compressed_frame = self.screen_capture.get_compressed_frame()
                
                if compressed_frame:
                    # Encode to base64 for JSON transmission
                    frame_b64 = base64.b64encode(compressed_frame).decode('utf-8')
                    
                    # Send with lock to prevent concurrent sends
                    with self.socket_lock:
                        if not send_message(self.socket, MSG_SCREEN_FRAME, {'frame': frame_b64}):
                            print("[CLIENT] Failed to send screen frame")
                            break
                    
                    frame_count += 1
                    if frame_count % 50 == 0:
                        print(f"[CLIENT] Sent {frame_count} screen frames")
                
                # 10 FPS for screen sharing
                threading.Event().wait(0.1)
                
            except Exception as e:
                print(f"[CLIENT] Screen frame send error: {e}")
                break
        
        print("[CLIENT] Screen frame sender stopped")
    
    def stop_screen_share(self):
        """Stop screen sharing"""
        if self.screen_sharing:
            print("[CLIENT] Stopping screen share...")
            self.screen_sharing = False
            self.screen_capture.stop_capture()
            
            # Send stop message
            try:
                with self.socket_lock:
                    send_message(self.socket, MSG_SCREEN_STOP, {})
            except Exception as e:
                print(f"[CLIENT] Error sending stop message: {e}")
            
            print("[CLIENT] Screen sharing stopped")
    
    def send_chat_message(self, message):
        """Send chat message"""
        try:
            self.chat_client.send_message(message)
            return True
        except Exception as e:
            print(f"[CLIENT] Chat send error: {e}")
            return False
    
    def on_chat_message(self, username, message, timestamp):
        """Callback for received chat message"""
        if self.gui:
            # Update GUI from main thread
            self.gui.root.after(0, 
                lambda: self.gui.add_chat_message(username, message, timestamp)
            )
    
    def upload_file(self, filepath):
        """Upload file to server - Thread-safe"""
        self._in_file_transfer.set()
        try:
            print(f"[CLIENT] Starting file upload: {filepath}")
            # Ensure exclusive access to the socket and pause receiver
            with self.socket_lock:
                success, message = self.file_client.upload_file(filepath)
            print(f"[CLIENT] Upload result: {message}")
            return success
        except Exception as e:
            print(f"[CLIENT] Upload error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._in_file_transfer.clear()
    
    def download_file(self, file_id, save_path):
        """Download file from server - Thread-safe"""
        self._in_file_transfer.set()
        try:
            print(f"[CLIENT] Starting file download: {file_id}")
            # Ensure exclusive access to the socket and pause receiver
            with self.socket_lock:
                success, message = self.file_client.download_file(file_id, save_path)
            print(f"[CLIENT] Download result: {message}")
            return success, message
        except Exception as e:
            print(f"[CLIENT] Download error: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            self._in_file_transfer.clear()
    
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
            with self.socket_lock:
                send_message(self.socket, MSG_DISCONNECT, {})
        except:
            pass
        
        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
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
        "Enter server IP address:",
        initialvalue=default_ip,
        parent=root
    )
    if not server_ip:
        return
    
    # Create client and connect
    client = CollaborationClient()
    
    print(f"[CLIENT] Connecting to {server_ip} as {username}...")
    
    if client.connect(username, server_ip):
        # Show main window
        root.deiconify()
        
        # Create GUI
        gui = CollaborationGUI(root, client)
        client.gui = gui
        
        # Auto-enable video and audio
        print("[CLIENT] Enabling video and audio...")
        client.enable_video()
        client.enable_audio()
        
        # Start GUI
        root.protocol("WM_DELETE_WINDOW", lambda: gui.disconnect())
        
        try:
            root.mainloop()
        except KeyboardInterrupt:
            print("\n[CLIENT] Interrupted")
            client.disconnect()
    else:
        messagebox.showerror("Connection Failed", "Could not connect to server.\n\nPlease check:\n- Server is running\n- IP address is correct\n- You're on the same network")

if __name__ == "__main__":
    main()