"""
Chat Client Module
Handles chat message sending and receiving
"""

import sys
sys.path.append('..')
from common.protocol import send_message
from common.config import MSG_CHAT

class ChatClient:
    def __init__(self, socket, callback):
        self.socket = socket
        self.callback = callback  # Function to call when message received
        
    def send_message(self, message):
        """Send chat message to server"""
        try:
            send_message(self.socket, MSG_CHAT, {'message': message})
            return True
        except Exception as e:
            print(f"[CHAT] Send error: {e}")
            return False
    
    def handle_received_message(self, data):
        """Handle received chat message"""
        username = data.get('username', 'Unknown')
        message = data.get('message', '')
        timestamp = data.get('timestamp', '')
        
        # Call callback to update UI
        if self.callback:
            self.callback(username, message, timestamp)