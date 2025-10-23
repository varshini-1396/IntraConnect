"""
File Transfer Client Module
Handles file upload and download
"""

import os
import sys
sys.path.append('..')
from common.protocol import send_message, receive_message
from common.config import MSG_FILE_INFO, MSG_FILE_REQUEST, FILE_CHUNK_SIZE

class FileClient:
    def __init__(self, socket):
        self.socket = socket
        self.available_files = {}  # {file_id: {filename, size, uploader}}
        
    def upload_file(self, filepath):
        """Upload file to server"""
        try:
            if not os.path.exists(filepath):
                return False, "File not found"
            
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            
            # Send file metadata
            send_message(self.socket, MSG_FILE_INFO, {
                'filename': filename,
                'size': filesize
            })
            
            # Send file data in chunks
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    self.socket.sendall(chunk)
            
            print(f"[FILE] Uploaded '{filename}'")
            return True, "File uploaded successfully"
            
        except Exception as e:
            print(f"[FILE] Upload error: {e}")
            return False, str(e)
    
    def download_file(self, file_id, save_path):
        """Download file from server"""
        try:
            # Request file
            send_message(self.socket, MSG_FILE_REQUEST, {'file_id': file_id})
            
            # Receive file metadata
            msg_type, data = receive_message(self.socket)
            if msg_type != MSG_FILE_INFO:
                return False, "Invalid response"
            
            filename = data['filename']
            filesize = data['size']
            
            # Receive file data
            received = 0
            filepath = os.path.join(save_path, filename)
            
            with open(filepath, 'wb') as f:
                while received < filesize:
                    chunk_size = min(FILE_CHUNK_SIZE, filesize - received)
                    chunk = self.socket.recv(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            if received == filesize:
                print(f"[FILE] Downloaded '{filename}'")
                return True, f"File saved to {filepath}"
            else:
                return False, "Incomplete download"
                
        except Exception as e:
            print(f"[FILE] Download error: {e}")
            return False, str(e)
    
    def add_available_file(self, file_id, filename, size, uploader):
        """Add file to available files list"""
        self.available_files[file_id] = {
            'filename': filename,
            'size': size,
            'uploader': uploader
        }
    
    def get_available_files(self):
        """Get list of available files"""
        return self.available_files.copy()