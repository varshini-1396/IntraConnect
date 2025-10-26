"""
Screen Capture Module
Handles screen/slide capture for presentation
"""

import threading
import sys
sys.path.append('..')

try:
    from PIL import ImageGrab
except ImportError:
    print("[SCREEN] PIL not available, screen capture disabled")
    ImageGrab = None

try:
    import cv2
    import numpy as np
    from common.utils import compress_frame
except ImportError as e:
    print(f"[SCREEN] Required libraries not available: {e}")
    cv2 = None
    np = None
    compress_frame = None

class ScreenCapture:
    def __init__(self):
        self.running = False
        self.capturing = False
        self.current_frame = None
        self.lock = threading.Lock()
        
    def start_capture(self):
        """Start capturing screen"""
        if ImageGrab is None or cv2 is None or np is None:
            print("[SCREEN] Cannot start: dependencies not available")
            return False
            
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
                    if ImageGrab is None:
                        break
                    # Capture screen
                    screenshot = ImageGrab.grab()
                    
                    if screenshot is None:
                        continue
                    
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
                # Don't break on minor errors, just log and continue
                threading.Event().wait(0.1)
    
    def get_compressed_frame(self):
        """Get current screen frame compressed"""
        if compress_frame is None:
            return None
            
        with self.lock:
            if self.current_frame is not None:
                try:
                    compressed = compress_frame(self.current_frame, quality=70)
                    return compressed
                except Exception as e:
                    print(f"[SCREEN] Compression error: {e}")
                    return None
        return None
    
    def stop_capture(self):
        """Stop screen capture"""
        self.capturing = False
        self.running = False
        print("[SCREEN] Screen capture stopped")