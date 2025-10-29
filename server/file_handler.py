"""
File Handler - Manages file uploads and downloads
Fixed version with proper error handling
"""

import uuid
import threading
import socket
from common.protocol import send_message, receive_message
from common.config import MSG_FILE_INFO, MSG_FILE_DATA, FILE_CHUNK_SIZE

class FileHandler:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.lock = threading.Lock()
    
    def handle_file_upload(self, username, sock):
        """Handle file upload from client - Fixed version"""
        try:
            # Set socket timeout
            original_timeout = sock.gettimeout()
            sock.settimeout(30.0)
            
            try:
                # Receive file metadata (already received in server.py, passed as data)
                # We need to read it here
                msg_type, data = receive_message(sock)
                
                if msg_type != MSG_FILE_INFO:
                    print(f"[FILE] Invalid message type: {msg_type}")
                    return False
                
                filename = data.get('filename')
                filesize = data.get('size')
                
                if not filename or not filesize:
                    print("[FILE] Missing filename or filesize")
                    return False
                
                file_id = str(uuid.uuid4())
                
                print(f"[FILE] Receiving '{filename}' ({filesize} bytes) from {username}")
                
                # Receive file data in chunks
                file_data = b''
                received = 0
                
                while received < filesize:
                    remaining = filesize - received
                    chunk_size = min(FILE_CHUNK_SIZE, remaining)
                    
                    try:
                        chunk = sock.recv(chunk_size)
                        if not chunk:
                            print("[FILE] Connection closed during upload")
                            break
                        
                        file_data += chunk
                        received += len(chunk)
                        
                        # Progress logging
                        progress = (received / filesize) * 100
                        if received % (FILE_CHUNK_SIZE * 10) == 0 or received == filesize:
                            print(f"[FILE] Upload progress: {progress:.1f}%")
                    
                    except socket.timeout:
                        print("[FILE] Upload timeout")
                        break
                    except socket.error as e:
                        print(f"[FILE] Socket error: {e}")
                        break
                
                # Restore original timeout
                sock.settimeout(original_timeout)
                
                if received == filesize:
                    # Store file
                    with self.lock:
                        self.session_manager.add_file(file_id, filename, filesize, file_data, username)
                    
                    print(f"[FILE] ✓ File '{filename}' received successfully")
                    
                    # Notify all clients about new file
                    self.broadcast_file_available(file_id, filename, filesize, username)
                    return True
                else:
                    print(f"[FILE] File transfer incomplete: {received}/{filesize} bytes")
                    return False
            
            finally:
                # Always restore timeout
                sock.settimeout(original_timeout)
                
        except Exception as e:
            print(f"[FILE] Upload error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def handle_file_download(self, username, sock, file_id):
        """Handle file download request - Fixed version"""
        try:
            # Get file info
            with self.lock:
                file_info = self.session_manager.get_file(file_id)
            
            if not file_info:
                print(f"[FILE] File not found: {file_id}")
                send_message(sock, MSG_FILE_INFO, {'error': 'File not found'})
                return False
            
            filename = file_info['filename']
            filesize = file_info['size']
            file_data = file_info['data']
            
            print(f"[FILE] Sending '{filename}' ({filesize} bytes) to {username}")
            
            # Send file metadata
            if not send_message(sock, MSG_FILE_INFO, {
                'file_id': file_id,
                'filename': filename,
                'size': filesize
            }):
                print("[FILE] Failed to send file metadata")
                return False
            
            # Set socket timeout
            original_timeout = sock.gettimeout()
            sock.settimeout(30.0)
            
            try:
                # Send file data in chunks
                bytes_sent = 0
                total_size = len(file_data)
                
                while bytes_sent < total_size:
                    chunk_end = min(bytes_sent + FILE_CHUNK_SIZE, total_size)
                    chunk = file_data[bytes_sent:chunk_end]
                    
                    try:
                        sock.sendall(chunk)
                        bytes_sent += len(chunk)
                        
                        # Progress logging
                        progress = (bytes_sent / total_size) * 100
                        if bytes_sent % (FILE_CHUNK_SIZE * 10) == 0 or bytes_sent == total_size:
                            print(f"[FILE] Send progress: {progress:.1f}%")
                    
                    except socket.error as e:
                        print(f"[FILE] Socket error during send: {e}")
                        break
                
                # Restore timeout
                sock.settimeout(original_timeout)
                
                if bytes_sent == total_size:
                    print(f"[FILE] ✓ Sent '{filename}' to {username} successfully")
                    return True
                else:
                    print(f"[FILE] Incomplete send: {bytes_sent}/{total_size} bytes")
                    return False
            
            finally:
                sock.settimeout(original_timeout)
                
        except Exception as e:
            print(f"[FILE] Download error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def broadcast_file_available(self, file_id, filename, size, uploader):
        """Notify all clients about available file"""
        file_data = {
            'file_id': file_id,
            'filename': filename,
            'size': size,
            'uploader': uploader
        }
        
        print(f"[FILE] Broadcasting file availability: {filename}")
        
        sockets = self.session_manager.get_all_sockets_except()
        for username, sock in sockets:
            try:
                send_message(sock, MSG_FILE_INFO, file_data)
                print(f"[FILE] Notified {username} about {filename}")
            except Exception as e:
                print(f"[FILE] Failed to notify {username}: {e}")
