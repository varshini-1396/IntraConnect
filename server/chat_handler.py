"""
Chat Handler - Manages group text chat
"""

import threading
from common.protocol import send_message
from common.config import MSG_CHAT

class ChatHandler:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.chat_history = []
        self.lock = threading.Lock()
    
    def handle_chat_message(self, username, message):
        """Process and broadcast chat message"""
        with self.lock:
            chat_data = {
                'username': username,
                'message': message,
                'timestamp': self.get_timestamp()
            }
            self.chat_history.append(chat_data)
            print(f"[CHAT] {username}: {message}")
        
        # Broadcast to all users
        self.broadcast_message(chat_data)
    
    def broadcast_message(self, chat_data):
        """Send chat message to all connected clients"""
        sockets = self.session_manager.get_all_sockets_except()
        for username, sock in sockets:
            try:
                send_message(sock, MSG_CHAT, chat_data)
            except:
                print(f"[CHAT] Failed to send message to {username}")
    
    def get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def get_history(self):
        """Get chat history"""
        with self.lock:
            return self.chat_history.copy()