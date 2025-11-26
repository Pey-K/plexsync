"""
Plex Collection Sync - Windows GUI Launcher
A simple GUI wrapper for easy one-click startup on Windows.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import os
import sys
import webbrowser
from pathlib import Path

class PlexSyncLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Plex Collection Sync Launcher")
        self.root.geometry("700x600")
        self.root.resizable(False, False)
        
        # Check if .env exists
        if not Path(".env").exists():
            messagebox.showerror(
                "Configuration Missing",
                ".env file not found!\n\n"
                "Please create a .env file with your Plex credentials.\n"
                "You can copy .env.example to .env and edit it."
            )
            sys.exit(1)
        
        self.setup_ui()
        self.sync_process = None
        self.backend_process = None
        
    def setup_ui(self):
        # Header
        header = tk.Label(
            self.root,
            text="Plex Collection Sync",
            font=("Arial", 18, "bold"),
            pady=10
        )
        header.pack()
        
        # Status frame
        status_frame = ttk.Frame(self.root, padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready to start",
            font=("Arial", 10),
            fg="green"
        )
        self.status_label.pack()
        
        # Progress bar
        self.progress = ttk.Progressbar(
            self.root,
            mode='indeterminate',
            length=680
        )
        self.progress.pack(pady=10, padx=10)
        
        # Log output
        log_frame = ttk.LabelFrame(self.root, text="Log Output", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=20,
            width=80,
            font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons frame
        button_frame = ttk.Frame(self.root, padding=10)
        button_frame.pack(fill=tk.X)
        
        self.start_button = tk.Button(
            button_frame,
            text="Start Sync & Server",
            command=self.start_all,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(
            button_frame,
            text="Stop Server",
            command=self.stop_backend,
            bg="#f44336",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.open_browser_button = tk.Button(
            button_frame,
            text="Open API",
            command=lambda: webbrowser.open("http://localhost:3000/health"),
            bg="#2196F3",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.open_browser_button.pack(side=tk.LEFT, padx=5)
        
        self.quit_button = tk.Button(
            button_frame,
            text="Quit",
            command=self.quit_app,
            bg="#757575",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.quit_button.pack(side=tk.RIGHT, padx=5)
        
    def log(self, message):
        """Add message to log output."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
        
    def update_status(self, message, color="black"):
        """Update status label."""
        self.status_label.config(text=message, fg=color)
        self.root.update()
        
    def check_dependencies(self):
        """Check if Python and Node.js are available."""
        try:
            result = subprocess.run(
                ["python", "--version"],
                check=True,
                capture_output=True,
                timeout=5
            )
            python_version = result.stdout.decode().strip()
            self.log(f"Found: {python_version}")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            messagebox.showerror(
                "Python Not Found",
                "Python is not installed or not in PATH!\n\n"
                "Please install Python 3.9+ from:\n"
                "https://www.python.org/downloads/\n\n"
                "Make sure to check 'Add Python to PATH' during installation."
            )
            return False
        
        try:
            result = subprocess.run(
                ["node", "--version"],
                check=True,
                capture_output=True,
                timeout=5
            )
            node_version = result.stdout.decode().strip()
            self.log(f"Found: {node_version}")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            messagebox.showerror(
                "Node.js Not Found",
                "Node.js is not installed or not in PATH!\n\n"
                "Please install Node.js 18+ from:\n"
                "https://nodejs.org/\n\n"
                "Restart your computer after installation."
            )
            return False
        
        return True
    
    def install_dependencies(self):
        """Install Python and Node.js dependencies."""
        self.log("Checking Python dependencies...")
        try:
            result = subprocess.run(
                ["python", "-c", "import plexapi"],
                capture_output=True
            )
            if result.returncode != 0:
                self.log("Installing Python dependencies...")
                proc = subprocess.Popen(
                    ["pip", "install", "-r", "requirements.txt"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                for line in proc.stdout:
                    self.log(line.strip())
                proc.wait()
        except Exception as e:
            self.log(f"Error installing Python dependencies: {e}")
            return False
        
        self.log("Checking Node.js dependencies...")
        if not Path("node_modules").exists():
            self.log("Installing Node.js dependencies...")
            try:
                proc = subprocess.Popen(
                    ["npm", "install"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                for line in proc.stdout:
                    self.log(line.strip())
                proc.wait()
            except Exception as e:
                self.log(f"Error installing Node.js dependencies: {e}")
                return False
        
        return True
    
    def create_directories(self):
        """Create necessary directories."""
        dirs = [
            "data",
            "assets/images",
            "assets/images/movie_image",
            "assets/images/tv_image",
            "assets/images/music_image"
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def run_sync(self):
        """Run the sync script."""
        self.log("=" * 50)
        self.log("Starting Plex sync...")
        self.log("=" * 50)
        
        try:
            proc = subprocess.Popen(
                ["python", "plex_sync.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in proc.stdout:
                self.log(line.strip())
            
            proc.wait()
            
            if proc.returncode == 0:
                self.log("=" * 50)
                self.log("Sync completed successfully!")
                self.log("=" * 50)
                return True
            else:
                self.log("=" * 50)
                self.log("Sync completed with warnings/errors")
                self.log("=" * 50)
                return True  # Continue anyway
        except Exception as e:
            self.log(f"Error running sync: {e}")
            return False
    
    def start_backend(self):
        """Start the backend server."""
        self.log("=" * 50)
        self.log("Starting backend server...")
        self.log("API will be available at: http://localhost:3000")
        self.log("=" * 50)
        
        try:
            self.backend_process = subprocess.Popen(
                ["node", "server.js"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Start thread to read output
            def read_output():
                if self.backend_process:
                    for line in self.backend_process.stdout:
                        self.log(line.strip())
            
            threading.Thread(target=read_output, daemon=True).start()
            
            self.update_status("Server running on http://localhost:3000", "green")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            return True
        except Exception as e:
            self.log(f"Error starting backend: {e}")
            return False
    
    def start_all(self):
        """Start sync and server in sequence."""
        self.start_button.config(state=tk.DISABLED)
        self.progress.start()
        
        def run():
            try:
                # Check dependencies
                if not self.check_dependencies():
                    messagebox.showerror(
                        "Dependencies Missing",
                        "Python or Node.js not found in PATH!\n\n"
                        "Please install:\n"
                        "- Python 3.9+ from https://www.python.org/\n"
                        "- Node.js 18+ from https://nodejs.org/"
                    )
                    return
                
                # Install dependencies
                self.update_status("Installing dependencies...", "blue")
                if not self.install_dependencies():
                    messagebox.showerror("Error", "Failed to install dependencies!")
                    return
                
                # Create directories
                self.update_status("Setting up directories...", "blue")
                self.create_directories()
                
                # Run sync
                self.update_status("Running sync...", "blue")
                self.run_sync()
                
                # Start backend
                self.update_status("Starting server...", "blue")
                self.start_backend()
                
                self.progress.stop()
                messagebox.showinfo(
                    "Success",
                    "Sync completed and server started!\n\n"
                    "API available at: http://localhost:3000"
                )
            except Exception as e:
                self.progress.stop()
                messagebox.showerror("Error", f"An error occurred: {e}")
                self.start_button.config(state=tk.NORMAL)
        
        threading.Thread(target=run, daemon=True).start()
    
    def stop_backend(self):
        """Stop the backend server."""
        if self.backend_process:
            self.backend_process.terminate()
            self.backend_process = None
            self.update_status("Server stopped", "red")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.log("Backend server stopped")
    
    def quit_app(self):
        """Quit the application."""
        if self.backend_process:
            self.stop_backend()
        self.root.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PlexSyncLauncher(root)
    root.mainloop()

