"""
File Transfer Client Module
Handles file upload and download - FIXED with secondary TCP socket
"""

import os
import sys
import socket
import struct
import threading
import time
sys.path.append('..')
from common.protocol import send_message, receive_message
from common.config import MSG_FILE_INFO, MSG_FILE_REQUEST, FILE_CHUNK_SIZE, FILE_TRANSFER_PORT
from common.utils import get_local_ip

class FileClient:
    def __init__(self, socket_conn, server_ip):
        self.socket = socket_conn
        self.server_ip = server_ip
        self.available_files = {}  # {file_id: {filename, size, uploader}}
        self.download_listener = None
        self.download_transfer_socket = None # Socket used for active download transfer
        self.running = False
        
        # Start permanent listening socket for downloads
        self.start_download_listener()
        
    def start_download_listener(self):
        """Start a thread to listen for incoming download connections from the server."""
        try:
            self.download_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.download_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to a specific port for server to connect back to
            self.download_listener.bind(('0.0.0.0', FILE_TRANSFER_PORT))
            self.download_listener.listen(1)
            self.running = True
            threading.Thread(target=self._download_listener_thread, daemon=True).start()
            print(f"[FILE] Download listener started on port {FILE_TRANSFER_PORT}")
        except Exception as e:
            print(f"[FILE] Failed to start download listener: {e}")
            
    def _download_listener_thread(self):
        """Accepts one download connection from server and stores the socket."""
        while self.running:
            try:
                # Accept connection from server (when server initiates download)
                conn, addr = self.download_listener.accept()
                print(f"[FILE] Download connection accepted from {addr}")
                self.download_transfer_socket = conn
                
            except Exception as e:
                if self.running:
                    # Ignore errors during shutdown
                    pass
    
    def upload_file(self, filepath):
        """Client requests file upload by sending metadata over main TCP channel."""
        try:
            if not os.path.exists(filepath):
                return False, "File not found"
            
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            
            # 1. Send file metadata (request to upload)
            if not send_message(self.socket, MSG_FILE_INFO, {
                'filename': filename,
                'size': filesize,
                'status': 'REQUEST_UPLOAD' # New status for server to handle
            }):
                return False, "Failed to send file info"
            
            # The actual upload transfer will be initiated by the main client thread
            # after receiving the READY_UPLOAD message from the server.
            return True, "Upload process initiated (waiting for server confirmation)"
            
        except Exception as e:
            return False, f"Upload error: {e}"
            
    def _initiate_upload_transfer(self, filename, filesize, filepath, ip, port):
        """Client connects to server's temporary socket and sends raw file data."""
        transfer_sock = None
        try:
            print(f"[FILE] Initiating upload transfer to {ip}:{port}")
            transfer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            transfer_sock.settimeout(5.0)
            transfer_sock.connect((ip, port))
            transfer_sock.settimeout(60.0)
            
            # Send file data in chunks
            bytes_sent = 0
            with open(filepath, 'rb') as f:
                while bytes_sent < filesize:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    transfer_sock.sendall(chunk)
                    bytes_sent += len(chunk)
                    
                    progress = (bytes_sent / filesize) * 100
                    if bytes_sent % (FILE_CHUNK_SIZE * 20) == 0 or bytes_sent == filesize:
                        print(f"[FILE] Upload progress: {progress:.1f}%")

            transfer_sock.close()
            
            if bytes_sent == filesize:
                return True, "File uploaded successfully"
            else:
                return False, "Incomplete upload"
                
        except socket.timeout:
            if transfer_sock: transfer_sock.close()
            return False, "Upload transfer timed out"
        except Exception as e:
            if transfer_sock: transfer_sock.close()
            return False, f"Upload transfer error: {e}"

    def download_file(self, file_id, save_path):
        """Client requests file download over main TCP channel."""
        try:
            # 1. Send file request
            if not send_message(self.socket, MSG_FILE_REQUEST, {'file_id': file_id}):
                return False, "Failed to send file request"
            
            # The actual download transfer will be initiated by the server connecting to the
            # client's listener, and then processed by the main client thread.
            return True, "Download request sent (waiting for server response)"
            
        except Exception as e:
            return False, str(e)
            
    def _initiate_download_transfer(self, file_id, filename, filesize, save_path):
        """Client receives file data on the pre-established listener socket."""
        conn = None
        try:
            # Wait for the transfer socket to be available (accepted by _download_listener_thread)
            timeout = time.time() + 5
            while self.download_transfer_socket is None and time.time() < timeout:
                time.sleep(0.1)
                
            if self.download_transfer_socket is None:
                return False, "Server failed to connect for download"

            conn = self.download_transfer_socket
            conn.settimeout(60.0)

            # 2. Receive file data
            received = 0
            filepath = os.path.join(save_path, filename)
            
            with open(filepath, 'wb') as f:
                while received < filesize:
                    remaining = filesize - received
                    chunk_size = min(FILE_CHUNK_SIZE, remaining)
                    
                    chunk = conn.recv(chunk_size)
                    if not chunk:
                        print("[FILE] Connection closed during download")
                        break
                    
                    f.write(chunk)
                    received += len(chunk)
                    
                    progress = (received / filesize) * 100
                    if received % (FILE_CHUNK_SIZE * 20) == 0 or received == filesize:
                        print(f"[FILE] Download progress: {progress:.1f}%")
            
            conn.close()
            self.download_transfer_socket = None # Clear for next download
            
            if received == filesize:
                return True, f"File saved to {filepath}"
            else:
                try:
                    os.remove(filepath)
                except:
                    pass
                return False, f"Incomplete download ({received}/{filesize} bytes)"
            
        except Exception as e:
            print(f"[FILE] Download transfer error: {e}")
            if conn: conn.close()
            self.download_transfer_socket = None
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
        
    def stop_listener(self):
        """Stop download listener"""
        self.running = False
        if self.download_listener:
            try:
                # Unblock the accept call
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('127.0.0.1', FILE_TRANSFER_PORT))
                s.close()
            except:
                pass
            self.download_listener.close()
            print("[FILE] Download listener stopped")