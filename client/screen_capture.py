"""
Screen Capture Module
Handles screen/slide capture for presentation
"""

import threading
import sys
sys.path.append('..')
from PIL import ImageGrab
from common.utils import compress_frame
import cv2
import numpy as np

class ScreenCapture:
    def __init__(self):
        self.running = False
        self.capturing = False
        self.current_frame = None
        self.lock = threading.Lock()
        
    def start_capture(self):
        """Start capturing screen"""
        self.capturing = True
        self.running = True
        threading.Thread(target=self.capture_thread, daemon=True).start()
        print("[SCREEN] Screen capture started")
        return True
    
    def capture_thread(self):
        """Continuously capture screen"""
        while self.running:
            try:
                if self.capturing:
                    # Capture screen
                    screenshot = ImageGrab.grab()
                    
                    # Resize to reasonable size for transmission
                    screenshot = screenshot.resize((1280, 720))
                    
                    # Convert to numpy array
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    with self.lock:
                        self.current_frame = frame
                
                threading.Event().wait(0.1)  # 10 FPS for screen sharing
                
            except Exception as e:
                print(f"[SCREEN] Capture error: {e}")
    
    def get_compressed_frame(self):
        """Get current screen frame compressed"""
        with self.lock:
            if self.current_frame is not None:
                compressed = compress_frame(self.current_frame, quality=70)
                return compressed
        return None
    
    def stop_capture(self):
        """Stop screen capture"""
        self.capturing = False
        self.running = False
        print("[SCREEN] Screen capture stopped")