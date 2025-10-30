"""
File Transfer Client Module
Handles file upload and download - Fixed version
"""

import os
import sys
import socket
import struct
sys.path.append('..')
from common.protocol import send_message, receive_message
from common.config import MSG_FILE_INFO, MSG_FILE_REQUEST, FILE_CHUNK_SIZE

class FileClient:
    def __init__(self, socket_conn):
        self.socket = socket_conn
        self.available_files = {}  # {file_id: {filename, size, uploader}}
        
    def upload_file(self, filepath):
        """Upload file to server - Thread-safe version"""
        try:
            if not os.path.exists(filepath):
                print("[FILE] File not found")
                return False, "File not found"
            
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            
            print(f"[FILE] Uploading '{filename}' ({filesize} bytes)...")
            
            # Send file metadata
            if not send_message(self.socket, MSG_FILE_INFO, {
                'filename': filename,
                'size': filesize
            }):
                return False, "Failed to send file info"
            
            # Send file data in chunks
            bytes_sent = 0
            with open(filepath, 'rb') as f:
                while bytes_sent < filesize:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    try:
                        self.socket.sendall(chunk)
                        bytes_sent += len(chunk)
                        
                        # Progress logging
                        progress = (bytes_sent / filesize) * 100
                        if bytes_sent % (FILE_CHUNK_SIZE * 10) == 0 or bytes_sent == filesize:
                            print(f"[FILE] Upload progress: {progress:.1f}%")
                    
                    except socket.error as e:
                        print(f"[FILE] Socket error during upload: {e}")
                        return False, f"Upload failed: {str(e)}"
            
            if bytes_sent == filesize:
                print(f"[FILE] ✓ Uploaded '{filename}' successfully")
                return True, "File uploaded successfully"
            else:
                print(f"[FILE] Incomplete upload: {bytes_sent}/{filesize} bytes")
                return False, "Incomplete upload"
            
        except Exception as e:
            print(f"[FILE] Upload error: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def download_file(self, file_id, save_path):
        """Download file from server - Thread-safe version"""
        try:
            print(f"[FILE] Requesting file {file_id}...")
            
            # Request file
            if not send_message(self.socket, MSG_FILE_REQUEST, {'file_id': file_id}):
                return False, "Failed to send file request"
            
            # Set socket timeout for receiving
            original_timeout = self.socket.gettimeout()
            self.socket.settimeout(30.0)  # 30 second timeout
            
            try:
                # Receive file metadata
                msg_type, data = receive_message(self.socket)
                
                if msg_type != MSG_FILE_INFO:
                    print(f"[FILE] Invalid response: {msg_type}")
                    return False, "Invalid response from server"
                
                if 'error' in data:
                    return False, data['error']
                
                filename = data['filename']
                filesize = data['size']
                
                print(f"[FILE] Downloading '{filename}' ({filesize} bytes)...")
                
                # Receive file data
                received = 0
                filepath = os.path.join(save_path, filename)
                
                with open(filepath, 'wb') as f:
                    while received < filesize:
                        remaining = filesize - received
                        chunk_size = min(FILE_CHUNK_SIZE, remaining)
                        
                        try:
                            chunk = self.socket.recv(chunk_size)
                            if not chunk:
                                print("[FILE] Connection closed during download")
                                break
                            
                            f.write(chunk)
                            received += len(chunk)
                            
                            # Progress logging
                            progress = (received / filesize) * 100
                            if received % (FILE_CHUNK_SIZE * 10) == 0 or received == filesize:
                                print(f"[FILE] Download progress: {progress:.1f}%")
                        
                        except socket.timeout:
                            print("[FILE] Download timeout")
                            break
                        except socket.error as e:
                            print(f"[FILE] Socket error during download: {e}")
                            break
                
                # Restore original timeout
                self.socket.settimeout(original_timeout)
                
                if received == filesize:
                    print(f"[FILE] ✓ Downloaded '{filename}' successfully")
                    return True, f"File saved to {filepath}"
                else:
                    print(f"[FILE] Incomplete download: {received}/{filesize} bytes")
                    # Delete incomplete file
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    return False, f"Incomplete download ({received}/{filesize} bytes)"
            
            finally:
                # Always restore timeout
                self.socket.settimeout(original_timeout)
                
        except Exception as e:
            print(f"[FILE] Download error: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def add_available_file(self, file_id, filename, size, uploader):
        """Add file to available files list"""
        self.available_files[file_id] = {
            'filename': filename,
            'size': size,
            'uploader': uploader
        }
        print(f"[FILE] New file available: {filename} from {uploader}")
    
    def get_available_files(self):
        """Get list of available files"""
        return self.available_files.copy()