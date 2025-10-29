"""
File Handler - Manages file uploads and downloads
Fixed version with proper error handling and secondary TCP socket for raw data
"""

import uuid
import threading
import socket
from common.protocol import send_message
from common.config import MSG_FILE_INFO, MSG_FILE_REQUEST, FILE_CHUNK_SIZE, FILE_TRANSFER_PORT
import os
import time

class FileHandler:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.lock = threading.Lock()
    
    def _create_transfer_socket(self, host, port=0):
        """Create a temporary listening socket for upload transfer"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to 0.0.0.0 to accept connection from the client, letting OS pick port (port=0)
        s.bind(('0.0.0.0', port)) 
        s.listen(1)
        return s
    
    def handle_file_upload(self, username, metadata):
        """Handle file upload: Server opens a temporary socket for the client to connect to."""
        temp_sock = None
        try:
            filename = metadata.get('filename')
            filesize = metadata.get('size')
            
            if not filename or not filesize:
                return False, "Invalid file metadata"
            
            # 1. Server creates a temporary listening socket
            host = self.session_manager.users[username]['address'][0]
            temp_sock = self._create_transfer_socket('0.0.0.0') # Bind to 0.0.0.0
            transfer_port = temp_sock.getsockname()[1]
            
            # 2. Server notifies client on main channel where to connect
            client_sock = self.session_manager.get_user_socket(username)
            if not send_message(client_sock, MSG_FILE_INFO, {
                'file_id': None, # No ID yet
                'filename': filename,
                'size': filesize,
                'status': 'READY_UPLOAD',
                'ip': host, # Tell client to connect to the server's primary IP
                'port': transfer_port
            }):
                temp_sock.close()
                return False, "Failed to signal upload readiness"
            
            print(f"[FILE] Ready to receive '{filename}' on {host}:{transfer_port}")
            
            # 3. Server accepts connection from client
            temp_sock.settimeout(10.0)
            conn, _ = temp_sock.accept()
            conn.settimeout(60.0)
            
            # 4. Receive file data
            file_data = b''
            received = 0
            
            while received < filesize:
                remaining = filesize - received
                chunk_size = min(FILE_CHUNK_SIZE, remaining)
                chunk = conn.recv(chunk_size)
                
                if not chunk:
                    print("[FILE] Connection closed during upload")
                    break
                
                file_data += chunk
                received += len(chunk)
                
                if received % (FILE_CHUNK_SIZE * 20) == 0 or received == filesize:
                    print(f"[FILE] Upload progress: {(received / filesize) * 100:.1f}%")
            
            conn.close()
            temp_sock.close()
            
            if received == filesize:
                file_id = str(uuid.uuid4())
                self.session_manager.add_file(file_id, filename, filesize, file_data, username)
                print(f"[FILE] ✓ File '{filename}' received and stored. ID: {file_id}")
                self.broadcast_file_available(file_id, filename, filesize, username)
                return True, "File uploaded successfully"
            else:
                return False, f"Incomplete upload: {received}/{filesize} bytes"
                
        except socket.timeout:
            print("[FILE] Upload connection timeout")
            if temp_sock: temp_sock.close()
            return False, "Upload timed out"
        except Exception as e:
            print(f"[FILE] Upload error: {e}")
            if temp_sock: temp_sock.close()
            return False, str(e)
    
    def handle_file_download(self, username, file_id):
        """Handle file download: Server connects to client on its download listener socket."""
        transfer_sock = None
        try:
            file_info = self.session_manager.get_file(file_id)
            client_sock = self.session_manager.get_user_socket(username)
            client_ip = self.session_manager.users[username]['address'][0]
            
            if not file_info:
                send_message(client_sock, MSG_FILE_INFO, {'error': 'File not found'})
                return False
            
            filename = file_info['filename']
            filesize = file_info['size']
            file_data = file_info['data']
            
            # 1. Server notifies client on main channel to expect connection
            transfer_port = FILE_TRANSFER_PORT
            
            if not send_message(client_sock, MSG_FILE_INFO, {
                'file_id': file_id,
                'filename': filename,
                'size': filesize,
                'status': 'READY_DOWNLOAD',
                'ip': client_ip, # Client doesn't need this, but structure is consistent
                'port': transfer_port
            }):
                return False, "Failed to signal download readiness"
            
            print(f"[FILE] Client ready for download. Connecting to {client_ip}:{transfer_port}...")

            # 2. Server creates a new socket and connects to the client's listening download port
            transfer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            transfer_sock.settimeout(5.0)
            transfer_sock.connect((client_ip, transfer_port))
            transfer_sock.settimeout(60.0)
            
            # 3. Server sends file data
            bytes_sent = 0
            total_size = len(file_data)
            
            while bytes_sent < total_size:
                chunk_end = min(bytes_sent + FILE_CHUNK_SIZE, total_size)
                chunk = file_data[bytes_sent:chunk_end]
                transfer_sock.sendall(chunk)
                bytes_sent += len(chunk)
                
                if bytes_sent % (FILE_CHUNK_SIZE * 20) == 0 or bytes_sent == total_size:
                    print(f"[FILE] Send progress: {(bytes_sent / total_size) * 100:.1f}%")

            transfer_sock.close()
            
            if bytes_sent == total_size:
                print(f"[FILE] ✓ Sent '{filename}' to {username} successfully")
                return True
            else:
                return False

        except socket.timeout:
            print("[FILE] Download connection timeout")
            if transfer_sock: transfer_sock.close()
            return False
        except Exception as e:
            print(f"[FILE] Download error: {e}")
            if transfer_sock: transfer_sock.close()
            return False
    
    def broadcast_file_available(self, file_id, filename, size, uploader):
        """Notify all clients about available file"""
        # Send full file metadata on the main channel
        file_data = {
            'file_id': file_id,
            'filename': filename,
            'size': size,
            'uploader': uploader,
            'status': 'AVAILABLE' # Signal for client GUI to list the file
        }
        
        print(f"[FILE] Broadcasting file availability: {filename}")
        
        sockets = self.session_manager.get_all_sockets_except()
        for username, sock in sockets:
            try:
                send_message(sock, MSG_FILE_INFO, file_data)
            except Exception as e:
                print(f"[FILE] Failed to notify {username}: {e}")