"""
File Handler - Manages file uploads and downloads
"""

import uuid
import threading
from common.protocol import send_message, receive_message
from common.config import MSG_FILE_INFO, MSG_FILE_DATA, FILE_CHUNK_SIZE

class FileHandler:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.lock = threading.Lock()
    
    def handle_file_upload(self, username, sock):
        """Handle file upload from client"""
        try:
            # Receive file metadata
            msg_type, data = receive_message(sock)
            if msg_type != MSG_FILE_INFO:
                return False
            
            filename = data['filename']
            filesize = data['size']
            file_id = str(uuid.uuid4())
            
            print(f"[FILE] Receiving '{filename}' ({filesize} bytes) from {username}")
            
            # Receive file data in chunks
            file_data = b''
            received = 0
            
            while received < filesize:
                chunk_size = min(FILE_CHUNK_SIZE, filesize - received)
                chunk = sock.recv(chunk_size)
                if not chunk:
                    break
                file_data += chunk
                received += len(chunk)
            
            if received == filesize:
                # Store file
                self.session_manager.add_file(file_id, filename, filesize, file_data, username)
                print(f"[FILE] File '{filename}' received successfully")
                
                # Notify all clients about new file
                self.broadcast_file_available(file_id, filename, filesize, username)
                return True
            else:
                print("[FILE] File transfer incomplete")
                return False
                
        except Exception as e:
            print(f"[FILE] Upload error: {e}")
            return False
    
    def handle_file_download(self, username, sock, file_id):
        """Handle file download request"""
        try:
            file_info = self.session_manager.get_file(file_id)
            if not file_info:
                send_message(sock, MSG_FILE_DATA, {'error': 'File not found'})
                return False
            
            # Send file metadata
            send_message(sock, MSG_FILE_INFO, {
                'file_id': file_id,
                'filename': file_info['filename'],
                'size': file_info['size']
            })
            
            # Send file data
            sock.sendall(file_info['data'])
            print(f"[FILE] Sent '{file_info['filename']}' to {username}")
            return True
            
        except Exception as e:
            print(f"[FILE] Download error: {e}")
            return False
    
    def broadcast_file_available(self, file_id, filename, size, uploader):
        """Notify all clients about available file"""
        file_data = {
            'file_id': file_id,
            'filename': filename,
            'size': size,
            'uploader': uploader
        }
        
        sockets = self.session_manager.get_all_sockets_except(uploader)
        for username, sock in sockets:
            try:
                send_message(sock, MSG_FILE_INFO, file_data)
            except:
                print(f"[FILE] Failed to notify {username}")