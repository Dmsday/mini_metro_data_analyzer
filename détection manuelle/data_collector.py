import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
import json
from datetime import datetime
import math

# -------------------------------
# Dialog to choose a shape (for station or demand)
# -------------------------------
class StationShapeDialog(tk.Toplevel):
    def __init__(self, master, prompt="Select the shape for the station:", dialog_title="Station Shape Selection"):
        super().__init__(master)
        self.title(dialog_title)
        self.result = None
        self.geometry("300x100")
        self.resizable(False, False)
        ttk.Label(self, text=prompt).pack(pady=5)
        self.combobox = ttk.Combobox(
            self,
            values=['circle', 'square', 'triangle', 'cross', 'bell', 'star'],
            state='readonly'
        )
        self.combobox.set('circle')
        self.combobox.pack(pady=5)
        ok_button = ttk.Button(self, text="OK", command=self.on_ok)
        ok_button.pack(pady=5)
        self.grab_set()  # Make this dialog modal
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_ok(self):
        self.result = self.combobox.get()
        self.destroy()

    def on_close(self):
        self.destroy()


# -------------------------------
# Main Application Class
# -------------------------------
class MiniMetroDataCollector:
    def __init__(self):
        # Initialize main window (resizable)
        self.root = tk.Tk()
        self.root.title("Mini Metro Data Collector")
        self.root.resizable(True, True)

        # Define colors for up to 7 lines
        self.line_colors = ["yellow", "dark blue", "green", "purple", "orange", "brown", "pink"]

        # Application state variables
        self.recording = False        # Recording state (overlay active)
        self.game_active = False      # Is the game started?
        self.drawing_line = False     # Are we currently drawing/extending a line?
        self.current_line_index = None  # Index of the current line in self.current_data['lines']

        # Data storage:
        # - stations: each station is a tuple (x, y, shape, [demand shapes])
        # - obstacles: list of obstacles (each is a list of points)
        # - lines: each line is a dictionary with keys:
        #       'stations': list of connected station points
        #       'number': line number
        #       'color': color for the line
        # - resources: trains, wagons, tunnels, line_available (new lines available) and line_placed (lines already placed)
        self.current_data = {
            'stations': [],
            'obstacles': [],
            'lines': [],
            'resources': {
                'trains': 3,
                'wagons': 0,
                'tunnels': 3,          # Number of tunnels available
                'line_available': 3,   # New lines available (max 7 total lines = available + placed)
                'line_placed': 0       # Lines that have been placed
            }
        }

        # Setup main UI and overlay window
        self.setup_ui()
        self.setup_overlay_window()

        # Variables for drawing obstacles and for dialog positioning
        self.drawing = False
        self.current_obstacle = []
        self.last_click_x = 0  # x-coordinate of last click (for dialog placement)
        self.last_click_y = 0  # y-coordinate of last click

        # Configure global keyboard shortcuts
        self.setup_keyboard_shortcuts()

    # -------------------------------
    # Configure global keyboard shortcuts
    # -------------------------------
    def setup_keyboard_shortcuts(self):
        keyboard.on_press_key('g', self.handle_g_press)
        keyboard.on_press_key('r', self.handle_r_press)

    def handle_g_press(self, e):
        if keyboard.is_pressed('shift'):
            self.root.after(0, self.toggle_game)

    def handle_r_press(self, e):
        if keyboard.is_pressed('shift') and self.game_active:
            self.root.after(0, self.toggle_recording)

    # -------------------------------
    # Setup UI elements
    # -------------------------------
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')

        # ----- Status Tab -----
        status_frame = ttk.Frame(self.notebook)
        self.notebook.add(status_frame, text='Status')

        self.status_label = tk.Label(status_frame, text="Press Shift+G to start a game")
        self.status_label.pack(pady=5)

        shortcuts_text = (
            "Shortcuts:\n"
            "Shift+G : Start/Stop game\n"
            "Shift+R : Start/Stop recording\n"
            "Left-click on canvas : Add station\n"
            "Maintain Left-click on canvas : draw obstacle\n"
            "Right-click on canvas : Extend/Add a line\n"
            "In Summary tab : Use dropdown to change station shape and 'Add Demand' button"
        )
        self.shortcuts_label = tk.Label(status_frame, text=shortcuts_text, justify="left")
        self.shortcuts_label.pack(pady=5)

        self.restart_button = tk.Button(status_frame, text="Restart Game", command=self.restart_game)
        self.restart_button.pack(pady=5)

        self.quit_button = tk.Button(status_frame, text="Quit", command=self.root.destroy)
        self.quit_button.pack(pady=5)

        # ----- Resources Tab -----
        resources_frame = ttk.Frame(self.notebook)
        self.notebook.add(resources_frame, text='Resources')

        self.trains_spinbox = self.create_resource_spinbox(resources_frame, "Trains:", 'trains')
        self.wagons_spinbox = self.create_resource_spinbox(resources_frame, "Wagons:", 'wagons')
        self.tunnels_spinbox = self.create_resource_spinbox(resources_frame, "Tunnels:", 'tunnels')
        self.line_avail_spinbox = self.create_resource_spinbox(resources_frame, "Line Available:", 'line_available')

        frame_line_placed = ttk.Frame(resources_frame)
        frame_line_placed.pack(pady=5, anchor='w')
        ttk.Label(frame_line_placed, text="Line Placed: ").pack(side=tk.LEFT)
        self.line_placed_label = ttk.Label(frame_line_placed, text="0")
        self.line_placed_label.pack(side=tk.LEFT)

        # ----- Summary Tab -----
        summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(summary_frame, text='Summary')

        stations_frame = ttk.LabelFrame(summary_frame, text="Stations")
        stations_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.stations_tree = ttk.Treeview(stations_frame, columns=("Shape", "Demands", "Action"), show="headings")
        self.stations_tree.heading("Shape", text="Shape")
        self.stations_tree.heading("Demands", text="Demands")
        self.stations_tree.heading("Action", text="Action")
        self.stations_tree.column("Action", width=100, anchor='center')
        self.stations_tree.pack(fill='both', expand=True)
        self.stations_tree.bind("<Button-1>", self.station_tree_click)

        station_props_frame = ttk.LabelFrame(summary_frame, text="Station Properties")
        station_props_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(station_props_frame, text="Change Shape:").pack(side='left')
        self.station_shape_combobox = ttk.Combobox(
            station_props_frame,
            values=['circle', 'square', 'triangle', 'cross', 'bell', 'star'],
            state='readonly'
        )
        self.station_shape_combobox.pack(side='left', padx=5)
        self.station_shape_combobox.bind('<<ComboboxSelected>>', self.on_station_shape_change)

        lines_frame = ttk.LabelFrame(summary_frame, text="Lines")
        lines_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.lines_tree = ttk.Treeview(lines_frame, columns=("Line", "Status"), show="headings")
        self.lines_tree.heading("Line", text="Line")
        self.lines_tree.heading("Status", text="Status")
        self.lines_tree.column("Line", width=80, anchor='center')
        self.lines_tree.column("Status", width=300, anchor='w')
        self.lines_tree.pack(fill='both', expand=True)
        # Add Demands management frame
        demands_frame = ttk.LabelFrame(summary_frame, text="Station Demands")
        demands_frame.pack(fill='x', padx=5, pady=5)

        # Add demands list
        self.demands_listbox = ttk.Combobox(demands_frame, state='readonly')
        self.demands_listbox.pack(side='left', padx=5)

        # Add remove demand button
        self.remove_demand_btn = ttk.Button(demands_frame, text="Remove Selected Demand",
                                            command=self.remove_selected_demand)
        self.remove_demand_btn.pack(side='left', padx=5)

    # Function to create a resource spinbox
    def create_resource_spinbox(self, parent, label, resource_key):
        frame = ttk.Frame(parent)
        frame.pack(pady=5, anchor='w')
        ttk.Label(frame, text=label).pack(side=tk.LEFT)

        if resource_key == 'line_available':
            spinbox = ttk.Spinbox(frame, from_=0, to=7, width=5,
                                  command=lambda: self.update_line_resources())
        else:
            spinbox = ttk.Spinbox(frame, from_=0, to=100, width=5,
                                  command=lambda: self.update_resource(resource_key))
        spinbox.pack(side=tk.LEFT)
        return spinbox

    # -------------------------------
    # Setup overlay window for drawing
    # -------------------------------
    def setup_overlay_window(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.attributes('-topmost', True)
        self.overlay.withdraw()

    # -------------------------------
    # Toggle game state : start/stop game
    # -------------------------------
    def toggle_game(self):
        if self.game_active:
            # Stop the game
            self.game_active = False
            self.recording = False
            self.status_label.config(text="Game ended")
            self.overlay.withdraw()
        else:
            self.restart_game()

    def restart_game(self):
        # Reset all game data and update UI
        self.game_active = True
        self.recording = False
        self.current_data = {
            'stations': [],
            'obstacles': [],
            'lines': [],
            'resources': {
                'trains': 3,
                'wagons': 0,
                'tunnels': 1,
                'line_available': 3,
                'line_placed': 0
            }
        }
        self.reset_resources()
        self.status_label.config(text="Game in progress - Press Shift+R to record")
        self.update_stations_summary()
        self.update_lines_summary()
        self.redraw_canvas()

    def reset_resources(self):
        # Reset resource values and update UI elements
        self.current_data['resources']['trains'] = 3
        self.current_data['resources']['wagons'] = 0
        self.current_data['resources']['tunnels'] = 3
        self.current_data['resources']['line_available'] = 3
        self.current_data['resources']['line_placed'] = 0
        self.trains_spinbox.set(3)
        self.wagons_spinbox.set(0)
        self.tunnels_spinbox.set(3)
        self.line_avail_spinbox.set(3)
        self.line_placed_label.config(text="0")

    def update_resources_ui(self):
        # Update the resource UI elements
        self.line_avail_spinbox.set(self.current_data['resources']['line_available'])
        self.line_placed_label.config(text=str(self.current_data['resources']['line_placed']))
        self.trains_spinbox.set(self.current_data['resources']['trains'])
        self.wagons_spinbox.set(self.current_data['resources']['wagons'])
        self.tunnels_spinbox.set(self.current_data['resources']['tunnels'])

    def update_resource(self, resource):
        # Update a specific resource value from its spinbox input
        if resource == 'trains':
            value = int(self.trains_spinbox.get())
        elif resource == 'wagons':
            value = int(self.wagons_spinbox.get())
        elif resource == 'tunnels':
            value = int(self.tunnels_spinbox.get())
        elif resource == 'line_available':
            value = int(self.line_avail_spinbox.get())
            if value > 7:
                value = 7
                self.line_avail_spinbox.set(value)
        else:
            return
        self.current_data['resources'][resource] = value

    # -------------------------------
    # Toggle recording : show/hide overlay for drawing
    # -------------------------------
    def toggle_recording(self):
        if not self.game_active:
            return
        self.recording = not self.recording
        if self.recording:
            self.status_label.config(text="Recording in progress...")
            self.overlay.deiconify()
            self.setup_overlay()
        else:
            self.status_label.config(text="Recording stopped")
            self.overlay.withdraw()
            self.save_data()

    def setup_overlay(self):
        self.overlay.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        if not hasattr(self, 'canvas'):
            self.canvas = tk.Canvas(self.overlay, highlightthickness=0)
            self.canvas.pack(fill='both', expand=True)
            # Bind mouse events for adding station or drawing obstacles
            self.canvas.bind('<Button-1>', self.start_drawing)
            self.canvas.bind('<B1-Motion>', self.draw)
            self.canvas.bind('<ButtonRelease-1>', self.stop_drawing)
            self.canvas.bind('<Double-Button-1>', self.remove_element)
            # Bind right-click events for line drawing/extension
            self.canvas.bind('<Button-3>', self.start_line)
            self.canvas.bind('<B3-Motion>', self.draw_line)
            self.canvas.bind('<ButtonRelease-3>', self.stop_line)
            self.canvas.bind('<Double-Button-3>', self.remove_line)

    # -------------------------------
    # Drawing on the canvas (stations, obstacles, lines)
    # -------------------------------
    def start_drawing(self, event):
        if not self.recording:
            return
        self.drawing = True
        self.current_obstacle = [(event.x, event.y)]
        # Save click position for dialog placement
        self.last_click_x = event.x_root
        self.last_click_y = event.y_root
        # After 100ms, if no movement, consider it as adding a station
        self.root.after(100, self.check_if_station, event.x, event.y)

    def check_if_station(self, x, y):
        if self.drawing and len(self.current_obstacle) == 1:
            # Show dialog above overlay near click position
            dialog = StationShapeDialog(self.root, prompt="Select station shape:", dialog_title="Station Shape Selection")
            dialog.geometry("+{}+{}".format(self.last_click_x + 10, self.last_click_y + 10))
            dialog.lift()
            dialog.attributes('-topmost', True)
            self.root.wait_window(dialog)
            shape = dialog.result if dialog.result is not None else 'circle'
            self.current_data['stations'].append((x, y, shape, []))
            self.draw_station(x, y, shape)
            self.current_obstacle = []
            self.drawing = False
            self.update_stations_summary()

    def draw_station(self, x, y, shape="circle"):
        if not hasattr(self, 'canvas'):
            return
        # Increase station size (radius 10)
        if shape == "circle":
            self.canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill='red')
        elif shape == "square":
            self.canvas.create_rectangle(x - 10, y - 10, x + 10, y + 10, fill='red')
        elif shape == "triangle":
            self.canvas.create_polygon(x, y - 10, x - 10, y + 10, x + 10, y + 10, fill='red')
        elif shape == "cross":
            self.canvas.create_line(x - 10, y - 10, x + 10, y + 10, fill='red', width=2)
            self.canvas.create_line(x - 10, y + 10, x + 10, y - 10, fill='red', width=2)
        elif shape == "bell":
            self.canvas.create_arc(x - 10, y - 10, x + 10, y + 10, start=0, extent=180, fill='red')
        elif shape == "star":
            self.draw_star(x, y, 10)

    def draw_star(self, x, y, size):
        points = []
        for i in range(10):
            angle = math.radians(i * 36)
            r = size if i % 2 == 0 else size * 0.5
            points.append(x + r * math.sin(angle))
            points.append(y - r * math.cos(angle))
        self.canvas.create_polygon(points, fill='red', outline='black')

    def draw(self, event):
        if not self.recording or not self.drawing:
            return
        self.current_obstacle.append((event.x, event.y))
        if len(self.current_obstacle) > 1:
            x1, y1 = self.current_obstacle[-2]
            x2, y2 = self.current_obstacle[-1]
            self.canvas.create_line(x1, y1, x2, y2, fill='blue', width=2)

    def stop_drawing(self, event):
        if not self.recording or not self.drawing:
            return
        if len(self.current_obstacle) > 1:
            self.current_data['obstacles'].append(self.current_obstacle)
        self.drawing = False

    def remove_element(self, event):
        x, y = event.x, event.y
        # Remove a station if click is near it
        for i, (sx, sy, shape, demands) in enumerate(self.current_data['stations']):
            if abs(x - sx) < 10 and abs(y - sy) < 10:
                self.current_data['stations'].pop(i)
                self.update_stations_summary()
                self.redraw_canvas()
                return
        # Remove an obstacle if click is near it
        for i, obstacle in enumerate(self.current_data['obstacles']):
            for px, py in obstacle:
                if abs(x - px) < 10 and abs(y - py) < 10:
                    self.current_data['obstacles'].pop(i)
                    self.redraw_canvas()
                    return

    # -------------------------------
    # Line drawing and extension
    # -------------------------------
    def get_line_endpoint_at(self, x, y, threshold=15):
        """Check if (x,y) is near an endpoint of any line"""
        for index, line in enumerate(self.current_data['lines']):
            if line['stations']:
                # Get first and last stations
                first = line['stations'][0]
                last = line['stations'][-1]

                # Calculate extended endpoint positions
                for station, is_start in [(first, True), (last, False)]:
                    # Find the direction to extend
                    if is_start and len(line['stations']) > 1:
                        next_station = line['stations'][1]
                        angle = math.atan2(station[1] - next_station[1],
                                           station[0] - next_station[0])
                    elif not is_start and len(line['stations']) > 1:
                        prev_station = line['stations'][-2]
                        angle = math.atan2(station[1] - prev_station[1],
                                           station[0] - prev_station[0])
                    else:
                        continue

                    # Calculate extended endpoint
                    extension_length = 15
                    ext_x = station[0] + (-extension_length if is_start else extension_length) * math.cos(angle)
                    ext_y = station[1] + (-extension_length if is_start else extension_length) * math.sin(angle)

                    # Check if click is near extended endpoint
                    if math.hypot(x - ext_x, y - ext_y) < threshold:
                        return index, is_start
        return None, None

    def start_line(self, event):
        if not self.recording:
            return
            # Check if click is on an endpoint circle
        endpoint_line, is_start = self.get_line_endpoint_at(event.x, event.y)
        if endpoint_line is not None:
            self.current_line_index = endpoint_line
            self.drawing_line = True
            self.extending_from_start = is_start
            return

        # Find clicked station
        clicked_station = self.find_nearest_station(event.x, event.y)
        if not clicked_station:
            return

        # Store only coordinates of the station, not the full tuple
        station_coords = (clicked_station[0], clicked_station[1])
        self.extending_from_start = False  # New line always extends from end

        # Check if this station is the endpoint of an existing line
        line_index = None
        for i, line in enumerate(self.current_data['lines']):
            if line['stations'] and (line['stations'][-1][0] == station_coords[0] and
                                     line['stations'][-1][1] == station_coords[1]):
                line_index = i
                break

        if line_index is not None:
            self.current_line_index = line_index
        else:
            # Create new line if available
            if self.current_data['resources']['line_available'] > 0:
                new_line = {
                    'stations': [station_coords],  # Store only coordinates
                    'number': len(self.current_data['lines']) + 1,
                    'color': self.line_colors[len(self.current_data['lines']) % len(self.line_colors)]
                }
                self.current_data['lines'].append(new_line)
                self.current_line_index = len(self.current_data['lines']) - 1
                self.current_data['resources']['line_available'] -= 1
                self.current_data['resources']['line_placed'] += 1
                self.update_resources_ui()
            else:
                messagebox.showerror("Error", "No available line to create a new line.", parent=self.overlay)
                return
        self.drawing_line = True

    def draw_line(self, event):
        if not self.drawing_line or self.current_line_index is None:
            return
        self.canvas.delete('temp_line')
        line = self.current_data['lines'][self.current_line_index]
        if hasattr(self, 'extending_from_start') and self.extending_from_start:
            start_point = line['stations'][0]
        else:
            start_point = line['stations'][-1]

        line_color = line['color']
        self.canvas.create_line(start_point[0], start_point[1],
                                event.x, event.y,
                                fill=line_color, tags='temp_line', width=2)

    def calculate_line_offset(self, start, end, line_index):
        """
        Calculate offset for parallel lines between same stations.
        Returns offset vector (dx, dy) perpendicular to line direction.
        """
        # Find how many lines connect these stations
        parallel_lines = []
        for i, line in enumerate(self.current_data['lines']):
            stations = line['stations']
            for j in range(len(stations) - 1):
                if ((stations[j] == start and stations[j + 1] == end) or
                        (stations[j] == end and stations[j + 1] == start)):
                    parallel_lines.append(i)

        if len(parallel_lines) <= 1:
            return (0, 0)

        # Calculate perpendicular vector
        dx = end[1] - start[1]
        dy = start[0] - end[0]
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return (0, 0)

        # Normalize and scale
        dx = (dx / length) * 5  # 5 pixels offset between parallel lines
        dy = (dy / length) * 5

        # Calculate this line's position in parallel lines
        position = parallel_lines.index(line_index)
        offset = position - (len(parallel_lines) - 1) / 2

        return (dx * offset, dy * offset)

    def draw_line_segment(self, start, end, color, line_index):
        """Draw a line segment with appropriate offset if parallel lines exist"""
        dx, dy = self.calculate_line_offset(start, end, line_index)
        start_offset = (start[0] + dx, start[1] + dy)
        end_offset = (end[0] + dx, end[1] + dy)

        # Calculate angle for extensions
        angle = math.atan2(end[1] - start[1], end[0] - start[0])

        # Draw extended line segments and endpoint circles
        extension_length = 15  # Length of extension beyond stations

        # Extend at start if it's an endpoint
        if start == self.current_data['lines'][line_index]['stations'][0]:
            ext_start_x = start_offset[0] - extension_length * math.cos(angle)
            ext_start_y = start_offset[1] - extension_length * math.sin(angle)
            self.canvas.create_line(ext_start_x, ext_start_y,
                                    start_offset[0], start_offset[1],
                                    fill=color, width=2)
            # Draw start endpoint circle
            self.canvas.create_oval(ext_start_x - 5, ext_start_y - 5,
                                    ext_start_x + 5, ext_start_y + 5,
                                    fill=color, outline='black')

        # Draw main line segment
        self.canvas.create_line(start_offset[0], start_offset[1],
                                end_offset[0], end_offset[1],
                                fill=color, width=2)

        # Extend at end if it's an endpoint
        if end == self.current_data['lines'][line_index]['stations'][-1]:
            ext_end_x = end_offset[0] + extension_length * math.cos(angle)
            ext_end_y = end_offset[1] + extension_length * math.sin(angle)
            self.canvas.create_line(end_offset[0], end_offset[1],
                                    ext_end_x, ext_end_y,
                                    fill=color, width=2)
            # Draw end endpoint circle
            self.canvas.create_oval(ext_end_x - 5, ext_end_y - 5,
                                    ext_end_x + 5, ext_end_y + 5,
                                    fill=color, outline='black')

    def stop_line(self, event):
        if not self.drawing_line or self.current_line_index is None:
            return
        end_station = self.find_nearest_station(event.x, event.y)
        if not end_station:
            self.canvas.delete('temp_line')
            self.drawing_line = False
            self.current_line_index = None
            return

        end_coords = (end_station[0], end_station[1])
        line = self.current_data['lines'][self.current_line_index]

        if hasattr(self, 'extending_from_start') and self.extending_from_start:
            start_coords = line['stations'][0]
        else:
            start_coords = line['stations'][-1]

        # Check for tunnel requirements, counting each obstacle crossing
        tunnel_count = self.count_tunnel_required(start_coords, end_coords)
        if tunnel_count > 0:
            if self.current_data['resources']['tunnels'] < tunnel_count:
                messagebox.showerror("Error", f"Not enough tunnels. Need {tunnel_count} tunnels.", parent=self.overlay)
                self.canvas.delete('temp_line')
                self.drawing_line = False
                self.current_line_index = None
                return
            else:
                self.current_data['resources']['tunnels'] -= tunnel_count
                self.update_resources_ui()

        # Add station to correct end of line
        if hasattr(self, 'extending_from_start') and self.extending_from_start:
            line['stations'].insert(0, end_coords)
        else:
            line['stations'].append(end_coords)

        self.update_lines_summary()
        self.redraw_canvas()
        self.canvas.delete('temp_line')
        self.drawing_line = False
        self.current_line_index = None

    # Add method to count tunnel crossings
    def count_tunnel_required(self, start, end):
        """Count how many times a line segment crosses obstacles"""
        count = 0
        for obstacle in self.current_data['obstacles']:
            for i in range(len(obstacle) - 1):
                if self.line_intersect(start, end, obstacle[i], obstacle[i + 1]):
                    count += 1
        return count

    # Add station memory to lines and handle station deletion :
    def remove_element(self, event):
        x, y = event.x, event.y
        # Remove a station if click is near it
        for i, (sx, sy, shape, demands) in enumerate(self.current_data['stations']):
            if abs(x - sx) < 10 and abs(y - sy) < 10:
                # Remember connected stations for each line
                self.handle_station_removal(i)
                self.current_data['stations'].pop(i)
                self.update_stations_summary()
                self.redraw_canvas()
                return

    def handle_station_removal(self, station_index):
        station = self.current_data['stations'][station_index]
        station_pos = (station[0], station[1])

        # Check each line
        i = 0
        while i < len(self.current_data['lines']):
            line = self.current_data['lines'][i]
            if station_pos in line['stations']:
                idx = line['stations'].index(station_pos)

                # If station is at the end or beginning, just remove it
                if idx == 0 or idx == len(line['stations']) - 1:
                    line['stations'].remove(station_pos)
                else:
                    # Connect previous and next stations
                    prev_station = line['stations'][idx - 1]
                    next_station = line['stations'][idx + 1]

                    # Check if tunnels are needed for new connection
                    tunnel_count = self.count_tunnel_required(prev_station, next_station)
                    self.current_data['resources']['tunnels'] += tunnel_count

                    # Remove current station
                    line['stations'].pop(idx)

                # If less than 2 stations remain, remove the line
                if len(line['stations']) < 2:
                    self.current_data['lines'].pop(i)
                    self.current_data['resources']['line_available'] += 1
                    self.current_data['resources']['line_placed'] -= 1
                    i -= 1  # Adjust index since we removed a line

                self.update_resources_ui()
                self.update_lines_summary()
            i += 1

    def remove_line(self, event):
        x, y = event.x, event.y
        for i, line in enumerate(self.current_data['lines']):
            pts = line['stations']
            for j in range(len(pts) - 1):
                if self.point_near_line(x, y, pts[j][0], pts[j][1], pts[j + 1][0], pts[j + 1][1]):
                    # Check for tunnels in this line
                    for k in range(len(pts) - 1):
                        if self.check_tunnel_required(pts[k], pts[k + 1]):
                            self.current_data['resources']['tunnels'] += 1

                    self.current_data['lines'].pop(i)
                    self.current_data['resources']['line_available'] += 1
                    self.current_data['resources']['line_placed'] -= 1
                    self.update_lines_summary()
                    self.redraw_canvas()
                    self.update_resources_ui()
                    return

    def find_nearest_station(self, x, y, threshold=10):
        for station in self.current_data['stations']:
            if abs(station[0] - x) < threshold and abs(station[1] - y) < threshold:
                return station
        return None

    # -------------------------------
    # Check if a tunnel is required between two stations (if the segment crosses an obstacle)
    # -------------------------------
    def check_tunnel_required(self, start, end):
        for obstacle in self.current_data['obstacles']:
            for i in range(len(obstacle) - 1):
                if self.line_intersect(start, end, obstacle[i], obstacle[i+1]):
                    return True
        return False

    def line_intersect(self, p1, p2, p3, p4):
        # Segment intersection algorithm
        def ccw(A, B, C):
            return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
        return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))

    def point_near_line(self, px, py, x1, y1, x2, y2, threshold=10):
        # Calculate distance from point to segment
        line_mag = math.hypot(x2 - x1, y2 - y1)
        if line_mag < 0.000001:
            return False
        u = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (line_mag ** 2)
        if u < 0 or u > 1:
            return False
        ix = x1 + u * (x2 - x1)
        iy = y1 + u * (y2 - y1)
        distance = math.hypot(px - ix, py - iy)
        return distance < threshold

    # -------------------------------
    # Update Summary tab for stations and lines
    # -------------------------------
    def update_stations_summary(self):
        self.stations_tree.delete(*self.stations_tree.get_children())
        for i, station in enumerate(self.current_data['stations']):
            shape = station[2]
            demands = ', '.join(station[3])
            self.stations_tree.insert('', 'end', iid=str(i), values=(shape, demands, "Add Demand"))

        # Update demands dropdown if a station is selected
        selected = self.stations_tree.selection()
        if selected:
            station_index = int(selected[0])
            demands = self.current_data['stations'][station_index][3]
            self.demands_listbox['values'] = demands
            if demands:
                self.demands_listbox.set(demands[0])

    # station demand removal functionality
    def remove_selected_demand(self):
        selected_station = self.stations_tree.selection()
        if not selected_station:
            return

        station_index = int(selected_station[0])
        selected_demand = self.demands_listbox.get()
        if selected_demand:
            station = self.current_data['stations'][station_index]
            demands = list(station[3])  # Convert to list to modify
            if selected_demand in demands:
                demands.remove(selected_demand)
                self.current_data['stations'][station_index] = (
                    station[0], station[1], station[2], demands
                )
                self.update_stations_summary()
                self.redraw_canvas()

    def update_lines_summary(self):
        self.lines_tree.delete(*self.lines_tree.get_children())

        # Show only available + placed lines
        total_lines = (self.current_data['resources']['line_available'] +
                       self.current_data['resources']['line_placed'])

        for i in range(total_lines):
            line_label = f"Line {i + 1}"
            if i < len(self.current_data['lines']):
                line = self.current_data['lines'][i]
                stations_str = " -> ".join([f"({pt[0]},{pt[1]})" for pt in line['stations']])
                status = stations_str
            else:
                status = "Available"
            self.lines_tree.insert('', 'end', values=(line_label, status))

        # Add unavailable lines
        for i in range(total_lines, 7):
            line_label = f"Line {i + 1}"
            self.lines_tree.insert('', 'end', values=(line_label, "Unavailable"))

    def update_line_resources(self):
        placed_lines = self.current_data['resources']['line_placed']
        available = int(self.line_avail_spinbox.get())

        # Ensure total lines don't exceed 7
        if available + placed_lines > 7:
            available = 7 - placed_lines
            self.line_avail_spinbox.set(available)

        self.current_data['resources']['line_available'] = available
        self.update_lines_summary()

    # -------------------------------
    # Handle clicks in the stations Treeview for adding a demand
    # -------------------------------
    def station_tree_click(self, event):
        region = self.stations_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.stations_tree.identify_column(event.x)
        if col == "#3":  # Action column
            item = self.stations_tree.identify_row(event.y)
            if item:
                station_index = int(item)
                self.add_demand_for_station(station_index)

    def add_demand_for_station(self, station_index):
        # Open a dialog to choose the demand shape
        dialog = StationShapeDialog(self.root, prompt="Select demand shape:", dialog_title="Demand Shape Selection")
        dialog.lift()
        dialog.attributes('-topmost', True)
        self.root.wait_window(dialog)
        shape = dialog.result if dialog.result is not None else 'circle'
        station = self.current_data['stations'][station_index]
        demands = station[3]
        demands.append(shape)
        self.current_data['stations'][station_index] = (station[0], station[1], station[2], demands)
        self.update_stations_summary()
        self.redraw_canvas()

    def on_station_shape_change(self, event):
        selected = self.stations_tree.selection()
        if selected:
            station_index = int(selected[0])
            new_shape = self.station_shape_combobox.get()
            x, y, _, demands = self.current_data['stations'][station_index]
            self.current_data['stations'][station_index] = (x, y, new_shape, demands)
            self.update_stations_summary()
            self.redraw_canvas()

    # -------------------------------
    # Redraw the canvas (stations, obstacles, lines, and endpoint circles)
    # -------------------------------
    def redraw_canvas(self):
        if hasattr(self, 'canvas'):
            self.canvas.delete("all")

            # Draw obstacles
            for obstacle in self.current_data['obstacles']:
                for i in range(len(obstacle) - 1):
                    x1, y1 = obstacle[i]
                    x2, y2 = obstacle[i + 1]
                    self.canvas.create_line(x1, y1, x2, y2, fill='blue', width=2)

            # Draw lines
            for line_index, line in enumerate(self.current_data['lines']):
                pts = line['stations']
                for i in range(len(pts) - 1):
                    self.draw_line_segment(pts[i], pts[i + 1], line['color'], line_index)

            # Draw stations last
            for x, y, shape, demands in self.current_data['stations']:
                self.draw_station(x, y, shape)

    # -------------------------------
    # Save game data to a JSON file
    # -------------------------------
    def save_data(self):
        if self.game_active:
            if not hasattr(self, 'game_filename'):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.game_filename = f"mini_metro_game_{timestamp}.json"
            try:
                with open(self.game_filename, 'r') as f:
                    game_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                game_data = {'snapshots': []}
            current_snapshot = {
                'timestamp': datetime.now().isoformat(),
                'data': self.current_data
            }
            game_data['snapshots'].append(current_snapshot)
            with open(self.game_filename, 'w') as f:
                json.dump(game_data, f, indent=2)
            print(f"State saved in {self.game_filename}")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mini_metro_data_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(self.current_data, f, indent=2)
            print(f"Data saved in {filename}")

    # -------------------------------
    # Run the main application loop
    # -------------------------------
    def run(self):
        try:
            self.root.mainloop()
        finally:
            keyboard.unhook_all()


if __name__ == "__main__":
    app = MiniMetroDataCollector()
    app.run()
