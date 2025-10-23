"""
Screen Handler - Manages screen/slide sharing
"""

import threading
from common.protocol import send_message
from common.config import MSG_SCREEN_FRAME, MSG_SCREEN_START, MSG_SCREEN_STOP

class ScreenHandler:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.lock = threading.Lock()
    
    def start_sharing(self, username):
        """Start screen sharing for a user"""
        with self.lock:
            current_presenter = self.session_manager.get_presenter()
            if current_presenter and current_presenter != username:
                return False, f"{current_presenter} is already presenting"
            
            self.session_manager.set_presenter(username)
            print(f"[SCREEN] {username} started screen sharing")
            
            # Notify all clients
            self.broadcast_presenter_change(username, True)
            return True, "Screen sharing started"
    
    def stop_sharing(self, username):
        """Stop screen sharing"""
        with self.lock:
            if self.session_manager.get_presenter() == username:
                self.session_manager.clear_presenter()
                print(f"[SCREEN] {username} stopped screen sharing")
                
                # Notify all clients
                self.broadcast_presenter_change(username, False)
                return True
            return False
    
    def broadcast_screen_frame(self, username, frame_data):
        """Broadcast screen frame to all clients except presenter"""
        if self.session_manager.get_presenter() != username:
            return  # Only presenter can send frames
        
        sockets = self.session_manager.get_all_sockets_except(username)
        data = {'frame': frame_data}
        
        for user, sock in sockets:
            try:
                send_message(sock, MSG_SCREEN_FRAME, data)
            except:
                print(f"[SCREEN] Failed to send frame to {user}")
    
    def broadcast_presenter_change(self, username, is_starting):
        """Notify all clients about presenter change"""
        msg_type = MSG_SCREEN_START if is_starting else MSG_SCREEN_STOP
        data = {'presenter': username}
        
        sockets = self.session_manager.get_all_sockets_except()
        for user, sock in sockets:
            try:
                send_message(sock, msg_type, data)
            except:
                pass