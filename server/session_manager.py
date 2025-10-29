"""
Session Manager - Handles user connections and session state
"""

import threading
from datetime import datetime

class SessionManager:
    def __init__(self):
        self.users = {}  # {username: {socket, address, video_port, audio_port}}
        self.lock = threading.Lock()
        self.presenter = None  # Current screen sharing presenter
        self.files = {}  # {file_id: {filename, size, data, uploader}}
        
    def add_user(self, username, sock, address):
        """Add a new user to the session; ensure unique username and RETURN the assigned username"""
        with self.lock:
            base = username.strip() or "User"
            assigned = base
            suffix = 1
            while assigned in self.users:
                suffix += 1
                assigned = f"{base}_{suffix}"
            
            self.users[assigned] = {
                'socket': sock,
                'address': address,
                'connected_at': datetime.now(),
                'video_active': False,
                'audio_active': False
            }
            print(f"[SESSION] User '{assigned}' joined from {address}")
            return assigned
    
    def remove_user(self, username):
        """Remove a user from the session"""
        with self.lock:
            if username in self.users:
                if self.presenter == username:
                    self.presenter = None
                del self.users[username]
                print(f"[SESSION] User '{username}' left")
                return True
            return False
    
    def get_user_list(self):
        """Get list of all connected users"""
        with self.lock:
            return list(self.users.keys())
    
    def get_user_socket(self, username):
        """Get socket for a specific user"""
        with self.lock:
            return self.users.get(username, {}).get('socket')
    
    def get_all_sockets_except(self, except_username=None):
        """Get all user sockets except specified one"""
        with self.lock:
            sockets = []
            for username, user_data in self.users.items():
                if username != except_username:
                    sockets.append((username, user_data['socket']))
            return sockets
    
    def set_presenter(self, username):
        """Set the current presenter for screen sharing"""
        with self.lock:
            if username in self.users:
                self.presenter = username
                return True
            return False
    
    def clear_presenter(self):
        """Clear the current presenter"""
        with self.lock:
            self.presenter = None
    
    def get_presenter(self):
        """Get current presenter username"""
        with self.lock:
            return self.presenter
    
    def add_file(self, file_id, filename, size, data, uploader):
        """Store uploaded file"""
        with self.lock:
            self.files[file_id] = {
                'filename': filename,
                'size': size,
                'data': data,
                'uploader': uploader,
                'uploaded_at': datetime.now()
            }
    
    def get_file(self, file_id):
        """Retrieve file data"""
        with self.lock:
            return self.files.get(file_id)
    
    def get_user_count(self):
        """Get number of connected users"""
        with self.lock:
            return len(self.users)