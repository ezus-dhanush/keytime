import tkinter as tk
from tkinter import ttk
import threading
import time
from datetime import datetime
import random
import os

# Try to import optional dependencies but provide fallbacks if they're missing
try:
    from pynput import keyboard, mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("Warning: pynput module not found. Input tracking will be simulated.")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil module not found. Window tracking will be limited.")

class KeyTime:
    def __init__(self, root):
        self.root = root
        self.root.title("KeyTime")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Set Matrix color theme
        self.matrix_green = "#00FF41"
        self.matrix_dark_green = "#008F11"
        self.matrix_black = "#0D0208"
        
        # Configure root window with Matrix theme
        self.root.configure(bg=self.matrix_black)
        
        # Styling
        self.setup_styles()
        
        # Variables for time tracking
        self.total_typing_time = 0  # Total time in seconds
        self.total_active_time = 0  # Total active time
        self.total_inactive_time = 0  # Total inactive time
        self.total_clicks = 0
        self.is_typing = False
        self.last_keypress_time = None
        self.last_status_change_time = datetime.now()
        self.inactivity_threshold = 5  # Seconds of inactivity before stopping timer
        self.stop_threads = False
        self.start_time = datetime.now()
        self.keypress_history = [0] * 60  # For the keypress histogram (60 seconds)
        self.keystroke_count = 0  # Count keypresses for visualization
        
        # Window tracking
        self.window_activity = {}
        self.current_window = "NONE"
        
        # Performance optimization variables
        self.last_gui_update = time.time()
        self.gui_update_interval = 0.5  # Update GUI every 0.5 seconds
        self.last_window_check_time = time.time()
        self.window_check_interval = 1.0  # Check active window every second
        self.tree_update_interval = 10.0  # Update window stats tree every 10 seconds
        self.last_tree_update = time.time()
        self.visualization_update_interval = 1.0
        self.last_visualization_update = time.time()
        
        # Active tab tracking to reduce unnecessary updates
        self.active_tab = 0
        
        # Create GUI elements
        self.setup_gui()
        
        # Start the keyboard listener and timer update threads
        self.start_threads()
    
    def setup_styles(self):
        """Set up the Matrix-themed styles for all widgets"""
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Configure all the styles
        self.style.configure("TFrame", background=self.matrix_black)
        self.style.configure("TLabel", background=self.matrix_black, foreground=self.matrix_green, font=("Courier New", 12))
        self.style.configure("Timer.TLabel", background=self.matrix_black, foreground=self.matrix_green, font=("Courier New", 24, "bold"))
        self.style.configure("Header.TLabel", background=self.matrix_black, foreground=self.matrix_green, font=("Courier New", 16, "bold"))
        
        # Configure labelframes
        self.style.configure("TLabelframe", background=self.matrix_black, foreground=self.matrix_green)
        self.style.configure("TLabelframe.Label", background=self.matrix_black, foreground=self.matrix_green, font=("Courier New", 12, "bold"))
        
        # Configure notebook
        self.style.configure("TNotebook", background=self.matrix_black, foreground=self.matrix_green)
        self.style.map("TNotebook.Tab", background=[("selected", self.matrix_dark_green), ("!selected", self.matrix_black)],
                       foreground=[("selected", self.matrix_green), ("!selected", self.matrix_green)])
        self.style.configure("TNotebook.Tab", background=self.matrix_black, foreground=self.matrix_green, padding=[10, 5])
        
        # Configure Treeview
        self.style.configure("Treeview", 
                            background=self.matrix_black, 
                            foreground=self.matrix_green, 
                            fieldbackground=self.matrix_black,
                            font=("Courier New", 10))
        self.style.map('Treeview', background=[('selected', self.matrix_dark_green)])
        self.style.configure("Treeview.Heading", 
                            background=self.matrix_dark_green, 
                            foreground=self.matrix_green,
                            font=("Courier New", 11, "bold"))
    
    def setup_gui(self):
        """Set up the main GUI components"""
        # Main frame with notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Dashboard tab
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="DASHBOARD")
        
        # Stats tab
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="METRICS")
        
        # Visualization tab
        visualization_frame = ttk.Frame(self.notebook)
        self.notebook.add(visualization_frame, text="VISUALIZE")
        
        # Track tab changes
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Dashboard setup
        self.setup_dashboard(dashboard_frame)
        
        # Stats setup
        self.setup_stats_tab(stats_frame)
        
        # Visualization setup
        self.setup_visualization_tab(visualization_frame)
    
    def on_tab_changed(self, event):
        """Track which tab is currently active"""
        self.active_tab = self.notebook.index("current")
    
    def setup_dashboard(self, parent):
        """Set up the dashboard tab contents"""
        # Title with Matrix-inspired header
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(title_frame, text="< KeyTime >", style="Header.TLabel")
        title_label.pack(pady=(0, 5))
        
        subtitle_label = ttk.Label(title_frame, text=">> Digital Activity Matrix <<", style="TLabel")
        subtitle_label.pack(pady=(0, 10))
        
        # Upper metrics frame
        metrics_frame = ttk.Frame(parent)
        metrics_frame.pack(fill=tk.X, pady=5)
        
        # Timer display frame
        timer_frame = ttk.LabelFrame(metrics_frame, text="TYPING SYSTEM")
        timer_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.time_label = ttk.Label(timer_frame, text="00:00:00", style="Timer.TLabel")
        self.time_label.pack(pady=10, padx=10)
        
        # Mouse clicks frame
        clicks_frame = ttk.LabelFrame(metrics_frame, text="NEURAL CLICKS")
        clicks_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.clicks_label = ttk.Label(clicks_frame, text="0", style="Timer.TLabel")
        self.clicks_label.pack(pady=10, padx=10)
        
        # Efficiency frame
        efficiency_frame = ttk.LabelFrame(metrics_frame, text="SYS EFFICIENCY")
        efficiency_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.efficiency_label = ttk.Label(efficiency_frame, text="0%", style="Timer.TLabel")
        self.efficiency_label.pack(pady=10, padx=10)
        
        # Lower metrics frame
        new_metrics_frame = ttk.Frame(parent)
        new_metrics_frame.pack(fill=tk.X, pady=10)
        
        # Active time frame
        active_frame = ttk.LabelFrame(new_metrics_frame, text="MATRIX CONNECT TIME")
        active_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.active_time_label = ttk.Label(active_frame, text="00:00:00", style="Timer.TLabel")
        self.active_time_label.pack(pady=10, padx=10)
        
        # Inactive time frame
        inactive_frame = ttk.LabelFrame(new_metrics_frame, text="UNPLUGGED TIME")
        inactive_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.inactive_time_label = ttk.Label(inactive_frame, text="00:00:00", style="Timer.TLabel")
        self.inactive_time_label.pack(pady=10, padx=10)
        
        # Status indicator
        status_frame = ttk.Frame(parent)
        status_frame.pack(pady=15, fill=tk.X)
        
        self.status_indicator = ttk.Label(status_frame, text="■", font=("Courier New", 16))
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_text = ttk.Label(status_frame, text="SEARCHING FOR SIGNAL...", style="TLabel")
        self.status_text.pack(side=tk.LEFT)
        
        # Current window frame
        window_frame = ttk.LabelFrame(parent, text="CURRENT PROGRAM")
        window_frame.pack(pady=10, fill=tk.X)
        
        self.current_window_label = ttk.Label(window_frame, text="SCANNING...", style="TLabel")
        self.current_window_label.pack(pady=5, padx=5, anchor=tk.W)
        
        # Digital rain effect (Matrix code)
        self.matrix_code_label = ttk.Label(parent, text="", font=("Courier New", 10), foreground=self.matrix_green)
        self.matrix_code_label.pack(pady=5, fill=tk.X)
        
        self.update_status(False)
    
    def setup_stats_tab(self, parent):
        """Set up the statistics tab contents"""
        # Title
        title_label = ttk.Label(parent, text="SYSTEM ACTIVITY ANALYSIS", style="Header.TLabel")
        title_label.pack(pady=(0, 15))
        
        # Create treeview for window stats
        columns = ("window", "time")
        self.window_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        
        # Configure columns
        self.window_tree.heading("window", text="PROGRAM/PROCESS")
        self.window_tree.heading("time", text="TIME ALLOCATION")
        self.window_tree.column("window", width=300)
        self.window_tree.column("time", width=150, anchor=tk.CENTER)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.window_tree.yview)
        self.window_tree.configure(yscroll=scrollbar.set)
        
        # Pack elements
        self.window_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Summary stats frame
        summary_frame = ttk.Frame(parent)
        summary_frame.pack(fill=tk.X, pady=10)
        
        # Most productive app
        self.productive_app_label = ttk.Label(summary_frame, text="MOST ACTIVE PROGRAM: Calculating...", style="TLabel")
        self.productive_app_label.pack(anchor=tk.W, pady=2)
        
        # Session start time
        session_start = self.start_time.strftime("%H:%M:%S")
        self.session_label = ttk.Label(summary_frame, text=f"SESSION INITIATED: {session_start}", style="TLabel")
        self.session_label.pack(anchor=tk.W, pady=2)
    
    def setup_visualization_tab(self, parent):
        """Set up the visualization tab contents"""
        # Title
        title_label = ttk.Label(parent, text="ACTIVITY VISUALIZATION", style="Header.TLabel")
        title_label.pack(pady=(0, 15))
        
        # Activity histogram
        histogram_frame = ttk.LabelFrame(parent, text="KEY ACTIVITY STREAM")
        histogram_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas for drawing the visualization
        self.canvas = tk.Canvas(histogram_frame, bg=self.matrix_black, 
                               highlightbackground=self.matrix_dark_green, 
                               highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Legend
        legend_frame = ttk.Frame(parent)
        legend_frame.pack(fill=tk.X, pady=5)
        
        legend_label = ttk.Label(legend_frame, text="KEY INTENSITY: ", style="TLabel")
        legend_label.pack(side=tk.LEFT, padx=5)
        
        # Low activity indicator
        ttk.Label(legend_frame, text="LOW", foreground=self.matrix_dark_green, 
                 background=self.matrix_black).pack(side=tk.LEFT, padx=5)
        
        # Medium activity indicator
        ttk.Label(legend_frame, text="MED", foreground=self.matrix_green, 
                 background=self.matrix_black).pack(side=tk.LEFT, padx=5)
        
        # High activity indicator
        ttk.Label(legend_frame, text="HIGH", foreground="#FFFFFF", 
                 background=self.matrix_black).pack(side=tk.LEFT, padx=5)
        
        # Stats frame
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill=tk.X, pady=10)
        
        # KPM label (Keystrokes Per Minute)
        self.kpm_label = ttk.Label(stats_frame, text="KEYS/MIN: 0", style="TLabel")
        self.kpm_label.pack(side=tk.LEFT, padx=20)
        
        # CPM label (Clicks Per Minute)
        self.cpm_label = ttk.Label(stats_frame, text="CLICKS/MIN: 0", style="TLabel")
        self.cpm_label.pack(side=tk.LEFT, padx=20)
    
    def update_status(self, active):
        """Update the active/inactive status and related counters"""
        current_time = datetime.now()
        time_diff = (current_time - self.last_status_change_time).total_seconds()
        
        # Update active/inactive time counters
        if active and not self.is_typing:  # Changing from inactive to active
            self.total_inactive_time += time_diff
            self.last_status_change_time = current_time
        elif not active and self.is_typing:  # Changing from active to inactive
            self.total_active_time += time_diff
            self.last_status_change_time = current_time
        
        # Update UI status
        if active:
            self.status_indicator.config(foreground=self.matrix_green, text="■")
            self.status_text.config(text="CONNECTED TO MATRIX")
        else:
            self.status_indicator.config(foreground="#FF0000", text="■")
            self.status_text.config(text="SIGNAL LOST")
        
        self.is_typing = active
    
    def format_time(self, seconds):
        """Format seconds into hours:minutes:seconds"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    
    def get_active_window_name(self):
        """Get the name of the currently active window"""
        try:
            # Only check active window periodically to reduce CPU usage
            current_time = time.time()
            if current_time - self.last_window_check_time < self.window_check_interval:
                return self.current_window or "UNKNOWN"
            
            self.last_window_check_time = current_time
            
            # Get foreground window process
            active_process_name = "UNKNOWN"
            
            # Use psutil if available
            if PSUTIL_AVAILABLE:
                try:
                    if os.name == 'nt':  # Windows
                        try:
                            import win32gui
                            import win32process
                            
                            hwnd = win32gui.GetForegroundWindow()
                            _, active_pid = win32process.GetWindowThreadProcessId(hwnd)
                            window_title = win32gui.GetWindowText(hwnd)
                            
                            if active_pid:
                                process = psutil.Process(active_pid)
                                active_process_name = process.name()
                                
                                # Add window title if available
                                if window_title:
                                    active_process_name = f"{active_process_name} - {window_title}"
                        except ImportError:
                            # Fallback if win32gui not available
                            active_process_name = "TERMINAL"
                    else:  # Linux/Mac - simplified approach
                        try:
                            # Get the process with the highest CPU that's likely to be foreground
                            processes = []
                            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                                # Skip system processes
                                if proc.info['name'] not in ['System', 'systemd', 'launchd', 'kernel']:
                                    processes.append((proc.info['pid'], proc.info['name'], proc.info['cpu_percent']))
                            
                            # Sort by CPU usage
                            if processes:
                                processes.sort(key=lambda x: x[2], reverse=True)
                                _, active_process_name, _ = processes[0]
                        except Exception:
                            active_process_name = "TERMINAL"
                except Exception:
                    active_process_name = "TERMINAL"
            else:
                # Fallback if psutil is not available
                active_process_name = "TERMINAL"
            
            # Convert to uppercase for Matrix theme
            return active_process_name.upper()
        except:
            return "UNKNOWN"
    
    def simulate_key_press(self):
        """Simulate a keypress when pynput is not available"""
        if random.random() < 0.3:  # 30% chance of a keypress each second
            self.on_key_press(None)
    
    def on_key_press(self, key):
        """Callback function for key press events"""
        current_time = datetime.now()
        
        # Get current window name
        window_name = self.get_active_window_name()
        self.current_window = window_name
        
        # Increment keystroke counter
        self.keystroke_count += 1
        
        # Update activity histogram
        current_second = int(current_time.timestamp()) % 60
        self.keypress_history[current_second] += 1
        
        if not self.is_typing:
            # Start timing if not already timing
            self.is_typing = True
            self.last_keypress_time = current_time
            self.last_status_change_time = current_time
        else:
            # Calculate time since last keypress
            time_diff = (current_time - self.last_keypress_time).total_seconds()
            
            # Only add to total if the time difference is less than the inactivity threshold
            if time_diff < self.inactivity_threshold:
                self.total_typing_time += time_diff
                
                # Add to window activity counter
                if window_name in self.window_activity:
                    self.window_activity[window_name] += time_diff
                else:
                    # Only add new keys if we don't have too many already
                    if len(self.window_activity) < 100:
                        self.window_activity[window_name] = time_diff
            
            # Update last keypress time
            self.last_keypress_time = current_time
    
    def on_click(self, x, y, button, pressed):
        """Callback function for mouse click events"""
        if pressed:
            self.total_clicks += 1
            current_time = datetime.now()
            
            # Always update window name on clicks
            window_name = self.get_active_window_name()
            self.current_window = window_name
            
            if not self.is_typing:
                self.is_typing = True
                self.last_keypress_time = current_time
                self.last_status_change_time = current_time
            else:
                if self.last_keypress_time:
                    time_diff = (current_time - self.last_keypress_time).total_seconds()
                    if time_diff < self.inactivity_threshold:
                        self.total_typing_time += time_diff
                        
                        # Add to current window only
                        if window_name in self.window_activity:
                            self.window_activity[window_name] += time_diff
                        else:
                            if len(self.window_activity) < 100:
                                self.window_activity[window_name] = time_diff
                
                self.last_keypress_time = current_time
    
    def check_inactivity(self):
        """Check for inactivity and update timer accordingly"""
        while not self.stop_threads:
            if self.is_typing and self.last_keypress_time:
                current_time = datetime.now()
                inactivity_time = (current_time - self.last_keypress_time).total_seconds()
                
                if inactivity_time >= self.inactivity_threshold:
                    # Update active time before changing status
                    time_diff = (current_time - self.last_status_change_time).total_seconds()
                    self.total_active_time += time_diff
                    self.last_status_change_time = current_time
                    
                    # Set to inactive
                    self.is_typing = False
            
            # If pynput is not available, simulate keypresses
            if not PYNPUT_AVAILABLE:
                self.simulate_key_press()
                
            time.sleep(1.0)
    
    def calculate_efficiency(self):
        """Calculate efficiency percentage (active time vs total time)"""
        total_elapsed = (datetime.now() - self.start_time).total_seconds()
        if total_elapsed > 0:
            return (self.total_typing_time / total_elapsed) * 100
        return 0
    
    def update_visualization(self):
        """Update the activity visualization canvas"""
        if self.active_tab != 2:  # Visualization tab is index 2
            return
            
        current_time = time.time()
        if current_time - self.last_visualization_update < self.visualization_update_interval:
            return
            
        self.last_visualization_update = current_time
        
        # Clear the canvas
        self.canvas.delete("all")
        
        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not ready yet
            return
        
        # Draw time-based histogram of keypresses
        bar_width = canvas_width / 60
        max_value = max(self.keypress_history) if max(self.keypress_history) > 0 else 1
        
        for i, value in enumerate(self.keypress_history):
            # Calculate bar height proportional to value
            bar_height = (value / max_value) * (canvas_height - 20)
            
            # Skip drawing bars with no height to improve performance
            if bar_height < 1:
                continue
                
            # Calculate color intensity based on value
            intensity = min(value / max_value, 1.0)
            if intensity < 0.3:
                color = self.matrix_dark_green
            elif intensity < 0.7:
                color = self.matrix_green
            else:
                color = "#FFFFFF"  # Very active is white
            
            x1 = i * bar_width
            y1 = canvas_height - bar_height
            x2 = (i + 1) * bar_width - 1
            y2 = canvas_height
            
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
        
        # Add time markers
        for i in range(0, 60, 10):
            x = i * bar_width
            self.canvas.create_line(x, canvas_height, x, canvas_height - 5, fill=self.matrix_green)
            self.canvas.create_text(x, canvas_height - 10, text=str(i), fill=self.matrix_green, font=("Courier New", 8))
        
        # Calculate and update KPM (Keys Per Minute)
        elapsed_minutes = (datetime.now() - self.start_time).total_seconds() / 60
        kpm = 0
        if elapsed_minutes > 0:
            kpm = self.keystroke_count / elapsed_minutes
        self.kpm_label.config(text=f"KEYS/MIN: {kpm:.1f}")
        
        # Calculate and update CPM (Clicks Per Minute)
        cpm = 0
        if elapsed_minutes > 0:
            cpm = self.total_clicks / elapsed_minutes
        self.cpm_label.config(text=f"CLICKS/MIN: {cpm:.1f}")
    
    def update_window_tree(self):
        """Update the window statistics treeview"""
        # Skip updates if stats tab isn't visible
        if self.active_tab != 1:  # Stats tab is index 1
            return
            
        current_time = time.time()
        # Only update tree periodically to improve performance
        if current_time - self.last_tree_update < self.tree_update_interval:
            return
            
        self.last_tree_update = current_time
        
        # Skip if no activity yet
        if not self.window_activity:
            return
        
        # Clear existing items
        for item in self.window_tree.get_children():
            self.window_tree.delete(item)
        
        # Sort windows by time spent (descending)
        # Get only top 20 entries to avoid processing too many items
        sorted_windows = sorted(self.window_activity.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Add items to the tree
        for window_name, seconds in sorted_windows:
            time_str = self.format_time(seconds)
            self.window_tree.insert("", tk.END, values=(window_name, time_str))
        
        # Update most productive app
        if sorted_windows:
            most_active_app = sorted_windows[0][0]
            self.productive_app_label.config(text=f"MOST ACTIVE PROGRAM: {most_active_app}")
    
    def generate_matrix_code(self):
        """Generate a simple Matrix-like digital rain effect"""
        chars = "10"
        line_length = 40
        return "".join([random.choice(chars) for _ in range(line_length)])
    
    def update_gui(self):
        """Update the GUI timer display"""
        while not self.stop_threads:
            current_time = time.time()
            
            # Calculate ongoing active/inactive time
            now = datetime.now()
            ongoing_time = (now - self.last_status_change_time).total_seconds()
            
            # Update active/inactive counters based on current status
            active_time = self.total_active_time
            inactive_time = self.total_inactive_time
            
            if self.is_typing:
                active_time += ongoing_time
            else:
                inactive_time += ongoing_time
            
            # Only update GUI at specified interval
            if current_time - self.last_gui_update >= self.gui_update_interval:
                self.last_gui_update = current_time
                
                # Update Matrix code effect
                matrix_code = self.generate_matrix_code()
                self.matrix_code_label.config(text=matrix_code)
                
                # Only update visible elements based on active tab
                if self.active_tab == 0:  # Dashboard tab
                    # Update the timer display
                    self.time_label.config(text=self.format_time(self.total_typing_time))
                    
                    # Update the clicks display
                    self.clicks_label.config(text=str(self.total_clicks))
                    
                    # Update efficiency
                    efficiency_percentage = self.calculate_efficiency()
                    self.efficiency_label.config(text=f"{efficiency_percentage:.1f}%")
                    
                    # Update active and inactive time labels
                    self.active_time_label.config(text=self.format_time(active_time))
                    self.inactive_time_label.config(text=self.format_time(inactive_time))
                    
                    # Update the current window label
                    if self.current_window:
                        self.current_window_label.config(text=self.current_window)
                    
                    # Update the status indicator
                    self.update_status(self.is_typing)
                elif self.active_tab == 1:  # Stats tab
                    # Update window statistics
                    self.update_window_tree()
                elif self.active_tab == 2:  # Visualization tab
                    # Update visualization
                    self.update_visualization()
            
            # Sleep for a shorter time to improve responsiveness
            time.sleep(0.1)
    
    def start_threads(self):
        """Start all the background threads"""
        # Start keyboard and mouse listeners if pynput is available
        if PYNPUT_AVAILABLE:
            try:
                # Start keyboard listener
                self.kb_listener = keyboard.Listener(on_press=self.on_key_press)
                self.kb_listener.daemon = True
                self.kb_listener.start()
                
                # Start mouse listener
                self.mouse_listener = mouse.Listener(on_click=self.on_click)
                self.mouse_listener.daemon = True
                self.mouse_listener.start()
            except Exception as e:
                print(f"Error starting input listeners: {e}")
        
        # Start inactivity checker thread
        self.inactivity_thread = threading.Thread(target=self.check_inactivity)
        self.inactivity_thread.daemon = True
        self.inactivity_thread.start()
        
        # Start GUI update thread
        self.update_thread = threading.Thread(target=self.update_gui)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def on_closing(self):
        """Handle window closing event"""
        self.stop_threads = True
        
        # Stop listeners if they exist
        if PYNPUT_AVAILABLE:
            try:
                if hasattr(self, 'kb_listener') and self.kb_listener.is_alive():
                    self.kb_listener.stop()
                if hasattr(self, 'mouse_listener') and self.mouse_listener.is_alive():
                    self.mouse_listener.stop()
            except:
                pass
            
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = KeyTime(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        print(f"Error starting KeyTime: {e}")
        import traceback
        traceback.print_exc()