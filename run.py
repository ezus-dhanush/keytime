import tkinter as tk
from tkinter import ttk
import threading
import time
from pynput import keyboard, mouse
from datetime import datetime, timedelta
import psutil
import collections
import os

class EnhancedTypingTimeTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Typing Time Tracker")
        self.root.geometry("500x400")
        self.root.resizable(True, True)
        
        # Styling
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("Arial", 12))
        self.style.configure("Timer.TLabel", font=("Arial", 24, "bold"), foreground="#007bff")
        self.style.configure("Header.TLabel", font=("Arial", 14, "bold"))
        self.style.configure("Treeview", font=("Arial", 10))
        self.style.configure("Treeview.Heading", font=("Arial", 11, "bold"))
        
        # Variables for time tracking
        self.total_typing_time = 0  # Total time in seconds
        self.total_active_time = 0  # New: Total active time
        self.total_inactive_time = 0  # New: Total inactive time
        self.total_clicks = 0
        self.is_typing = False
        self.last_keypress_time = None
        self.last_status_change_time = datetime.now()  # Track when status changes for active/inactive time
        self.inactivity_threshold = 5  # Seconds of inactivity before stopping timer
        self.stop_threads = False
        self.start_time = datetime.now()
        
        # Window tracking - use a smaller dict instead of defaultdict
        self.window_activity = {}
        self.current_window = None
        
        # Performance optimization variables
        self.last_gui_update = time.time()
        self.gui_update_interval = 1.0  # Update GUI every 1.0 seconds
        self.last_window_check_time = time.time()
        self.window_check_interval = 1.0  # Check active window more frequently (was 3.0)
        self.tree_update_interval = 10.0  # Update window stats tree every 10 seconds
        self.last_tree_update = time.time()
        
        # Batch updates
        self.update_queue = collections.deque(maxlen=10)  # Limit queue size
        self.queue_lock = threading.Lock()
        
        # Active tab tracking to reduce unnecessary updates
        self.active_tab = 0  # Dashboard tab is active by default
        
        # Create GUI elements
        self.setup_gui()
        
        # Start the keyboard listener and timer update threads
        self.start_threads()
    
    def setup_gui(self):
        # Main frame with notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Dashboard tab
        dashboard_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(dashboard_frame, text="Dashboard")
        
        # Stats tab
        stats_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(stats_frame, text="Window Stats")
        
        # Track tab changes
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Dashboard setup
        self.setup_dashboard(dashboard_frame)
        
        # Stats setup
        self.setup_stats_tab(stats_frame)
    
    def on_tab_changed(self, event):
        """Track which tab is currently active"""
        self.active_tab = self.notebook.index("current")
    
    def setup_dashboard(self, parent):
        # Title
        title_label = ttk.Label(parent, text="Activity Tracking Dashboard", style="Header.TLabel")
        title_label.pack(pady=(0, 15))
        
        # Upper metrics frame for original metrics
        metrics_frame = ttk.Frame(parent)
        metrics_frame.pack(fill=tk.X, pady=5)
        
        # Timer display frame
        timer_frame = ttk.LabelFrame(metrics_frame, text="Typing Time")
        timer_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.time_label = ttk.Label(timer_frame, text="00:00:00", style="Timer.TLabel")
        self.time_label.pack(pady=10, padx=10)
        
        # Mouse clicks frame
        clicks_frame = ttk.LabelFrame(metrics_frame, text="Mouse Clicks")
        clicks_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.clicks_label = ttk.Label(clicks_frame, text="0", style="Timer.TLabel")
        self.clicks_label.pack(pady=10, padx=10)
        
        # Efficiency frame
        efficiency_frame = ttk.LabelFrame(metrics_frame, text="Efficiency")
        efficiency_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.efficiency_label = ttk.Label(efficiency_frame, text="0%", style="Timer.TLabel")
        self.efficiency_label.pack(pady=10, padx=10)
        
        # Lower metrics frame for new timers
        new_metrics_frame = ttk.Frame(parent)
        new_metrics_frame.pack(fill=tk.X, pady=10)
        
        # Active time frame
        active_frame = ttk.LabelFrame(new_metrics_frame, text="Total Active Time")
        active_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.active_time_label = ttk.Label(active_frame, text="00:00:00", style="Timer.TLabel")
        self.active_time_label.pack(pady=10, padx=10)
        
        # Inactive time frame
        inactive_frame = ttk.LabelFrame(new_metrics_frame, text="Total Inactive Time")
        inactive_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.inactive_time_label = ttk.Label(inactive_frame, text="00:00:00", style="Timer.TLabel")
        self.inactive_time_label.pack(pady=10, padx=10)
        
        # Status indicator
        status_frame = ttk.Frame(parent)
        status_frame.pack(pady=15, fill=tk.X)
        
        self.status_indicator = ttk.Label(status_frame, text="•", font=("Arial", 16))
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_text = ttk.Label(status_frame, text="Waiting for activity...", style="TLabel")
        self.status_text.pack(side=tk.LEFT)
        
        # Current window frame
        window_frame = ttk.LabelFrame(parent, text="Current Window/Process")
        window_frame.pack(pady=10, fill=tk.X)
        
        self.current_window_label = ttk.Label(window_frame, text="None", style="TLabel")
        self.current_window_label.pack(pady=5, padx=5, anchor=tk.W)
        
        self.update_status(False)
    
    def setup_stats_tab(self, parent):
        # Title
        title_label = ttk.Label(parent, text="Window/Process Activity Statistics", style="Header.TLabel")
        title_label.pack(pady=(0, 15))
        
        # Create treeview for window stats
        columns = ("window", "time")
        self.window_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        
        # Configure columns
        self.window_tree.heading("window", text="Window/Process")
        self.window_tree.heading("time", text="Time Spent")
        self.window_tree.column("window", width=300)
        self.window_tree.column("time", width=150, anchor=tk.CENTER)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.window_tree.yview)
        self.window_tree.configure(yscroll=scrollbar.set)
        
        # Pack elements
        self.window_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def update_status(self, active):
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
            self.status_indicator.config(foreground="#00cc00", text="•")
            self.status_text.config(text="Actively working")
        else:
            self.status_indicator.config(foreground="#cc0000", text="•")
            self.status_text.config(text="Inactive")
        
        self.is_typing = active
    
    def format_time(self, seconds):
        """Format seconds into hours:minutes:seconds"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    
    def get_active_window_name(self):
        """Get the name of the currently active window - improved method"""
        try:
            # Only check active window periodically to reduce CPU usage
            current_time = time.time()
            if current_time - self.last_window_check_time < self.window_check_interval:
                # Return cached window name if still within interval
                return self.current_window or "Unknown"
            
            self.last_window_check_time = current_time
            
            # Get foreground window process
            active_pid = None
            active_process_name = "Unknown"
            
            if os.name == 'nt':  # Windows
                try:
                    import win32gui
                    import win32process
                    
                    hwnd = win32gui.GetForegroundWindow()
                    _, active_pid = win32process.GetWindowThreadProcessId(hwnd)
                    window_title = win32gui.GetWindowText(hwnd)
                    
                    if active_pid:
                        try:
                            process = psutil.Process(active_pid)
                            active_process_name = process.name()
                            
                            # Add window title if available
                            if window_title:
                                active_process_name = f"{active_process_name} - {window_title}"
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except ImportError:
                    # Fallback if win32gui not available
                    pass
            else:  # Linux/Mac - simplified approach
                try:
                    # Get the process with the highest CPU that's likely to be foreground
                    processes = []
                    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                        try:
                            # Skip system processes
                            if proc.info['name'] not in ['System', 'systemd', 'launchd', 'kernel']:
                                processes.append((proc.info['pid'], proc.info['name'], proc.info['cpu_percent']))
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    # Sort by CPU usage
                    if processes:
                        processes.sort(key=lambda x: x[2], reverse=True)
                        active_pid, active_process_name, _ = processes[0]
                except Exception as e:
                    print(f"Error detecting active window: {e}")
            
            return active_process_name
        except Exception as e:
            print(f"Error getting window name: {e}")
            return "Unknown"
    
    def on_key_press(self, key):
        """Callback function for key press events"""
        current_time = datetime.now()
        
        # Get current window name
        window_name = self.get_active_window_name()
        self.current_window = window_name
        
        if not self.is_typing:
            # Start timing if not already timing
            self.is_typing = True
            self.last_keypress_time = current_time
            self.last_status_change_time = current_time
        else:
            # Calculate time since last keypress
            time_diff = (current_time - self.last_keypress_time).total_seconds()
            
            # Only add to total if we haven't already counted this session
            # and the time difference is less than the inactivity threshold
            if time_diff < self.inactivity_threshold:
                self.total_typing_time += time_diff
                
                # Add to window activity counter - with optimization
                if window_name in self.window_activity:
                    self.window_activity[window_name] += time_diff
                else:
                    # Only add new keys if we don't have too many already (prevent memory growth)
                    if len(self.window_activity) < 100:  # Limit number of tracked windows
                        self.window_activity[window_name] = time_diff
            
            # Update last keypress time
            self.last_keypress_time = current_time
            
            # Queue the update instead of updating directly
            with self.queue_lock:
                self.update_queue.append(('activity', window_name, time_diff))
    
    def process_update_queue(self):
        """Process the queued updates in a batch"""
        with self.queue_lock:
            queue_copy = list(self.update_queue)
            self.update_queue.clear()
        
        # Process all updates in the queue
        for update_type, *args in queue_copy:
            if update_type == 'activity':
                pass  # Already processed in on_key_press
    
    def on_click(self, x, y, button, pressed):
        """Callback function for mouse click events"""
        if pressed:
            self.total_clicks += 1
            # Use a lighter version - don't call the full key press handler
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
            
            time.sleep(1.0)  # Check every second for better responsiveness
    
    def calculate_efficiency(self):
        """Calculate efficiency percentage (active time vs total time)"""
        total_elapsed = (datetime.now() - self.start_time).total_seconds()
        if total_elapsed > 0:
            return (self.total_typing_time / total_elapsed) * 100
        return 0
    
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
        
        # Process any pending updates
        self.process_update_queue()
        
        # Clear existing items but only if there are window activities to show
        if not self.window_activity:
            return
        
        # Use efficient treeview update - only update if needed
        existing_items = self.window_tree.get_children()
        
        # Sort windows by time spent (descending)
        # Get only top 20 entries to avoid processing too many items
        sorted_windows = sorted(self.window_activity.items(), key=lambda x: x[1], reverse=True)[:20]
        
        if len(existing_items) > 0:
            # Clear and rebuild only if we have significant changes
            for item in existing_items:
                self.window_tree.delete(item)
                
            # Add items to the tree
            for window_name, seconds in sorted_windows:
                time_str = self.format_time(seconds)
                self.window_tree.insert("", tk.END, values=(window_name, time_str))
        else:
            # First population
            for window_name, seconds in sorted_windows:
                time_str = self.format_time(seconds)
                self.window_tree.insert("", tk.END, values=(window_name, time_str))
    
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
                    # Update window statistics (separate interval handled inside)
                    self.update_window_tree()
            
            # Sleep for a shorter time to improve responsiveness
            time.sleep(0.1)
    
    def start_threads(self):
        # Start keyboard listener with exclusive mode for better performance
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press, suppress=False)
        self.kb_listener.daemon = True
        self.kb_listener.start()
        
        # Start mouse listener
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.mouse_listener.daemon = True
        self.mouse_listener.start()
        
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
        if self.kb_listener.is_alive():
            self.kb_listener.stop()
        if self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = EnhancedTypingTimeTracker(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()