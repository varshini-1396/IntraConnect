"""
Main Server Application
Coordinates all handlers and manages client connections
"""

import socket
import threading
import sys
from session_manager import SessionManager
from chat_handler import ChatHandler
from file_handler import FileHandler
from screen_handler import ScreenHandler
from video_handler import VideoHandler
from audio_handler import AudioHandler
sys.path.append('..')
from common.protocol import receive_message, send_message
from common.config import *
from common.utils import get_local_ip

class CollaborationServer:
    def __init__(self, host='0.0.0.0', port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        
        # Initialize managers and handlers
        self.session_manager = SessionManager()
        self.chat_handler = ChatHandler(self.session_manager)
        self.file_handler = FileHandler(self.session_manager)
        self.screen_handler = ScreenHandler(self.session_manager)
        self.video_handler = VideoHandler(self.session_manager, host)
        self.audio_handler = AudioHandler(self.session_manager, host)
        
    def start(self):
        """Start the server"""
        try:
            # Create main TCP socket for control messages
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            # Start video and audio handlers
            self.video_handler.start()
            self.audio_handler.start()
            
            local_ip = get_local_ip()
            print("=" * 60)
            print(f"  LAN Collaboration Server Started")
            print("=" * 60)
            print(f"  Server IP: {local_ip}")
            print(f"  Main Port: {self.port}")
            print(f"  Video Port: {VIDEO_PORT}")
            print(f"  Audio Port: {AUDIO_PORT}")
            print("=" * 60)
            print("  Waiting for client connections...")
            print()
            
            # Accept client connections
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"[SERVER] New connection from {address}")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    if self.running:
                        print(f"[SERVER] Error accepting connection: {e}")
            
        except Exception as e:
            print(f"[SERVER] Failed to start: {e}")
        finally:
            self.stop()
    
    def handle_client(self, client_socket, address):
        """Handle individual client connection"""
        username = None
        
        try:
            # Wait for connection message with username
            msg_type, data = receive_message(client_socket)
            
            if msg_type == MSG_CONNECT:
                username = data.get('username', 'Unknown')
                
                # Add user to session
                self.session_manager.add_user(username, client_socket, address)
                
                # Send success response with user list
                user_list = self.session_manager.get_user_list()
                send_message(client_socket, MSG_USER_LIST, {'users': user_list})
                
                # Notify all other clients about new user
                self.broadcast_user_list()
                
                # Handle client messages
                while self.running:
                    msg_type, data = receive_message(client_socket)
                    
                    if not msg_type:
                        break
                    
                    # Route message to appropriate handler
                    if msg_type == MSG_CHAT:
                        self.chat_handler.handle_chat_message(username, data['message'])
                    
                    elif msg_type == MSG_FILE_INFO:
                        self.file_handler.handle_file_upload(username, client_socket)
                    
                    elif msg_type == MSG_FILE_REQUEST:
                        file_id = data.get('file_id')
                        self.file_handler.handle_file_download(username, client_socket, file_id)
                    
                    elif msg_type == MSG_SCREEN_START:
                        success, message = self.screen_handler.start_sharing(username)
                        send_message(client_socket, MSG_SCREEN_START, {
                            'success': success,
                            'message': message
                        })
                    
                    elif msg_type == MSG_SCREEN_STOP:
                        self.screen_handler.stop_sharing(username)
                    
                    elif msg_type == MSG_SCREEN_FRAME:
                        frame_data = data.get('frame')
                        self.screen_handler.broadcast_screen_frame(username, frame_data)
                    
                    elif msg_type == MSG_DISCONNECT:
                        break
        
        except Exception as e:
            print(f"[SERVER] Error handling client {username}: {e}")
        
        finally:
            # Clean up
            if username:
                self.session_manager.remove_user(username)
                self.broadcast_user_list()
                print(f"[SERVER] {username} disconnected")
            
            try:
                client_socket.close()
            except:
                pass
    
    def broadcast_user_list(self):
        """Broadcast updated user list to all clients"""
        user_list = self.session_manager.get_user_list()
        sockets = self.session_manager.get_all_sockets_except()
        
        for username, sock in sockets:
            try:
                send_message(sock, MSG_USER_LIST, {'users': user_list})
            except:
                pass
    
    def stop(self):
        """Stop the server"""
        print("\n[SERVER] Shutting down...")
        self.running = False
        
        # Stop handlers
        self.video_handler.stop()
        self.audio_handler.stop()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print("[SERVER] Server stopped")

def main():
    server = CollaborationServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Interrupted by user")
        server.stop()

if __name__ == "__main__":
    main()