"""
IntraConnect Client
Modern LAN collaboration client with video, audio, chat, screen sharing, and file transfer
"""

import socket
import threading
import struct
import json
import time
import os
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import sounddevice as sd
import mss
import base64

# Configure CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class IntraConnectClient:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("IntraConnect - LAN Collaboration Suite")
        self.root.geometry("1400x900")
        
        # Connection state
        self.server_ip = None
        self.username = None
        self.tcp_socket = None
        self.udp_socket = None
        self.connected = False
        
        # Media state
        self.video_on = False
        self.audio_on = False
        self.screen_on = False
        
        # Media capture
        self.video_cap = None
        self.audio_stream = None
        self.audio_out_stream = None
        self.sample_rate = 44100
        self.screen_capturer = None
        
        # Speaking detection
        self.is_speaking = False
        self.speaking_threshold = 500
        
        # Video displays
        self.video_displays = []
        self.received_videos = {}
        self.username_to_slot = {}
        
        # File tracking
        self.file_items = {}
        
        # Downloads folder
        self.downloads_folder = "downloads"
        os.makedirs(self.downloads_folder, exist_ok=True)
        
        # Blank images
        try:
            blank_img = Image.new('RGBA', (2, 2), (0, 0, 0, 0))
            self.blank_ctk_i = ctk.CTkImage(light_image=blank_img, size=(1, 1))
        except:
            self.blank_ctk_i = None
        
        # UI state
        self.current_panel = "video"
        self.panels = {}
        self.screen_popup = None
        self.screen_popup_label = None
        self.pending_users = None
        self.ui_ready = False
        
        self.setup_login_screen()
    
    def setup_login_screen(self):
        """Setup login screen"""
        self.login_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.login_frame.pack(expand=True)
        
        # Title
        ctk.CTkLabel(
            self.login_frame,
            text="IntraConnect",
            font=("Arial", 48, "bold"),
            text_color="#00ff88"
        ).pack(pady=(0, 10))
        
        ctk.CTkLabel(
            self.login_frame,
            text="LAN Collaboration Suite",
            font=("Arial", 16),
            text_color="gray"
        ).pack(pady=(0, 40))
        
        # Form
        form = ctk.CTkFrame(self.login_frame, width=450, height=350, corner_radius=12)
        form.pack()
        form.pack_propagate(False)
        
        form_inner = ctk.CTkFrame(form, fg_color="transparent")
        form_inner.pack(expand=True, padx=40, pady=40)
        
        # Server IP
        ctk.CTkLabel(form_inner, text="Server IP", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 5))
        self.server_entry = ctk.CTkEntry(form_inner, width=370, height=45, font=("Arial", 13))
        self.server_entry.pack(pady=(0, 20))
        self.server_entry.insert(0, "127.0.0.1")
        
        # Username
        ctk.CTkLabel(form_inner, text="Username", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 5))
        self.username_entry = ctk.CTkEntry(form_inner, width=370, height=45, font=("Arial", 13))
        self.username_entry.pack(pady=(0, 25))
        
        # Connect button
        self.connect_btn = ctk.CTkButton(
            form_inner,
            text="Connect",
            width=370,
            height=50,
            font=("Arial", 16, "bold"),
            corner_radius=8,
            command=self.connect_to_server
        )
        self.connect_btn.pack()
    
    def connect_to_server(self):
        """Connect to server"""
        self.server_ip = self.server_entry.get().strip()
        self.username = self.username_entry.get().strip()
        
        if not self.server_ip or not self.username:
            messagebox.showerror("Error", "Enter server IP and username")
            return
        
        self.connect_btn.configure(text="Connecting...", state="disabled")
        self.root.update()
        
        def connect_thread():
            try:
                # TCP
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tcp_socket.connect((self.server_ip, 5555))
                
                # UDP
                self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udp_socket.bind(('0.0.0.0', 0))
                udp_port = self.udp_socket.getsockname()[1]
                
                # Send connect message
                msg = self.encode_message('CONNECT', {'username': self.username, 'udp_port': udp_port})
                self.tcp_socket.sendall(msg)
                
                self.connected = True
                
                # Start receivers
                threading.Thread(target=self.tcp_receiver, daemon=True).start()
                threading.Thread(target=self.udp_receiver, daemon=True).start()
                
                self.root.after(0, self.setup_main_interface)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Connection failed: {e}"))
                self.root.after(0, lambda: self.connect_btn.configure(text="Connect", state="normal"))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def setup_main_interface(self):
        """Setup main interface"""
        self.login_frame.destroy()
        
        # Top bar
        topbar = ctk.CTkFrame(self.root, height=70, corner_radius=0, fg_color="#1a1a1a")
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        
        ctk.CTkLabel(
            topbar,
            text="IntraConnect",
            font=("Arial", 24, "bold"),
            text_color="#00ff88"
        ).pack(side="left", padx=25)
        
        ctk.CTkLabel(
            topbar,
            text=f"👤 {self.username}",
            font=("Arial", 13),
            text_color="white"
        ).pack(side="left", padx=20)
        
        # Controls
        controls = ctk.CTkFrame(topbar, fg_color="transparent")
        controls.pack(side="right", padx=25)
        
        self.video_btn = ctk.CTkButton(
            controls,
            text="📹 Video OFF",
            width=130,
            height=42,
            font=("Arial", 12, "bold"),
            fg_color="#444",
            command=self.toggle_video
        )
        self.video_btn.pack(side="left", padx=5)
        
        self.audio_btn = ctk.CTkButton(
            controls,
            text="🎤 Mic OFF",
            width=130,
            height=42,
            font=("Arial", 12, "bold"),
            fg_color="#444",
            command=self.toggle_audio
        )
        self.audio_btn.pack(side="left", padx=5)
        
        self.screen_btn = ctk.CTkButton(
            controls,
            text="🖥️ Share OFF",
            width=130,
            height=42,
            font=("Arial", 12, "bold"),
            fg_color="#444",
            command=self.toggle_screen
        )
        self.screen_btn.pack(side="left", padx=5)
        
        # Main area
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Sidebar
        sidebar = ctk.CTkFrame(main, width=70, corner_radius=12, fg_color="#1a1a1a")
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)
        
        # Content area
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True)
        
        # Video panel
        video_panel = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
        video_panel.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            video_panel,
            text="Video Conference",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        ).pack(anchor="w", pady=(0, 5))
        
        video_grid = ctk.CTkFrame(video_panel, corner_radius=12, fg_color="#1a1a1a")
        video_grid.pack(fill="both", expand=True)
        
        # Create video tiles (3x4 grid)
        for i in range(12):
            row, col = i // 4, i % 4
            tile = ctk.CTkFrame(video_grid, corner_radius=8, border_width=0, fg_color="#2a2a2a")
            tile.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            
            label = ctk.CTkLabel(
                tile,
                text="📷 Off" if i == 0 else f"User {i}",
                font=("Arial", 12),
                text_color="gray"
            )
            label.place(relx=0.5, rely=0.5, anchor="center")
            
            name = ctk.CTkLabel(
                tile,
                text="Your Video" if i == 0 else "",
                font=("Arial", 10, "bold"),
                corner_radius=4
            )
            name.place(relx=0.5, rely=0.95, anchor="center")
            
            self.video_displays.append({
                'frame': tile,
                'label': label,
                'name': name,
                'last_frame': None,
                'video_active': False,
                'speaking': False
            })
        
        for i in range(4):
            video_grid.grid_columnconfigure(i, weight=1)
        for i in range(3):
            video_grid.grid_rowconfigure(i, weight=1)
        
        # Chat panel
        chat_panel = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
        
        chat_title = ctk.CTkLabel(
            chat_panel,
            text="💬 Group Chat",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        )
        chat_title.pack(anchor="w", pady=(0, 5))
        
        self.chat_box = ctk.CTkTextbox(
            chat_panel,
            corner_radius=8,
            fg_color="#1a1a1a",
            font=("Arial", 11),
            wrap="word"
        )
        self.chat_box.pack(fill="both", expand=True, pady=(0, 5))
        
        chat_input = ctk.CTkFrame(chat_panel, fg_color="transparent")
        chat_input.pack(fill="x", pady=(0, 10))
        
        self.chat_entry = ctk.CTkEntry(
            chat_input,
            height=40,
            font=("Arial", 11),
            placeholder_text="Type message..."
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda e: self.send_chat())
        
        ctk.CTkButton(
            chat_input,
            text="Send",
            width=80,
            height=40,
            font=("Arial", 12, "bold"),
            command=self.send_chat
        ).pack(side="right")
        
        # Files panel
        files_panel = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
        
        files_title = ctk.CTkLabel(
            files_panel,
            text="📁 File Sharing",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        )
        files_title.pack(anchor="w", pady=(0, 5))
        
        ctk.CTkButton(
            files_panel,
            text="📤 Upload File",
            height=38,
            font=("Arial", 11, "bold"),
            command=self.upload_file
        ).pack(fill="x", pady=(0, 5))
        
        self.files_list = ctk.CTkScrollableFrame(files_panel, corner_radius=8, fg_color="#1a1a1a")
        self.files_list.pack(fill="both", expand=True)
        
        # Users panel
        users_panel = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
        
        users_title = ctk.CTkLabel(
            users_panel,
            text="👥 Connected Users",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        )
        users_title.pack(anchor="w", pady=(0, 5))
        
        self.users_frame = ctk.CTkScrollableFrame(users_panel, height=100, corner_radius=8, fg_color="#1a1a1a")
        self.users_frame.pack(fill="both", expand=True)
        
        self.panels = {
            'video': video_panel,
            'chat': chat_panel,
            'files': files_panel,
            'users': users_panel,
        }
        
        # Sidebar buttons
        def sidebar_btn(parent, text, panel=None, cmd=None):
            return ctk.CTkButton(
                parent,
                text=text,
                width=60,
                height=60,
                font=("Arial", 20, "bold"),
                fg_color="#2a2a2a",
                command=lambda p=panel: self.switch_panel(p) if panel else cmd()
            )
        
        sidebar_btn(sidebar, "📹", panel="video").pack(padx=5, pady=(10, 5))
        sidebar_btn(sidebar, "🖥️", cmd=self.open_screen_popup).pack(padx=5, pady=5)
        sidebar_btn(sidebar, "💬", panel="chat").pack(padx=5, pady=5)
        sidebar_btn(sidebar, "📁", panel="files").pack(padx=5, pady=5)
        sidebar_btn(sidebar, "👥", panel="users").pack(padx=5, pady=5)
        
        self.switch_panel("video")
        
        self.add_chat_msg("System", "Connected to IntraConnect server!", "#00ff88")
        
        self.ui_ready = True
        
        # Apply any buffered user list
        if self.pending_users is not None:
            try:
                self.update_users(self.pending_users)
            except:
                pass
            self.pending_users = None
    
    # Media controls
    
    def toggle_video(self):
        """Toggle video"""
        if not self.video_on:
            if self.start_video():
                self.video_btn.configure(text="📹 Video ON", fg_color="#00ff88")
        else:
            self.stop_video()
            self.video_btn.configure(text="📹 Video OFF", fg_color="#444")
    
    def toggle_audio(self):
        """Toggle audio"""
        if not self.audio_on:
            if self.start_audio():
                self.audio_btn.configure(text="🎤 Mic ON", fg_color="#00ff88")
        else:
            self.stop_audio()
            self.audio_btn.configure(text="🎤 Mic OFF", fg_color="#444")
    
    def toggle_screen(self):
        """Toggle screen share"""
        if not self.screen_on:
            if self.start_screen():
                self.screen_btn.configure(text="🖥️ Share ON", fg_color="#00ff88")
        else:
            self.stop_screen()
            self.screen_btn.configure(text="🖥️ Share OFF", fg_color="#444")
    
    def open_camera(self):
        """Try to open a camera device reliably on Windows by testing multiple backends and indices."""
        backends = [
            getattr(cv2, 'CAP_DSHOW', 700),
            getattr(cv2, 'CAP_MSMF', 1400),
            getattr(cv2, 'CAP_ANY', 0),
        ]
        indices = [0, 1, 2]
        
        for backend in backends:
            for idx in indices:
                try:
                    cap = cv2.VideoCapture(idx, backend)
                    if not cap or not cap.isOpened():
                        if cap:
                            cap.release()
                        continue
                    
                    # Prefer MJPG for faster CPU encode if supported
                    try:
                        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    except:
                        pass
                    
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    cap.set(cv2.CAP_PROP_FPS, 15)
                    
                    # Validate by grabbing one frame
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap
                    cap.release()
                except:
                    try:
                        cap.release()
                    except:
                        pass
        
        return None
    
    def encode_frame_for_udp(self, frame, target_max=60000):
        """Encode frame as JPEG with size under target_max bytes by scaling/quality reduction."""
        try:
            h, w = frame.shape[:2]
            
            # Start with small size to avoid fragmentation
            target_sizes = [(320, 240), (288, 216), (256, 192)]
            qualities = [60, 50, 40, 35, 30]
            
            for (tw, th) in target_sizes:
                resized = cv2.resize(frame, (tw, th)) if (w, h) != (tw, th) else frame
                for q in qualities:
                    ok, buf = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, q])
                    if ok:
                        data = buf.tobytes()
                        if len(data) <= target_max:
                            return data
            
            # Fallback: return smallest we produced even if larger
            ok, buf = cv2.imencode('.jpg', cv2.resize(frame, (256, 192)), [cv2.IMWRITE_JPEG_QUALITY, 30])
            return buf.tobytes() if ok else None
        except:
            return None
    
    # Video
    
    def start_video(self):
        """Start video with robust backend/index probing."""
        try:
            cap = self.open_camera()
            if not cap:
                messagebox.showerror(
                    "Camera Error",
                    "Unable to access camera. Close apps using the camera (Zoom/Teams/Meet), "
                    "ensure permissions are granted, or try a different device."
                )
                return False
            
            self.video_cap = cap
            self.video_on = True
            threading.Thread(target=self.video_loop, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Video start failed: {e}")
            return False
    
    def video_loop(self):
        """Video streaming loop"""
        while self.video_on:
            ret, frame = self.video_cap.read()
            if ret:
                # Encode to safe UDP-sized JPEG (~60KB)
                compressed = self.encode_frame_for_udp(frame)
                if compressed:
                    packet = f"VIDEOFRAME:{self.username}:".encode() + compressed
                    try:
                        self.udp_socket.sendto(packet, (self.server_ip, 5556))
                    except:
                        pass
                
                # Display own video
                self.update_video(0, frame)
            
            time.sleep(1.0 / 15)
    
    def stop_video(self):
        """Stop video"""
        self.video_on = False
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        
        # Notify server
        msg = self.encode_message('VIDEO_STOP', {'username': self.username})
        try:
            self.tcp_socket.sendall(msg)
        except:
            pass
        
        # Clear own tile
        try:
            if self.blank_ctk_i:
                self.video_displays[0]['label'].configure(text="📷 Off", image=self.blank_ctk_i)
        except:
            pass
    
    # Audio
    
    def start_audio(self):
        """Start audio"""
        try:
            # Input stream (microphone)
            self.audio_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=1024,
                callback=self.audio_callback
            )
            
            # Output stream (speakers) - for playing received audio
            self.audio_out_stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=1024
            )
            
            self.audio_stream.start()
            self.audio_out_stream.start()
            self.audio_on = True
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Audio start failed: {e}")
            return False
    
    def audio_callback(self, indata, frames, time, status):
        """Callback for audio input - FIXED JSON serialization"""
        if not self.audio_on:
            return
        
        try:
            # Convert numpy array to bytes
            audio_data = indata.tobytes()
            
            # Speaking detection
            rms = np.sqrt(np.mean(np.square(indata))) * 1000  # Calculate RMS in millivolts
            current_speaking = rms > self.speaking_threshold
            
            # FIXED: Convert numpy bool_ to Python bool
            if bool(current_speaking) != self.is_speaking:
                self.is_speaking = bool(current_speaking)  # FIXED: Convert to Python bool
                msg = self.encode_message('SPEAKING_STATUS', {
                    'username': self.username,
                    'speaking': self.is_speaking  # Now using Python bool
                })
                try:
                    self.tcp_socket.sendall(msg)
                except:
                    pass
            
            # Send audio via UDP
            packet = f"AUDIOFRAME:{self.username}:".encode() + audio_data
            try:
                self.udp_socket.sendto(packet, (self.server_ip, 5557))
            except:
                pass
        except Exception as e:
            print(f"Audio callback error: {e}")
    
    def stop_audio(self):
        """Stop audio"""
        self.audio_on = False
        
        # Clear speaking status
        if hasattr(self, 'is_speaking') and self.is_speaking:
            msg = self.encode_message('SPEAKING_STATUS', {
                'username': self.username,
                'speaking': False
            })
            try:
                self.tcp_socket.sendall(msg)
            except:
                pass
            self.is_speaking = False
        
        try:
            if hasattr(self, 'audio_stream') and self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
            if hasattr(self, 'audio_out_stream') and self.audio_out_stream:
                self.audio_out_stream.stop()
                self.audio_out_stream.close()
        except Exception as e:
            print(f"Error stopping audio: {e}")
    
    # Screen share
    
    def start_screen(self):
        """Start screen share"""
        try:
            self.screen_capturer = mss.mss()
            self.screen_on = True
            msg = self.encode_message('SCREEN_START', {})
            self.tcp_socket.sendall(msg)
            threading.Thread(target=self.screen_loop, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Screen share failed: {e}")
            return False
    
    def screen_loop(self):
        """Screen sharing loop"""
        while self.screen_on:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[0]
                    shot = sct.grab(monitor)
                    frame = np.array(shot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    frame = cv2.resize(frame, (800, 600))
                    
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    compressed = buffer.tobytes()
                    frame_b64 = base64.b64encode(compressed).decode('utf-8')
                    
                    msg = self.encode_message('SCREEN_FRAME', {'frame': frame_b64})
                    self.tcp_socket.sendall(msg)
                
                time.sleep(1.0 / 10)
            except:
                pass
    
    def stop_screen(self):
        """Stop screen share"""
        self.screen_on = False
        if self.screen_capturer:
            try:
                self.screen_capturer.close()
            except:
                pass
            self.screen_capturer = None
        
        msg = self.encode_message('SCREEN_STOP', {})
        try:
            self.tcp_socket.sendall(msg)
        except:
            pass
    
    # Network
    
    def encode_message(self, msg_type, data):
        """Encode message"""
        message = {'type': msg_type, 'data': data}
        msg_json = json.dumps(message)
        msg_bytes = msg_json.encode('utf-8')
        length = struct.pack('>I', len(msg_bytes))
        return length + msg_bytes
    
    def tcp_receiver(self):
        """TCP receiver"""
        while self.connected:
            try:
                length_data = self.tcp_socket.recv(4)
                if not length_data:
                    break
                
                msg_length = struct.unpack('>I', length_data)[0]
                msg_data = b''
                while len(msg_data) < msg_length:
                    chunk = self.tcp_socket.recv(min(msg_length - len(msg_data), 4096))
                    if not chunk:
                        break
                    msg_data += chunk
                
                if len(msg_data) != msg_length:
                    continue
                
                msg_json = msg_data.decode('utf-8')
                message = json.loads(msg_json)
                self.handle_message(message)
            except:
                break
        
        self.connected = False
    
    def udp_receiver(self):
        """UDP receiver"""
        while self.connected:
            try:
                data, addr = self.udp_socket.recvfrom(65536)
                
                parts = data.split(b':', 2)
                if len(parts) < 3:
                    continue
                
                msg_type = parts[0].decode('utf-8')
                username = parts[1].decode('utf-8')
                payload = parts[2]
                
                if msg_type == 'VIDEOFRAME':
                    nparr = np.frombuffer(payload, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        slot = self.username_to_slot.get(username)
                        if slot is None:
                            # Allocate next available slot
                            for s in range(1, len(self.video_displays)):
                                if s not in self.username_to_slot.values():
                                    self.username_to_slot[username] = s
                                    try:
                                        self.video_displays[s]['name'].configure(text=username)
                                    except:
                                        pass
                                    slot = s
                                    break
                        
                        if slot is not None and slot < len(self.video_displays):
                            self.update_video(slot, frame, username)
                
                elif msg_type == 'AUDIOFRAME':
                    # FIXED: Only play audio from OTHER users, not yourself
                    if username != self.username:
                        if hasattr(self, 'audio_out_stream') and self.audio_out_stream and self.audio_out_stream.active:
                            try:
                                audio_data = np.frombuffer(payload, dtype='int16')
                                self.audio_out_stream.write(audio_data)
                            except Exception as e:
                                print(f"Error playing audio: {e}")
            except:
                pass
    
    def handle_message(self, message):
        """Handle TCP message"""
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'USER_LIST':
            users = data.get('users', [])
            if not self.ui_ready:
                self.pending_users = users
            else:
                self.root.after(0, lambda u=users: self.update_users(u))
        
        elif msg_type == 'CHAT':
            self.root.after(0, lambda: self.add_chat_msg(data['username'], data['message']))
        
        elif msg_type == 'VIDEO_FRAME':
            try:
                username = data.get('username')
                frame_b64 = data.get('frame')
                if not username or not frame_b64:
                    return
                
                frame_data = base64.b64decode(frame_b64)
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is None:
                    return
                
                slot = self.username_to_slot.get(username)
                if slot is None:
                    # Allocate next available slot
                    for s in range(1, len(self.video_displays)):
                        if s not in self.username_to_slot.values():
                            self.username_to_slot[username] = s
                            try:
                                self.video_displays[s]['name'].configure(text=username)
                            except:
                                pass
                            slot = s
                            break
                
                if slot is not None:
                    self.root.after(0, lambda s=slot, f=frame, u=username: self.update_video(s, f, u))
            except:
                pass
        
        elif msg_type == 'FILE_INFO':
            self.root.after(0, lambda: self.add_file_item(data))
            self.root.after(0, lambda: self.show_toast(f"{data.get('uploader','Someone')} shared {data.get('filename','a file')}"))
        
        elif msg_type == 'FILE_CHUNK':
            filename = data['filename']
            file_data = data['chunk'].encode('latin-1')
            filepath = os.path.join(self.downloads_folder, filename)
            with open(filepath, 'wb') as f:
                f.write(file_data)
            self.root.after(0, lambda: messagebox.showinfo("Download", f"Saved: {filepath}"))
        
        elif msg_type == 'SCREEN_START':
            pass
        
        elif msg_type == 'SCREEN_STOP':
            def reset_screen():
                try:
                    if self.screen_popup_label:
                        self.screen_popup_label.configure(text="🖥️ No screen being shared", image=None)
                except:
                    pass
            self.root.after(0, reset_screen)
        
        elif msg_type == 'SCREEN_FRAME':
            try:
                frame_data = base64.b64decode(data['frame'])
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is not None:
                    self.root.after(0, lambda f=frame: self.display_screen(f))
            except:
                pass
        
        elif msg_type == 'VIDEO_STOP':
            username = data['username']
            slot = self.username_to_slot.get(username)
            try:
                if slot is not None and slot < len(self.video_displays):
                    self.video_displays[slot]['video_active'] = False
                    if self.blank_ctk_i:
                        self.video_displays[slot]['label'].configure(
                            text="📷 Off",
                            image=self.blank_ctk_i
                        )
                    self.video_displays[slot]['name'].configure(text=username)
            except:
                pass
        
        elif msg_type == 'SPEAKING_STATUS':
            username = data['username']
            speaking = data['speaking']
            
            # Find user's slot
            if username == self.username:
                slot = 0
            else:
                slot = hash(username) % 5 + 1
            
            try:
                if speaking:
                    self.video_displays[slot]['frame'].configure(border_width=3, border_color="#00ff88")
                else:
                    self.video_displays[slot]['frame'].configure(border_width=0)
            except:
                pass
    
    # UI Updates
    
    def switch_panel(self, panel_name):
        for name, panel in self.panels.items():
            if str(panel.winfo_manager()):
                panel.pack_forget()
        
        if panel_name in self.panels:
            self.panels[panel_name].pack(fill="both", expand=True)
        
        self.current_panel = panel_name
    
    def open_screen_popup(self):
        try:
            if self.screen_popup and self.screen_popup.winfo_exists():
                self.screen_popup.focus()
                return
        except:
            pass
        
        self.screen_popup = ctk.CTkToplevel(self.root)
        self.screen_popup.title("Screen Share Viewer")
        self.screen_popup.geometry("820x640")
        
        self.screen_popup_label = ctk.CTkLabel(
            self.screen_popup,
            text="🖥️ No screen being shared",
            font=("Arial", 14),
            text_color="gray"
        )
        self.screen_popup_label.pack(expand=True, fill="both", padx=10, pady=10)
        
        def on_close():
            try:
                self.screen_popup.destroy()
            except:
                pass
            self.screen_popup = None
            self.screen_popup_label = None
        
        self.screen_popup.protocol("WM_DELETE_WINDOW", on_close)
    
    def update_video(self, slot, frame, name=""):
        """Update video display"""
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((320, 240))
            ctk_i = ctk.CTkImage(light_image=img, size=(320, 240))
            
            self.video_displays[slot]['label'].configure(image=ctk_i, text="")
            self.video_displays[slot]['label'].image = ctk_i
            self.video_displays[slot]['video_active'] = True
            
            if name:
                self.video_displays[slot]['name'].configure(text=name)
        except:
            pass
    
    def update_users(self, users):
        """Update user list"""
        for widget in self.users_frame.winfo_children():
            widget.destroy()
        
        # Ensure slot exists
        next_slot = 1
        for user in sorted([u for u in users if u != self.username]):
            if user not in self.username_to_slot:
                # Find next free slot
                while next_slot < len(self.video_displays) and next_slot in self.username_to_slot.values():
                    next_slot += 1
                if next_slot < len(self.video_displays):
                    self.username_to_slot[user] = next_slot
                    try:
                        self.video_displays[next_slot]['name'].configure(text=user)
                    except:
                        pass
                    next_slot += 1
                else:
                    try:
                        self.video_displays[self.username_to_slot[user]].configure(text=user)
                    except:
                        pass
        
        for user in users:
            frame = ctk.CTkFrame(self.users_frame, fg_color="#2a2a2a", height=35, corner_radius=6)
            frame.pack(fill="x", pady=2)
            frame.pack_propagate(False)
            
            icon = "👤" if user == self.username else "👥"
            ctk.CTkLabel(
                frame,
                text=f"{icon} {user}",
                font=("Arial", 11),
                anchor="w"
            ).pack(side="left", padx=10)
        
        # Remove mappings for users no longer present
        present = set(users)
        for uname, slot in list(self.username_to_slot.items()):
            if uname != self.username and uname not in present:
                try:
                    if self.blank_ctk_i:
                        self.video_displays[slot]['label'].configure(text="📷 Off", image=self.blank_ctk_i)
                    self.video_displays[slot]['name'].configure(text="")
                except:
                    pass
                del self.username_to_slot[uname]
    
    def display_screen(self, frame):
        """Display screen frame"""
        try:
            if not self.screen_popup_label:
                return
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((800, 600))
            ctk_i = ctk.CTkImage(light_image=img, size=(800, 600))
            
            self.screen_popup_label.configure(image=ctk_i, text="")
            self.screen_popup_label.image = ctk_i
        except:
            pass
    
    def show_toast(self, message):
        try:
            toast = ctk.CTkFrame(self.root, fg_color="#2a2a2a", corner_radius=8)
            label = ctk.CTkLabel(toast, text=message, font=("Arial", 11))
            label.pack(padx=12, pady=10)
            
            toast.update_idletasks()
            toast_width = toast.winfo_width() or 280
            toast_height = toast.winfo_height() or 50
            root_width = self.root.winfo_width()
            root_height = self.root.winfo_height()
            
            x = 10
            y = root_height - toast_height - 10
            toast.place(x=x, y=y)
            
            def destroy():
                try:
                    toast.destroy()
                except:
                    pass
            
            self.root.after(3500, destroy)
        except:
            pass
    
    # Chat
    
    def send_chat(self):
        """Send chat"""
        msg_text = self.chat_entry.get().strip()
        if msg_text and self.connected:
            msg = self.encode_message('CHAT', {'message': msg_text})
            try:
                self.tcp_socket.sendall(msg)
                self.add_chat_msg(self.username, msg_text, own=True)
                self.chat_entry.delete(0, 'end')
            except:
                pass
    
    def add_chat_msg(self, user, msg, color="white", own=False):
        """Add chat message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.chat_box.configure(state="normal")
        
        if own:
            self.chat_box.insert("end", f"[{timestamp}] You\n", "time")
            self.chat_box.insert("end", f"{msg}\n\n", "own")
        else:
            self.chat_box.insert("end", f"[{timestamp}] {user}\n", "time")
            self.chat_box.insert("end", f"{msg}\n\n", "other")
        
        self.chat_box.tag_config("time", foreground="gray")
        self.chat_box.tag_config("own", foreground="#00ff88")
        self.chat_box.tag_config("other", foreground="white")
        
        self.chat_box.configure(state="disabled")
        self.chat_box.see("end")
    
    # Files
    
    def upload_file(self):
        """Upload file"""
        filepath = filedialog.askopenfilename()
        if filepath:
            try:
                filename = os.path.basename(filepath)
                filesize = os.path.getsize(filepath)
                
                # Send file info
                msg = self.encode_message('FILE_INFO', {'filename': filename, 'size': filesize})
                self.tcp_socket.sendall(msg)
                
                # Send file data
                with open(filepath, 'rb') as f:
                    file_data = f.read()
                
                msg = self.encode_message('FILE_CHUNK', {'filename': filename, 'chunk': file_data.decode('latin-1')})
                self.tcp_socket.sendall(msg)
                
                messagebox.showinfo("Success", f"Uploaded: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Upload failed: {e}")
    
    def download_file(self, filename):
        """Download file"""
        msg = self.encode_message('FILE_REQUEST', {'filename': filename})
        try:
            self.tcp_socket.sendall(msg)
        except:
            pass
    
    def add_file_item(self, data):
        """Add file to list"""
        filename = data['filename']
        filesize = data['size']
        uploader = data['uploader']
        
        if filename in self.file_items:
            return
        
        file_frame = ctk.CTkFrame(self.files_list, fg_color="#2a2a2a", height=60, corner_radius=8)
        file_frame.pack(fill="x", pady=3)
        file_frame.pack_propagate(False)
        
        info_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        
        ctk.CTkLabel(
            info_frame,
            text=filename,
            font=("Arial", 11, "bold"),
            anchor="w"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"{filesize} bytes • by {uploader}",
            font=("Arial", 9),
            text_color="gray",
            anchor="w"
        ).pack(anchor="w")
        
        ctk.CTkButton(
            file_frame,
            text="⬇ Download",
            width=90,
            height=35,
            font=("Arial", 10, "bold"),
            command=lambda: self.download_file(filename)
        ).pack(side="right", padx=10)
        
        self.file_items[filename] = file_frame
    
    # App lifecycle
    
    def run(self):
        """Run the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window close - FIXED"""
        if messagebox.askokcancel("Quit", "Exit IntraConnect?"):
            self.connected = False
            
            # Stop media
            self.video_on = False
            self.audio_on = False
            self.screen_on = False
            
            time.sleep(0.2)
            
            # Cleanup - FIXED: Use correct attribute names
            if self.video_cap:
                try:
                    self.video_cap.release()
                except:
                    pass
            
            # FIXED: Changed from self.audio_in to self.audio_stream
            if hasattr(self, 'audio_stream') and self.audio_stream:
                try:
                    self.audio_stream.stop()
                    self.audio_stream.close()
                except:
                    pass
            
            # FIXED: Changed from self.audio_out to self.audio_out_stream
            if hasattr(self, 'audio_out_stream') and self.audio_out_stream:
                try:
                    self.audio_out_stream.stop()
                    self.audio_out_stream.close()
                except:
                    pass
            
            # FIXED: Removed self.audio.terminate() - sounddevice doesn't need this
            
            if self.screen_capturer:
                try:
                    self.screen_capturer.close()
                except:
                    pass
            
            if self.tcp_socket:
                try:
                    self.tcp_socket.close()
                except:
                    pass
            
            if self.udp_socket:
                try:
                    self.udp_socket.close()
                except:
                    pass
            
            self.root.destroy()


if __name__ == "__main__":
    print("="*70)
    print(" "*20 + "IntraConnect Client")
    print("="*70)
    print("\nINFO: Starting application...")
    
    # Check dependencies
    try:
        import cv2
        import sounddevice
        import mss
        import customtkinter
        from PIL import Image
        import numpy
        print("✓ All dependencies found")
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Install with: pip install opencv-python sounddevice pillow numpy mss customtkinter")
        exit(1)
    
    print("✓ Initializing GUI...")
    print("="*70 + "\n")
    
    app = IntraConnectClient()
    app.run()