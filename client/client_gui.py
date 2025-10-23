"""
Client GUI Module
Main user interface for the collaboration application
"""

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import threading
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
        self.root.geometry("1400x900")
        self.root.configure(bg='#2C3E50')
        
        # Video display canvases
        self.video_canvases = {}
        self.video_labels = {}
        
        # Screen sharing canvas
        self.screen_canvas = None
        
        # Initialize UI
        self.create_ui()
        
        # Start UI update thread
        self.running = True
        threading.Thread(target=self.update_ui_thread, daemon=True).start()
    
    def create_ui(self):
        """Create the main user interface"""
        
        # Main container
        main_container = tk.Frame(self.root, bg='#2C3E50')
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top section: Video Conference
        video_frame = tk.LabelFrame(
            main_container,
            text="Video Conference",
            font=('Arial', 12, 'bold'),
            bg='#34495E',
            fg='white',
            padx=10,
            pady=10
        )
        video_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Video grid
        self.video_grid = tk.Frame(video_frame, bg='#34495E')
        self.video_grid.pack(fill=tk.BOTH, expand=True)
        
        # Bottom section split: Left (Chat + Files) and Right (Screen Share)
        bottom_frame = tk.Frame(main_container, bg='#2C3E50')
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        # Left side: Chat and Files
        left_frame = tk.Frame(bottom_frame, bg='#2C3E50')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Chat section
        chat_frame = tk.LabelFrame(
            left_frame,
            text="Group Chat",
            font=('Arial', 12, 'bold'),
            bg='#34495E',
            fg='white',
            padx=10,
            pady=10
        )
        chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Chat display
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            width=50,
            height=15,
            bg='#ECF0F1',
            fg='#2C3E50',
            font=('Arial', 10)
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.chat_display.config(state=tk.DISABLED)
        
        # Chat input
        chat_input_frame = tk.Frame(chat_frame, bg='#34495E')
        chat_input_frame.pack(fill=tk.X)
        
        self.chat_input = tk.Entry(
            chat_input_frame,
            font=('Arial', 11),
            bg='white',
            fg='#2C3E50'
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.chat_input.bind('<Return>', lambda e: self.send_chat_message())
        
        send_btn = tk.Button(
            chat_input_frame,
            text="Send",
            command=self.send_chat_message,
            bg='#3498DB',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20
        )
        send_btn.pack(side=tk.RIGHT)
        
        # Files section
        files_frame = tk.LabelFrame(
            left_frame,
            text="File Sharing",
            font=('Arial', 12, 'bold'),
            bg='#34495E',
            fg='white',
            padx=10,
            pady=10
        )
        files_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        # File list
        self.file_listbox = tk.Listbox(
            files_frame,
            bg='#ECF0F1',
            fg='#2C3E50',
            font=('Arial', 10),
            height=8
        )
        self.file_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # File buttons
        file_btn_frame = tk.Frame(files_frame, bg='#34495E')
        file_btn_frame.pack(fill=tk.X)
        
        upload_btn = tk.Button(
            file_btn_frame,
            text="Upload File",
            command=self.upload_file,
            bg='#2ECC71',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15
        )
        upload_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        download_btn = tk.Button(
            file_btn_frame,
            text="Download Selected",
            command=self.download_file,
            bg='#E67E22',fg='white',
            font=('Arial', 10, 'bold'),
            padx=15
        )
        download_btn.pack(side=tk.LEFT)
        
        # Right side: Screen Share
        screen_frame = tk.LabelFrame(
            bottom_frame,
            text="Screen Sharing",
            font=('Arial', 12, 'bold'),
            bg='#34495E',
            fg='white',
            padx=10,
            pady=10
        )
        screen_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Screen display
        self.screen_canvas = tk.Canvas(
            screen_frame,
            bg='#2C3E50',
            highlightthickness=0
        )
        self.screen_canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Screen share buttons
        screen_btn_frame = tk.Frame(screen_frame, bg='#34495E')
        screen_btn_frame.pack(fill=tk.X)
        
        self.share_btn = tk.Button(
            screen_btn_frame,
            text="Start Sharing",
            command=self.toggle_screen_share,
            bg='#9B59B6',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20
        )
        self.share_btn.pack(side=tk.LEFT)
        
        # Control buttons
        control_frame = tk.Frame(main_container, bg='#2C3E50')
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        
        self.video_btn = tk.Button(
            control_frame,
            text="📹 Video ON",
            command=self.toggle_video,
            bg='#27AE60',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        )
        self.video_btn.pack(side=tk.LEFT, padx=5)
        
        self.audio_btn = tk.Button(
            control_frame,
            text="🎤 Audio ON",
            command=self.toggle_audio,
            bg='#27AE60',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        )
        self.audio_btn.pack(side=tk.LEFT, padx=5)
        
        disconnect_btn = tk.Button(
            control_frame,
            text="Disconnect",
            command=self.disconnect,
            bg='#E74C3C',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        )
        disconnect_btn.pack(side=tk.RIGHT, padx=5)
        
        # Status bar
        self.status_label = tk.Label(
            self.root,
            text="Connected",
            bg='#27AE60',
            fg='white',
            font=('Arial', 10),
            anchor=tk.W,
            padx=10
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def update_ui_thread(self):
        """Thread to continuously update UI elements"""
        while self.running:
            try:
                # Update video displays
                self.update_video_displays()
                
                # Update screen share display
                self.update_screen_display()
                
                threading.Event().wait(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"[GUI] Update error: {e}")
    
    def update_video_displays(self):
        """Update all video displays"""
        try:
            # Get local frame
            if self.client.video_capture and self.client.video_enabled:
                local_frame = self.client.video_capture.get_local_frame()
                if local_frame is not None:
                    self.display_video_frame("You", local_frame)
            
            # Get remote frames
            if self.client.video_capture:
                remote_frames = self.client.video_capture.get_remote_frames()
                for username, frame in remote_frames.items():
                    self.display_video_frame(username, frame)
                
                # Remove disconnected users
                current_users = set(remote_frames.keys())
                if self.client.video_enabled:
                    current_users.add("You")
                
                for username in list(self.video_canvases.keys()):
                    if username not in current_users:
                        self.remove_video_display(username)
        
        except Exception as e:
            print(f"[GUI] Video update error: {e}")
    
    def display_video_frame(self, username, frame):
        """Display video frame for a user"""
        try:
            # Create canvas if doesn't exist
            if username not in self.video_canvases:
                self.create_video_canvas(username)
            
            # Resize frame to fit canvas
            frame_resized = cv2.resize(frame, (320, 240))
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            
            # Convert to PhotoImage
            img = Image.fromarray(frame_rgb)
            photo = ImageTk.PhotoImage(image=img)
            
            # Update canvas
            canvas = self.video_canvases[username]
            canvas.delete("all")
            canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            canvas.image = photo  # Keep reference
            
        except Exception as e:
            print(f"[GUI] Display frame error for {username}: {e}")
    
    def create_video_canvas(self, username):
        """Create video canvas for a user"""
        # Calculate grid position
        num_users = len(self.video_canvases)
        cols = min(3, num_users + 1)
        row = num_users // cols
        col = num_users % cols
        
        # Create frame for user
        user_frame = tk.Frame(self.video_grid, bg='#2C3E50', padx=5, pady=5)
        user_frame.grid(row=row, column=col, sticky='nsew')
        
        # Configure grid weights
        self.video_grid.grid_rowconfigure(row, weight=1)
        self.video_grid.grid_columnconfigure(col, weight=1)
        
        # Username label
        label = tk.Label(
            user_frame,
            text=username,
            bg='#34495E',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        label.pack(fill=tk.X)
        
        # Video canvas
        canvas = tk.Canvas(
            user_frame,
            width=320,
            height=240,
            bg='#2C3E50',
            highlightthickness=1,
            highlightbackground='#3498DB'
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        
        self.video_canvases[username] = canvas
        self.video_labels[username] = label
    
    def remove_video_display(self, username):
        """Remove video display for disconnected user"""
        if username in self.video_canvases:
            canvas = self.video_canvases[username]
            
            canvas.master.destroy()
            
            del self.video_canvases[username]
            del self.video_labels[username]
            
            # Reorganize grid
            self.reorganize_video_grid()
    
    def reorganize_video_grid(self):
        """Reorganize video grid after user removal"""
        users = list(self.video_canvases.keys())
        cols = min(3, len(users))
        
        for i, username in enumerate(users):
            row = i // cols
            col = i % cols
            canvas = self.video_canvases[username]
            canvas.master.grid(row=row, column=col)
            
            self.video_grid.grid_rowconfigure(row, weight=1)
            self.video_grid.grid_columnconfigure(col, weight=1)
    
    def update_screen_display(self):
        """Update screen sharing display"""
        try:
            if self.client.shared_screen is not None:
                frame = self.client.shared_screen
                
                # Get canvas size
                canvas_width = self.screen_canvas.winfo_width()
                canvas_height = self.screen_canvas.winfo_height()
                
                if canvas_width > 1 and canvas_height > 1:
                    # Resize frame to fit canvas
                    frame_resized = cv2.resize(frame, (canvas_width, canvas_height))
                    
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    
                    # Convert to PhotoImage
                    img = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(image=img)
                    
                    # Update canvas
                    self.screen_canvas.delete("all")
                    self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                    self.screen_canvas.image = photo
            else:
                # Clear canvas if no screen sharing
                if not hasattr(self, '_screen_cleared'):
                    self.screen_canvas.delete("all")
                    self.screen_canvas.create_text(
                        self.screen_canvas.winfo_width() // 2,
                        self.screen_canvas.winfo_height() // 2,
                        text="No screen sharing active",
                        fill='white',
                        font=('Arial', 14)
                    )
                    self._screen_cleared = True
        
        except Exception as e:
            print(f"[GUI] Screen display error: {e}")
    
    def send_chat_message(self):
        """Send chat message"""
        message = self.chat_input.get().strip()
        if message:
            self.client.send_chat_message(message)
            self.chat_input.delete(0, tk.END)
    
    def add_chat_message(self, username, message, timestamp):
        """Add message to chat display"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"[{timestamp}] {username}: {message}\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def upload_file(self):
        """Upload file dialog"""
        filepath = filedialog.askopenfilename(title="Select file to upload")
        if filepath:
            self.client.upload_file(filepath)
            messagebox.showinfo("File Upload", "File uploaded successfully!")
    
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
            success, message = self.client.download_file(file_id, save_dir)
            if success:
                messagebox.showinfo("Download Complete", message)
            else:
                messagebox.showerror("Download Failed", message)
    
    def add_file_to_list(self, file_id, filename, size, uploader):
        """Add file to available files list"""
        self.client.file_client.add_available_file(file_id, filename, size, uploader)
        
        # Update listbox
        display_text = f"{filename} ({format_file_size(size)}) - {uploader}"
        self.file_listbox.insert(tk.END, display_text)
    
    def toggle_video(self):
        """Toggle video on/off"""
        if self.client.video_enabled:
            self.client.disable_video()
            self.video_btn.config(text="📹 Video OFF", bg='#E74C3C')
        else:
            self.client.enable_video()
            self.video_btn.config(text="📹 Video ON", bg='#27AE60')
    
    def toggle_audio(self):
        """Toggle audio on/off"""
        if self.client.audio_enabled:
            self.client.disable_audio()
            self.audio_btn.config(text="🎤 Audio OFF", bg='#E74C3C')
        else:
            self.client.enable_audio()
            self.audio_btn.config(text="🎤 Audio ON", bg='#27AE60')
    
    def toggle_screen_share(self):
        """Toggle screen sharing"""
        if self.client.screen_sharing:
            self.client.stop_screen_share()
            self.share_btn.config(text="Start Sharing", bg='#9B59B6')
            self._screen_cleared = False
        else:
            success = self.client.start_screen_share()
            if success:
                self.share_btn.config(text="Stop Sharing", bg='#E74C3C')
            else:
                messagebox.showwarning("Screen Share", "Another user is already presenting")
    
    def disconnect(self):
        """Disconnect from server"""
        if messagebox.askyesno("Disconnect", "Are you sure you want to disconnect?"):
            self.client.disconnect()
            self.running = False
            self.root.quit()
    
    def update_status(self, message, color='#27AE60'):
        """Update status bar"""
        self.status_label.config(text=message, bg=color)