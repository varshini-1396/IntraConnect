# client.py
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
import pyaudio
import audioop
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
        self.audio = None
        self.audio_in = None
        self.audio_out = None
        self.screen_capturer = None
        
        # Speaking detection
        self.is_speaking = False
        self.speaking_threshold = 500
        
        # Video displays
        self.video_displays = []
        self.received_videos = {}
        
        # File tracking
        self.file_items = {}
        
        # Downloads folder
        self.downloads_folder = "downloads"
        os.makedirs(self.downloads_folder, exist_ok=True)
        
        # Blank images
        try:
            blank_img = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
            self._blank_ctki = ctk.CTkImage(light_image=blank_img, size=(1, 1))
        except:
            self._blank_ctki = None
        
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
            text="🔌 Connect",
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
        
        self.connect_btn.configure(text="⏳ Connecting...", state="disabled")
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
                msg = self.encode_message('CONNECT', {
                    'username': self.username,
                    'udp_port': udp_port
                })
                self.tcp_socket.sendall(msg)
                
                self.connected = True
                
                # Start receivers
                threading.Thread(target=self.tcp_receiver, daemon=True).start()
                threading.Thread(target=self.udp_receiver, daemon=True).start()
                
                self.root.after(0, self.setup_main_interface)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Connection failed: {e}"))
                self.root.after(0, lambda: self.connect_btn.configure(text="🔌 Connect", state="normal"))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def setup_main_interface(self):
        """Setup main interface"""
        self.login_frame.destroy()
        
        # Top bar
        top_bar = ctk.CTkFrame(self.root, height=70, corner_radius=0, fg_color="#1a1a1a")
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        
        ctk.CTkLabel(
            top_bar,
            text="IntraConnect",
            font=("Arial", 24, "bold"),
            text_color="#00ff88"
        ).pack(side="left", padx=25)
        
        ctk.CTkLabel(
            top_bar,
            text=f"👤 {self.username}",
            font=("Arial", 13),
            text_color="white"
        ).pack(side="left", padx=20)
        
        # Control buttons
        controls = ctk.CTkFrame(top_bar, fg_color="transparent")
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
        
        # Main content
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left side - Video and Screen
        left = ctk.CTkFrame(main, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Video grid
        ctk.CTkLabel(
            left,
            text="📹 Video Conference",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        ).pack(anchor="w", pady=(0, 5))
        
        video_grid = ctk.CTkFrame(left, corner_radius=12, fg_color="#1a1a1a")
        video_grid.pack(fill="both", expand=True, pady=(0, 10))
        
        # Create 6 video tiles (2 rows x 3 cols)
        for i in range(6):
            row, col = i // 3, i % 3
            
            tile = ctk.CTkFrame(video_grid, corner_radius=8, border_width=0, fg_color="#2a2a2a")
            tile.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            
            label = ctk.CTkLabel(
                tile,
                text="📷\nCamera Off" if i == 0 else f"User {i}",
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
        
        for i in range(3):
            video_grid.grid_columnconfigure(i, weight=1)
        for i in range(2):
            video_grid.grid_rowconfigure(i, weight=1)
        
        # Screen share area
        ctk.CTkLabel(
            left,
            text="🖥️ Screen Sharing",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        ).pack(anchor="w", pady=(0, 5))
        
        screen_frame = ctk.CTkFrame(left, corner_radius=12, height=300, fg_color="#1a1a1a")
        screen_frame.pack(fill="both")
        screen_frame.pack_propagate(False)
        
        self.screen_display = ctk.CTkLabel(
            screen_frame,
            text="🖥️\n\nNo screen being shared",
            font=("Arial", 14),
            text_color="gray"
        )
        self.screen_display.pack(expand=True)
        
        # Right side - Chat and Files
        right = ctk.CTkFrame(main, width=400, fg_color="transparent")
        right.pack(side="right", fill="both", padx=(5, 0))
        right.pack_propagate(False)
        
        # Users
        ctk.CTkLabel(
            right,
            text="👥 Connected Users",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        ).pack(anchor="w", pady=(0, 5))
        
        self.users_frame = ctk.CTkScrollableFrame(right, height=100, corner_radius=8, fg_color="#1a1a1a")
        self.users_frame.pack(fill="x", pady=(0, 10))
        
        # Chat
        ctk.CTkLabel(
            right,
            text="💬 Group Chat",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        ).pack(anchor="w", pady=(0, 5))
        
        self.chat_box = ctk.CTkTextbox(
            right,
            corner_radius=8,
            fg_color="#1a1a1a",
            font=("Arial", 11),
            wrap="word"
        )
        self.chat_box.pack(fill="both", expand=True, pady=(0, 5))
        
        # Chat input
        chat_input = ctk.CTkFrame(right, fg_color="transparent")
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
        
        # Files
        ctk.CTkLabel(
            right,
            text="📁 File Sharing",
            font=("Arial", 14, "bold"),
            text_color="#00ff88"
        ).pack(anchor="w", pady=(0, 5))
        
        ctk.CTkButton(
            right,
            text="📤 Upload File",
            height=38,
            font=("Arial", 11, "bold"),
            command=self.upload_file
        ).pack(fill="x", pady=(0, 5))
        
        self.files_list = ctk.CTkScrollableFrame(right, corner_radius=8, fg_color="#1a1a1a")
        self.files_list.pack(fill="both", expand=True)
        
        self.add_chat_msg("System", "Connected to IntraConnect server!", "#00ff88")
    
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
    
    # Video
    def start_video(self):
        """Start video"""
        try:
            self.video_cap = cv2.VideoCapture(0)
            if not self.video_cap.isOpened():
                messagebox.showerror("Error", "Cannot open camera")
                return False
            
            self.video_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            self.video_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            self.video_cap.set(cv2.CAP_PROP_FPS, 15)
            
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
                # Compress
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                compressed = buffer.tobytes()
                
                # Send via UDP
                packet = f"VIDEO_FRAME:{self.username}:".encode() + compressed
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
            if self._blank_ctki:
                self.video_displays[0]['label'].configure(text="📷\nCamera Off", image=self._blank_ctki)
        except:
            pass
    
    # Audio
    def start_audio(self):
        """Start audio"""
        try:
            self.audio = pyaudio.PyAudio()
            self.audio_in = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                frames_per_buffer=1024
            )
            self.audio_out = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                output=True,
                frames_per_buffer=1024
            )
            
            self.audio_on = True
            threading.Thread(target=self.audio_loop, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Audio start failed: {e}")
            return False
    
    def audio_loop(self):
        """Audio streaming loop"""
        while self.audio_on:
            try:
                audio_data = self.audio_in.read(1024, exception_on_overflow=False)
                
                # Speaking detection
                rms = audioop.rms(audio_data, 2)
                current_speaking = rms > self.speaking_threshold
                
                if current_speaking != self.is_speaking:
                    self.is_speaking = current_speaking
                    msg = self.encode_message('SPEAKING_STATUS', {
                        'username': self.username,
                        'speaking': self.is_speaking
                    })
                    try:
                        self.tcp_socket.sendall(msg)
                    except:
                        pass
                
                # Send audio
                packet = f"AUDIO_FRAME:{self.username}:".encode() + audio_data
                try:
                    self.udp_socket.sendto(packet, (self.server_ip, 5557))
                except:
                    pass
                
                time.sleep(1024 / 44100)
            except:
                pass
    
    def stop_audio(self):
        """Stop audio"""
        self.audio_on = False
        
        if self.is_speaking:
            msg = self.encode_message('SPEAKING_STATUS', {
                'username': self.username,
                'speaking': False
            })
            try:
                self.tcp_socket.sendall(msg)
            except:
                pass
            self.is_speaking = False
        
        if self.audio_in:
            try:
                self.audio_in.stop_stream()
                self.audio_in.close()
            except:
                pass
        if self.audio_out:
            try:
                self.audio_out.stop_stream()
                self.audio_out.close()
            except:
                pass
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
    
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
    
    def add_chat_msg(self, user, msg, own=False):
        """Add chat message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        self.chat_box.configure(state="normal")
        
        if own:
            self.chat_box.insert("end", f"[{timestamp}] You:\n", "time")
            self.chat_box.insert("end", f"{msg}\n\n", "own")
        else:
            self.chat_box.insert("end", f"[{timestamp}] {user}:\n", "time")
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
                msg = self.encode_message('FILE_INFO', {
                    'filename': filename,
                    'size': filesize
                })
                self.tcp_socket.sendall(msg)
                
                # Send file data
                with open(filepath, 'rb') as f:
                    file_data = f.read()
                
                msg = self.encode_message('FILE_CHUNK', {
                    'filename': filename,
                    'chunk': file_data.decode('latin-1')
                })
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
    
    # Update displays
    def update_video(self, slot, frame, name=""):
        """Update video display"""
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((320, 240))
            
            ctki = ctk.CTkImage(light_image=img, size=(320, 240))
            self.video_displays[slot]['label'].configure(image=ctki, text="")
            self.video_displays[slot]['label'].image = ctki
            self.video_displays[slot]['video_active'] = True
            
            if name:
                self.video_displays[slot]['name'].configure(text=name)
        except:
            pass
    
    def update_users(self, users):
        """Update user list"""
        for widget in self.users_frame.winfo_children():
            widget.destroy()
        
        for user in users:
            frame = ctk.CTkFrame(self.users_frame, fg_color="#2a2a2a", height=35, corner_radius=6)
            frame.pack(fill="x", pady=2)
            frame.pack_propagate(False)
            
            icon = "🟢" if user == self.username else "👤"
            ctk.CTkLabel(
                frame,
                text=f"{icon} {user}",
                font=("Arial", 11),
                anchor="w"
            ).pack(side="left", padx=10)
    
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
                
                if msg_type == 'VIDEO_FRAME':
                    nparr = np.frombuffer(payload, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        slot = (hash(username) % 5) + 1
                        self.update_video(slot, frame, username)
                
                elif msg_type == 'AUDIO_FRAME':
                    if self.audio_out:
                        try:
                            self.audio_out.write(payload)
                        except:
                            pass
            except:
                pass
    
    def handle_message(self, message):
        """Handle TCP message"""
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'USER_LIST':
            self.root.after(0, lambda: self.update_users(data['users']))
        
        elif msg_type == 'CHAT':
            self.root.after(0, lambda: self.add_chat_msg(data['username'], data['message']))
        
        elif msg_type == 'FILE_INFO':
            self.root.after(0, lambda: self.add_file_item(data))
        
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
            self.root.after(0, lambda: self.screen_display.configure(
                text="🖥️\n\nNo screen being shared", image=""
            ))
        
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
            slot = (hash(username) % 5) + 1
            try:
                self.video_displays[slot]['video_active'] = False
                if self._blank_ctki:
                    self.video_displays[slot]['label'].configure(
                        text="📷\nCamera Off",
                        image=self._blank_ctki
                    )
            except:
                pass
        
        elif msg_type == 'SPEAKING_STATUS':
            username = data['username']
            speaking = data['speaking']
            
            if username == self.username:
                slot = 0
            else:
                slot = (hash(username) % 5) + 1
            
            try:
                if speaking:
                    self.video_displays[slot]['frame'].configure(
                        border_width=3,
                        border_color="#00ff88"
                    )
                else:
                    self.video_displays[slot]['frame'].configure(
                        border_width=0
                    )
            except:
                pass
    
    def display_screen(self, frame):
        """Display screen frame"""
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((760, 570))
            
            ctki = ctk.CTkImage(light_image=img, size=(760, 570))
            self.screen_display.configure(image=ctki, text="")
            self.screen_display.image = ctki
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
    
    def run(self):
        """Run the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window close"""
        if messagebox.askokcancel("Quit", "Exit IntraConnect?"):
            self.connected = False
            
            # Stop media
            self.video_on = False
            self.audio_on = False
            self.screen_on = False
            
            time.sleep(0.2)
            
            # Cleanup
            if self.video_cap:
                try:
                    self.video_cap.release()
                except:
                    pass
            
            if self.audio_in:
                try:
                    self.audio_in.stop_stream()
                    self.audio_in.close()
                except:
                    pass
            
            if self.audio_out:
                try:
                    self.audio_out.stop_stream()
                    self.audio_out.close()
                except:
                    pass
            
            if self.audio:
                try:
                    self.audio.terminate()
                except:
                    pass
            
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
    print("\n" + "="*70)
    print(" "*20 + "🌐 IntraConnect Client")
    print("="*70)
    print("\n[INFO] Starting application...")
    
    try:
        import cv2
        import pyaudio
        import mss
        import customtkinter
        from PIL import Image
        import numpy
        print("[✓] All dependencies found")
    except ImportError as e:
        print(f"\n[ERROR] Missing dependency: {e}")
        print("\nInstall with: pip install opencv-python pyaudio pillow numpy mss customtkinter")
        exit(1)
    
    print("[✓] Initializing GUI...")
    print("="*70 + "\n")
    
    app = IntraConnectClient()
    app.run()