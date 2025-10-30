"""
Protocol definitions for client-server communication
Handles message serialization and deserialization
"""

import json
import struct

def encode_message(msg_type, data):
    """
    Encode a message for transmission
    Format: [4 bytes length][msg_type][json data]
    """
    message = {
        'type': msg_type,
        'data': data
    }
    json_data = json.dumps(message).encode('utf-8')
    length = struct.pack('!I', len(json_data))
    return length + json_data

def decode_message(data):
    """
    Decode received message
    Returns: (msg_type, data_dict)
    """
    try:
        message = json.loads(data.decode('utf-8'))
        return message['type'], message['data']
    except:
        return None, None

def receive_message(sock):
    """
    Receive a complete message from socket
    """
    try:
        # Read message length (4 bytes)
        raw_length = sock.recv(4)
        if not raw_length:
            return None, None
        
        msg_length = struct.unpack('!I', raw_length)[0]
        
        # Read the message data
        data = b''
        while len(data) < msg_length:
            packet = sock.recv(min(msg_length - len(data), 4096))
            if not packet:
                return None, None
            data += packet
        
        return decode_message(data)
    except:
        return None, None

def send_message(sock, msg_type, data):
    """
    Send a message through socket
    """
    try:
        message = encode_message(msg_type, data)
        sock.sendall(message)
        return True
    except:
        return False