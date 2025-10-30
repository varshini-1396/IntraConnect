# LAN Collaboration System

A comprehensive multi-user communication application for Local Area Networks (LAN) featuring video conferencing, audio chat, screen sharing, text chat, and file transfer.

## Features

- **Multi-User Video Conferencing**: Real-time video streaming with multiple participants
- **Audio Conferencing**: Crystal-clear audio with server-side mixing
- **Screen Sharing**: Share your screen or presentations with all participants
- **Group Chat**: Real-time text messaging
- **File Sharing**: Upload and download files within the session

## Requirements

- Python 3.8 or higher
- Webcam and microphone
- Local Area Network connection

## Installation

1. Clone or download this repository

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. For Linux users, install PortAudio:

```bash
sudo apt-get install portaudio19-dev python3-pyaudio
```

4. For Windows users, PyAudio might need manual installation:

```bash
pip install pipwin
pipwin install pyaudio
```

## Usage

### Starting the Server

1. Navigate to the server directory:

```bash
cd server
```

2. Run the server:

```bash
python server.py
```

3. Note the server IP address displayed in the console

### Starting the Client

1. Navigate to the client directory:

```bash
cd client
```

2. Run the client:

```bash
python client.py
```

3. Enter your username when prompted

4. Enter the server IP address

5. The application will automatically enable video and audio

## Controls

- **Video ON/OFF**: Toggle your webcam
- **Audio ON/OFF**: Toggle your microphone
- **Start/Stop Sharing**: Share your screen
- **Send**: Send chat messages
- **Upload File**: Share files with all participants
- **Download Selected**: Download files shared by others
- **Disconnect**: Leave the session

## Network Ports

- Main Control Port: 5555 (TCP)
- Video Stream Port: 5556 (UDP)
- Audio Stream Port: 5557 (UDP)

## Troubleshooting

### Video not working

- Check webcam permissions
- Ensure no other application is using the camera
- Try adjusting VIDEO_QUALITY in config.py

### Audio issues

- Check microphone/speaker permissions
- Adjust AUDIO_CHUNK size in config.py for better performance
- Ensure no other audio application is running

### Connection issues

- Verify all devices are on the same network
- Check firewall settings and allow the ports
- Ensure server IP address is correct

## Architecture

The system uses a client-server architecture:

- **Server**: Manages sessions, relays data between clients
- **Client**: Captures/displays media, handles user interaction

Communication protocols:

- TCP: Reliable messaging (chat, files, control)
- UDP: Real-time streaming (video, audio)

## File Structure

```
lan-collaboration-system/
├── server/
│   ├── server.py              # Main server
│   ├── session_manager.py     # User management
│   ├── video_handler.py       # Video streaming
│   ├── audio_handler.py       # Audio mixing
│   ├── chat_handler.py        # Chat management
│   ├── file_handler.py        # File transfers
│   └── screen_handler.py      # Screen sharing
├── client/
│   ├── client.py              # Main client
│   ├── client_gui.py          # User interface
│   ├── video_capture.py       # Video capture/display
│   ├── audio_capture.py       # Audio capture/playback
│   ├── screen_capture.py      # Screen capture
│   ├── chat_client.py         # Chat functionality
│   └── file_client.py         # File transfer client
├── common/
│   ├── config.py              # Configuration
│   ├── protocol.py            # Communication protocol
│   └── utils.py               # Utility functions
└── requirements.txt           # Dependencies
```

## License

This project is for educational purposes.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

