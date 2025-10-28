"""
Client GUI Module
Main user interface for the collaboration application
"""

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk
import threading
import time
from PIL import Image, ImageTk
import cv2
import sys
sys.path.append('..')
from common.utils import format_file_size

class CollaborationGUI:
    def __init__(self, root, client):
        self.root = root
        self.client = client
        self.root.title("LAN Collaboration System")
        self.root.geometry("1600x1000")
        
        # Modern color scheme
        self.colors = {
            'bg_dark': '#1a1a2e',
            'bg_medium': '#16213e',
            'bg_light': '#0f3460',
            'accent': '#e94560',
            'accent_light': '#ff6b6b',
            'success': '#06ffa5',
            'text_light': '#ffffff',
            'text_dark': '#a8a8a8',
            'card_bg': '#1f2937',
            'hover': '#374151'
        }
        
        self.root.configure(bg=self.colors['bg_dark'])
        
        # Video display canvases
        self.video_canvases = {}
        self.video_labels = {}
        self.video_frames = {}
        
        # Display lock for thread safety
        self.display_lock = threading.Lock()
        
        # Screen sharing canvas
        self.screen_canvas = None
        
        # Screen sharing state
        self._screen_cleared = False
        
        # Initialize UI
        self.create_ui()
        
        # Start UI update thread
        self.running = True
        threading.Thread(target=self.update_ui_thread, daemon=True).start()
    
    def create_ui(self):
        """Create the modern user interface"""
        
        # Header bar
        header = tk.Frame(self.root, bg=self.colors['bg_medium'], height=60)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        
        # Logo/Title
        title_label = tk.Label(
            header,
            text="🎥 LAN Collaboration",
            font=('Segoe UI', 18, 'bold'),
            bg=self.colors['bg_medium'],
            fg=self.colors['success']
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # User info
        user_label = tk.Label(
            header,
            text=f"👤 {self.client.username}",
            font=('Segoe UI', 12),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_light']
        )
        user_label.pack(side=tk.LEFT, padx=10)
        
        # Control buttons in header
        controls_frame = tk.Frame(header, bg=self.colors['bg_medium'])
        controls_frame.pack(side=tk.RIGHT, padx=20)
        
        self.video_btn = tk.Button(
            controls_frame,
            text="📹 Video ON",
            command=self.toggle_video,
            bg=self.colors['success'],
            fg=self.colors['bg_dark'],
            font=('Segoe UI', 11, 'bold'),
            bd=0,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground=self.colors['accent']
        )
        self.video_btn.pack(side=tk.LEFT, padx=5)
        
        self.audio_btn = tk.Button(
            controls_frame,
            text="🎤 Audio ON",
            command=self.toggle_audio,
            bg=self.colors['success'],
            fg=self.colors['bg_dark'],
            font=('Segoe UI', 11, 'bold'),
            bd=0,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground=self.colors['accent']
        )
        self.audio_btn.pack(side=tk.LEFT, padx=5)
        
        self.share_btn = tk.Button(
            controls_frame,
            text="🖥️ Share Screen",
            command=self.toggle_screen_share,
            bg=self.colors['bg_light'],
            fg=self.colors['text_light'],
            font=('Segoe UI', 11, 'bold'),
            bd=0,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground=self.colors['accent']
        )
        self.share_btn.pack(side=tk.LEFT, padx=5)
        
        disconnect_btn = tk.Button(
            controls_frame,
            text="🚪 Disconnect",
            command=self.disconnect,
            bg=self.colors['accent'],
            fg=self.colors['text_light'],
            font=('Segoe UI', 11, 'bold'),
            bd=0,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground=self.colors['accent_light']
        )
        disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Main container
        main_container = tk.Frame(self.root, bg=self.colors['bg_dark'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left side: Video conference (70% width)
        left_panel = tk.Frame(main_container, bg=self.colors['bg_dark'])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Video conference section
        video_header = tk.Frame(left_panel, bg=self.colors['card_bg'], height=40)
        video_header.pack(fill=tk.X, pady=(0, 5))
        video_header.pack_propagate(False)
        
        tk.Label(
            video_header,
            text="📹 Video Conference",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light']
        ).pack(side=tk.LEFT, padx=15, pady=8)
        
        # Video grid with scrollbar
        video_container = tk.Frame(left_panel, bg=self.colors['bg_dark'])
        video_container.pack(fill=tk.BOTH, expand=True)
        
        video_canvas_widget = tk.Canvas(
            video_container,
            bg=self.colors['bg_dark'],
            highlightthickness=0
        )
        video_scrollbar = tk.Scrollbar(
            video_container,
            orient="vertical",
            command=video_canvas_widget.yview
        )
        
        self.video_grid = tk.Frame(video_canvas_widget, bg=self.colors['bg_dark'])
        
        video_canvas_widget.create_window((0, 0), window=self.video_grid, anchor="nw")
        video_canvas_widget.configure(yscrollcommand=video_scrollbar.set)
        
        video_canvas_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        video_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_grid.bind(
            "<Configure>",
            lambda e: video_canvas_widget.configure(scrollregion=video_canvas_widget.bbox("all"))
        )
        
        # Screen sharing section (below videos)
        screen_header = tk.Frame(left_panel, bg=self.colors['card_bg'], height=40)
        screen_header.pack(fill=tk.X, pady=(10, 5))
        screen_header.pack_propagate(False)
        
        tk.Label(
            screen_header,
            text="🖥️ Screen Sharing",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light']
        ).pack(side=tk.LEFT, padx=15, pady=8)
        
        screen_frame = tk.Frame(left_panel, bg=self.colors['card_bg'])
        screen_frame.pack(fill=tk.BOTH, expand=True)
        
        self.screen_canvas = tk.Canvas(
            screen_frame,
            bg=self.colors['bg_dark'],
            highlightthickness=0,
            height=300
        )
        self.screen_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right side: Chat and Files (30% width)
        right_panel = tk.Frame(main_container, bg=self.colors['bg_dark'], width=450)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # Chat section
        chat_header = tk.Frame(right_panel, bg=self.colors['card_bg'], height=40)
        chat_header.pack(fill=tk.X, pady=(0, 5))
        chat_header.pack_propagate(False)
        
        tk.Label(
            chat_header,
            text="💬 Group Chat",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light']
        ).pack(side=tk.LEFT, padx=15, pady=8)
        
        chat_container = tk.Frame(right_panel, bg=self.colors['card_bg'])
        chat_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Chat display with custom styling
        self.chat_display = scrolledtext.ScrolledText(
            chat_container,
            wrap=tk.WORD,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_light'],
            font=('Segoe UI', 10),
            bd=0,
            padx=10,
            pady=10,
            insertbackground=self.colors['success']
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        self.chat_display.config(state=tk.DISABLED)
        
        # Chat input
        chat_input_frame = tk.Frame(chat_container, bg=self.colors['card_bg'])
        chat_input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.chat_input = tk.Entry(
            chat_input_frame,
            font=('Segoe UI', 11),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_light'],
            insertbackground=self.colors['success'],
            bd=0,
            relief=tk.FLAT
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=8, padx=(0, 5))
        self.chat_input.bind('<Return>', lambda e: self.send_chat_message())
        
        send_btn = tk.Button(
            chat_input_frame,
            text="➤",
            command=self.send_chat_message,
            bg=self.colors['success'],
            fg=self.colors['bg_dark'],
            font=('Segoe UI', 14, 'bold'),
            bd=0,
            width=3,
            cursor='hand2',
            activebackground=self.colors['accent']
        )
        send_btn.pack(side=tk.RIGHT)
        
        # Files section
        files_header = tk.Frame(right_panel, bg=self.colors['card_bg'], height=40)
        files_header.pack(fill=tk.X, pady=(0, 5))
        files_header.pack_propagate(False)
        
        tk.Label(
            files_header,
            text="📁 File Sharing",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light']
        ).pack(side=tk.LEFT, padx=15, pady=8)
        
        files_container = tk.Frame(right_panel, bg=self.colors['card_bg'])
        files_container.pack(fill=tk.BOTH, expand=True)
        
        # File list
        self.file_listbox = tk.Listbox(
            files_container,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_light'],
            font=('Segoe UI', 10),
            bd=0,
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['text_light'],
            highlightthickness=0
        )
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        
        # File buttons
        file_btn_frame = tk.Frame(files_container, bg=self.colors['card_bg'])
        file_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        upload_btn = tk.Button(
            file_btn_frame,
            text="⬆️ Upload",
            command=self.upload_file,
            bg=self.colors['bg_light'],
            fg=self.colors['text_light'],
            font=('Segoe UI', 10, 'bold'),
            bd=0,
            padx=15,
            pady=6,
            cursor='hand2',
            activebackground=self.colors['hover']
        )
        upload_btn.pack(side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X)
        
        download_btn = tk.Button(
            file_btn_frame,
            text="⬇️ Download",
            command=self.download_file,
            bg=self.colors['bg_light'],
            fg=self.colors['text_light'],
            font=('Segoe UI', 10, 'bold'),
            bd=0,
            padx=15,
            pady=6,
            cursor='hand2',
            activebackground=self.colors['hover']
        )
        download_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X)
        
        # Status bar
        self.status_label = tk.Label(
            self.root,
            text="🟢 Connected",
            bg=self.colors['bg_medium'],
            fg=self.colors['success'],
            font=('Segoe UI', 10, 'bold'),
            anchor=tk.W,
            padx=20,
            pady=8
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def update_ui_thread(self):
        """Thread to continuously update UI elements"""
        last_update = time.time()
        target_fps = 15
        
        while self.running:
            try:
                current_time = time.time()
                elapsed = current_time - last_update
                
                if elapsed >= (1.0 / target_fps):
                    self.root.after(0, self.update_video_displays)
                    self.root.after(0, self.update_screen_display)
                    last_update = current_time
                
                time.sleep(0.033)
                
            except Exception as e:
                if self.running:
                    print(f"[GUI] Update error: {e}")
                time.sleep(0.1)
    
    def update_video_displays(self):
        """Update all video displays"""
        try:
            all_visible_users = set()
            
            # Get local frame if video enabled
            if self.client.video_capture and self.client.video_enabled:
                local_frame = self.client.video_capture.get_local_frame()
                if local_frame is not None:
                    self.display_video_frame("You", local_frame)
                    all_visible_users.add("You")
            
            # Get remote frames
            if self.client.video_capture:
                remote_frames = self.client.video_capture.get_remote_frames()
                
                for username, frame in remote_frames.items():
                    if frame is not None:
                        self.display_video_frame(username, frame)
                        all_visible_users.add(username)
                
                # Remove disconnected users
                current_users = set(remote_frames.keys())
                if self.client.video_enabled:
                    current_users.add("You")
                
                for username in list(self.video_canvases.keys()):
                    if username not in current_users:
                        self.remove_video_display(username)
        
        except Exception as e:
            if self.running:
                print(f"[GUI] Video update error: {e}")
    
    def display_video_frame(self, username, frame):
        """Display video frame for a user"""
        try:
            with self.display_lock:
                if username not in self.video_canvases:
                    self.create_video_canvas(username)
                
                # Resize frame
                frame_resized = cv2.resize(frame, (320, 240))
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                
                img = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(image=img)
                
                canvas = self.video_canvases[username]
                
                if hasattr(canvas, 'current_image_id') and canvas.current_image_id is not None:
                    canvas.itemconfig(canvas.current_image_id, image=photo)
                else:
                    canvas.current_image_id = canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                
                canvas.image = photo
                
        except Exception as e:
            if self.running:
                print(f"[GUI] Display frame error for {username}: {e}")
    
    def create_video_canvas(self, username):
        """Create video canvas for a user with modern styling"""
        num_users = len(self.video_canvases)
        cols = 3
        row = num_users // cols
        col = num_users % cols
        
        # User card
        user_card = tk.Frame(
            self.video_grid,
            bg=self.colors['card_bg'],
            padx=8,
            pady=8
        )
        user_card.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)
        
        self.video_grid.grid_rowconfigure(row, weight=1)
        self.video_grid.grid_columnconfigure(col, weight=1)
        
        # Username label with modern styling
        label = tk.Label(
            user_card,
            text=f"👤 {username}",
            bg=self.colors['bg_light'],
            fg=self.colors['text_light'],
            font=('Segoe UI', 11, 'bold'),
            pady=6
        )
        label.pack(fill=tk.X)
        
        # Video canvas
        canvas = tk.Canvas(
            user_card,
            width=320,
            height=240,
            bg=self.colors['bg_dark'],
            highlightthickness=0
        )
        canvas.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        canvas.current_image_id = None
        canvas.image = None
        
        self.video_canvases[username] = canvas
        self.video_labels[username] = label
        self.video_frames[username] = user_card
    
    def remove_video_display(self, username):
        """Remove video display for disconnected user"""
        if username in self.video_frames:
            self.video_frames[username].destroy()
            del self.video_canvases[username]
            del self.video_labels[username]
            del self.video_frames[username]
            self.reorganize_video_grid()
    
    def reorganize_video_grid(self):
        """Reorganize video grid after user removal"""
        users = list(self.video_canvases.keys())
        cols = 3
        
        for i, username in enumerate(users):
            row = i // cols
            col = i % cols
            self.video_frames[username].grid(row=row, column=col)
            self.video_grid.grid_rowconfigure(row, weight=1)
            self.video_grid.grid_columnconfigure(col, weight=1)
    
    def update_screen_display(self):
        """Update screen sharing display"""
        try:
            if self.client.shared_screen is not None:
                frame = self.client.shared_screen
                
                canvas_width = self.screen_canvas.winfo_width()
                canvas_height = self.screen_canvas.winfo_height()
                
                if canvas_width > 1 and canvas_height > 1:
                    frame_resized = cv2.resize(frame, (canvas_width, canvas_height))
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    
                    img = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(image=img)
                    
                    if not hasattr(self.screen_canvas, 'screen_image_id') or self.screen_canvas.screen_image_id is None:
                        self.screen_canvas.delete("all")
                        self.screen_canvas.screen_image_id = self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                    else:
                        self.screen_canvas.itemconfig(self.screen_canvas.screen_image_id, image=photo)
                    
                    self.screen_canvas.image = photo
                    self._screen_cleared = False
            else:
                if not self._screen_cleared:
                    self.screen_canvas.delete("all")
                    if self.screen_canvas.winfo_width() > 1:
                        self.screen_canvas.create_text(
                            self.screen_canvas.winfo_width() // 2,
                            self.screen_canvas.winfo_height() // 2,
                            text="No screen sharing active\nClick 'Share Screen' to start",
                            fill=self.colors['text_dark'],
                            font=('Segoe UI', 12),
                            justify=tk.CENTER
                        )
                    self._screen_cleared = True
                    if hasattr(self.screen_canvas, 'screen_image_id'):
                        self.screen_canvas.screen_image_id = None
        
        except Exception as e:
            if "main loop" not in str(e) and self.running:
                print(f"[GUI] Screen display error: {e}")
    
    def send_chat_message(self):
        """Send chat message"""
        message = self.chat_input.get().strip()
        if message:
            self.client.send_chat_message(message)
            self.chat_input.delete(0, tk.END)
    
    def add_chat_message(self, username, message, timestamp):
        """Add message to chat display with styling"""
        self.chat_display.config(state=tk.NORMAL)
        
        # Different styling for own messages
        if username == self.client.username:
            prefix = "You"
            color_tag = "own_message"
        else:
            prefix = username
            color_tag = "other_message"
        
        # Configure tags if not already done
        self.chat_display.tag_config("own_message", foreground=self.colors['success'])
        self.chat_display.tag_config("other_message", foreground=self.colors['accent_light'])
        self.chat_display.tag_config("timestamp", foreground=self.colors['text_dark'])
        
        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.chat_display.insert(tk.END, f"{prefix}: ", color_tag)
        self.chat_display.insert(tk.END, f"{message}\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def upload_file(self):
        """Upload file dialog"""
        filepath = filedialog.askopenfilename(title="Select file to upload")
        if filepath:
            threading.Thread(target=self._upload_file_thread, args=(filepath,), daemon=True).start()
    
    def _upload_file_thread(self, filepath):
        """Upload file in separate thread to prevent GUI freeze"""
        try:
            success = self.client.upload_file(filepath)
            if success:
                self.root.after(0, lambda: messagebox.showinfo("Success", "File uploaded successfully!"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", "File upload failed"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Upload error: {str(e)}"))
    
    def download_file(self):
        """Download selected file"""
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to download")
            return
        
        index = selection[0]
        file_info = list(self.client.file_client.available_files.items())[index]
        file_id = file_info[0]
        
        save_dir = filedialog.askdirectory(title="Select download location")
        if save_dir:
            threading.Thread(target=self._download_file_thread, args=(file_id, save_dir), daemon=True).start()
    
    def _download_file_thread(self, file_id, save_dir):
        """Download file in separate thread"""
        try:
            success, message = self.client.download_file(file_id, save_dir)
            if success:
                self.root.after(0, lambda: messagebox.showinfo("Success", message))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Download error: {str(e)}"))
    
    def add_file_to_list(self, file_id, filename, size, uploader):
        """Add file to available files list"""
        self.client.file_client.add_available_file(file_id, filename, size, uploader)
        display_text = f"📄 {filename} ({format_file_size(size)}) - {uploader}"
        self.file_listbox.insert(tk.END, display_text)
    
    def toggle_video(self):
        """Toggle video on/off"""
        if self.client.video_enabled:
            self.client.disable_video()
            self.video_btn.config(
                text="📹 Video OFF",
                bg=self.colors['accent']
            )
            self.update_status("🔴 Video disabled", self.colors['accent'])
        else:
            self.client.enable_video()
            self.video_btn.config(
                text="📹 Video ON",
                bg=self.colors['success']
            )
            self.update_status("🟢 Video enabled", self.colors['success'])
    
    def toggle_audio(self):
        """Toggle audio on/off"""
        if self.client.audio_enabled:
            self.client.disable_audio()
            self.audio_btn.config(
                text="🎤 Audio OFF",
                bg=self.colors['accent']
            )
            self.update_status("🔴 Audio disabled", self.colors['accent'])
        else:
            self.client.enable_audio()
            self.audio_btn.config(
                text="🎤 Audio ON",
                bg=self.colors['success']
            )
            self.update_status("🟢 Audio enabled", self.colors['success'])
    
    def toggle_screen_share(self):
        """Toggle screen sharing"""
        if self.client.screen_sharing:
            threading.Thread(target=self._stop_screen_share_thread, daemon=True).start()
        else:
            threading.Thread(target=self._start_screen_share_thread, daemon=True).start()
    
    def _start_screen_share_thread(self):
        """Start screen sharing in separate thread"""
        try:
            success = self.client.start_screen_share()
            if success:
                self.root.after(0, lambda: self.share_btn.config(
                    text="🛑 Stop Sharing",
                    bg=self.colors['accent']
                ))
                self.root.after(0, lambda: self.update_status("🟢 Screen sharing active", self.colors['success']))
            else:
                self.root.after(0, lambda: messagebox.showwarning("Screen Share", "Another user is already presenting"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Screen share error: {str(e)}"))
    
    def _stop_screen_share_thread(self):
        """Stop screen sharing in separate thread"""
        try:
            self.client.stop_screen_share()
            self.root.after(0, lambda: self.share_btn.config(
                text="🖥️ Share Screen",
                bg=self.colors['bg_light']
            ))
            self.root.after(0, lambda: self.update_status("🟢 Connected", self.colors['success']))
            self._screen_cleared = False
        except Exception as e:
            print(f"[GUI] Stop screen share error: {e}")
    
    def disconnect(self):
        """Disconnect from server"""
        if messagebox.askyesno("Disconnect", "Are you sure you want to disconnect?"):
            self.running = False
            self.client.disconnect()
            self.root.quit()
    
    def update_status(self, message, color=None):
        """Update status bar"""
        if color is None:
            color = self.colors['success']
        self.status_label.config(text=message, fg=color)