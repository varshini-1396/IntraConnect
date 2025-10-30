"""
Screen Capture Module
Handles screen/slide capture for presentation - Fixed hanging issues
"""

import threading
import time
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
        self.capture_thread = None
        
    def start_capture(self):
        """Start capturing screen"""
        if ImageGrab is None or cv2 is None or np is None:
            print("[SCREEN] Cannot start: dependencies not available")
            return False
        
        if self.capturing:
            print("[SCREEN] Already capturing")
            return True
            
        self.capturing = True
        self.running = True
        
        # Start capture thread
        self.capture_thread = threading.Thread(target=self.capture_thread_func, daemon=True)
        self.capture_thread.start()
        
        print("[SCREEN] Screen capture started")
        return True
    
    def capture_thread_func(self):
        """Continuously capture screen - Non-blocking"""
        frame_count = 0
        last_capture_time = time.time()
        
        while self.running and self.capturing:
            try:
                current_time = time.time()
                
                # Capture at 10 FPS max
                if current_time - last_capture_time < 0.1:
                    time.sleep(0.02)
                    continue
                
                last_capture_time = current_time
                
                # Capture screen with timeout protection
                try:
                    screenshot = ImageGrab.grab()
                    
                    if screenshot is None:
                        time.sleep(0.1)
                        continue
                    
                    # Resize to reasonable size for transmission (720p)
                    screenshot = screenshot.resize((1280, 720))
                    
                    # Convert to numpy array
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # Store frame
                    with self.lock:
                        self.current_frame = frame
                    
                    frame_count += 1
                    
                    # Log progress occasionally
                    if frame_count % 50 == 0:
                        print(f"[SCREEN] Captured {frame_count} frames")
                
                except Exception as capture_error:
                    print(f"[SCREEN] Capture error: {capture_error}")
                    time.sleep(0.5)
                    continue
                
                # Small sleep to prevent CPU overload
                time.sleep(0.05)
                
            except Exception as e:
                print(f"[SCREEN] Thread error: {e}")
                time.sleep(0.5)
        
        print("[SCREEN] Capture thread stopped")
    
    def get_compressed_frame(self):
        """Get current screen frame compressed - Non-blocking"""
        if compress_frame is None:
            return None
        
        try:
            with self.lock:
                if self.current_frame is not None:
                    # Compress with timeout protection
                    compressed = compress_frame(self.current_frame, quality=60)
                    return compressed
        except Exception as e:
            print(f"[SCREEN] Compression error: {e}")
            return None
        
        return None
    
    def stop_capture(self):
        """Stop screen capture - Safe shutdown"""
        print("[SCREEN] Stopping screen capture...")
        self.capturing = False
        self.running = False
        
        # Wait for thread to finish (with timeout)
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        
        # Clear frame
        with self.lock:
            self.current_frame = None
        
        print("[SCREEN] Screen capture stopped")