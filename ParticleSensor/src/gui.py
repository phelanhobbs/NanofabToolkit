#!/usr/bin/env python3
"""
Particle Data Viewer GUI
A simple GUI application to view particle sensor data from the API endpoint.
"""

import sys
import warnings
import requests
import json
import csv
from datetime import datetime, timedelta
import pytz
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QFrame, QLabel, QMessageBox,
                             QHeaderView, QComboBox, QSplitter, QCheckBox, QGridLayout, QDateEdit, QFileDialog)
from PyQt5.QtCore import Qt, QDate

# Disable SSL warnings using warnings module
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Mountain Time timezone
MOUNTAIN_TZ = pytz.timezone('US/Mountain')

def convert_to_mountain(dt):
    """Convert datetime to Mountain Time, adding offset to fix API time discrepancy"""
    # Add 7 hours to fix the time discrepancy observed in the API data
    corrected_dt = dt + timedelta(hours=7)
    
    if corrected_dt.tzinfo is None:
        # Assume it's now in Mountain Time after correction
        return MOUNTAIN_TZ.localize(corrected_dt)
    else:
        # Convert to Mountain Time if it has timezone info
        return corrected_dt.astimezone(MOUNTAIN_TZ)


class ParticleDataViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_url = "https://nfhistory.nanofab.utah.edu/particle-data"
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Particle Data Viewer")
        self.setGeometry(100, 100, 1200, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_data)
        self.refresh_button.setMaximumWidth(150)
        main_layout.addWidget(self.refresh_button, alignment=Qt.AlignCenter)
        
        # Content layout (left and right halves)
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)
        
        # Left half - Empty box (placeholder for future use)
        left_frame = QFrame()
        left_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        left_frame.setLineWidth(2)
        left_layout = QVBoxLayout()
        left_frame.setLayout(left_layout)
        left_label = QLabel("Reserved Area")
        left_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(left_label)
        content_layout.addWidget(left_frame, 1)  # stretch factor of 1
        
        # Right half - Table for particle data
        right_frame = QFrame()
        right_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        right_frame.setLineWidth(2)
        right_layout = QVBoxLayout()
        right_frame.setLayout(right_layout)
        
        right_label = QLabel("Particle Data")
        right_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(right_label)
        
        # Information label about double-click functionality
        info_label = QLabel("💡 Double-click any sensor row to view historical data")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #666; font-style: italic; margin: 5px; font-size: 12px;")
        right_layout.addWidget(info_label)
        
        # Create table
        self.table = QTableWidget()
        # Define columns
        self.columns = [
            "Room Name", "Sensor Number", "Timestamp",
            "pm0_5 (ft³)", "pm1 (ft³)", "pm2_5 (ft³)", "pm4 (ft³)", "pm10 (ft³)"
        ]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.on_sensor_double_click)
        right_layout.addWidget(self.table)
        
        content_layout.addWidget(right_frame, 1)  # stretch factor of 1
        
    def refresh_data(self):
        """Fetch data from API and populate the table"""
        try:
            # Make GET request to the API
            response = requests.get(self.api_url, verify=False, timeout=5)
            response.raise_for_status()
            
            # Parse JSON data
            data = response.json()
            
            # Clear existing data
            self.table.setRowCount(0)
            
            # Populate table with data
            self.populate_table(data)
            
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Connection Error", 
                               f"Could not connect to {self.api_url}\nMake sure the server is running.")
        except requests.exceptions.Timeout:
            QMessageBox.critical(self, "Timeout Error", 
                               "Request timed out. Server may be unresponsive.")
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Request Error", f"Error fetching data: {str(e)}")
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Parse Error", "Invalid JSON response from server.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
            
    def populate_table(self, data, prefix=""):
        """Populate the table with particle sensor data"""
        # Handle the API response structure with sensors array
        if isinstance(data, dict) and "sensors" in data:
            data_list = data["sensors"]
        elif isinstance(data, list):
            data_list = data
        else:
            data_list = [data]
        
        for record in data_list:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            
            # Column 0: Room Name
            room_name = record.get("room_name", "N/A") if isinstance(record, dict) else "N/A"
            self.table.setItem(row_position, 0, QTableWidgetItem(str(room_name)))
            
            # Column 1: Sensor Number
            sensor_number = record.get("sensor_number", "N/A") if isinstance(record, dict) else "N/A"
            self.table.setItem(row_position, 1, QTableWidgetItem(str(sensor_number)))
            
            # Column 2: Timestamp
            timestamp = record.get("timestamp") if isinstance(record, dict) else None
            if timestamp:
                try:
                    # Handle string timestamp format
                    if isinstance(timestamp, str):
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        # Convert to Mountain Time
                        dt_mountain = convert_to_mountain(dt)
                        timestamp_str = dt_mountain.strftime('%Y-%m-%d %H:%M:%S %Z')
                    else:
                        dt = datetime.fromtimestamp(timestamp)
                        # Convert to Mountain Time
                        dt_mountain = convert_to_mountain(dt)
                        timestamp_str = dt_mountain.strftime('%Y-%m-%d %H:%M:%S %Z')
                except:
                    timestamp_str = str(timestamp)
            else:
                timestamp_str = "N/A"
            self.table.setItem(row_position, 2, QTableWidgetItem(timestamp_str))
            
            # Get converted values
            converted = record.get("converted_values", {}) if isinstance(record, dict) else {}
            
            # Columns 3-7: Number concentrations (ft³)
            num_conc = converted.get("number_concentrations_ft3", {}) if isinstance(converted, dict) else {}
            self.table.setItem(row_position, 3, QTableWidgetItem(str(num_conc.get("pm0_5", "N/A"))))
            self.table.setItem(row_position, 4, QTableWidgetItem(str(num_conc.get("pm1", "N/A"))))
            self.table.setItem(row_position, 5, QTableWidgetItem(str(num_conc.get("pm2_5", "N/A"))))
            self.table.setItem(row_position, 6, QTableWidgetItem(str(num_conc.get("pm4", "N/A"))))
            self.table.setItem(row_position, 7, QTableWidgetItem(str(num_conc.get("pm10", "N/A"))))
    
    def on_sensor_double_click(self, item):
        """Handle double-click on sensor table item"""
        row = item.row()
        room_name_item = self.table.item(row, 0)
        sensor_number_item = self.table.item(row, 1)
        
        if room_name_item and sensor_number_item:
            room_name = room_name_item.text()
            sensor_number = sensor_number_item.text()
            
            # Open historical data window
            self.historical_window = HistoricalDataWindow(room_name, sensor_number, self.api_url)
            self.historical_window.show()


class HistoricalDataWindow(QMainWindow):
    def __init__(self, room_name, sensor_number, api_url):
        super().__init__()
        self.room_name = room_name
        self.sensor_number = sensor_number
        self.api_url = api_url
        self.init_ui()
        self.load_historical_data()
        
    def init_ui(self):
        """Initialize the historical data window UI"""
        self.setWindowTitle(f"Historical Data - {self.room_name}/{self.sensor_number}")
        self.setGeometry(150, 150, 1600, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title label
        title_label = QLabel(f"Historical Data for {self.room_name} - {self.sensor_number}")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        # Date range controls
        date_label = QLabel("Date Range:")
        control_layout.addWidget(date_label)
        
        start_date_label = QLabel("Start:")
        control_layout.addWidget(start_date_label)
        
        # Set default to one week ago
        default_start_date = QDate.currentDate().addDays(-7)
        self.start_date_edit = QDateEdit(default_start_date)
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setMaximumWidth(120)
        self.start_date_edit.dateChanged.connect(self.on_date_range_changed)
        control_layout.addWidget(self.start_date_edit)
        
        end_date_label = QLabel("End:")
        control_layout.addWidget(end_date_label)
        
        # Set default to today
        default_end_date = QDate.currentDate()
        self.end_date_edit = QDateEdit(default_end_date)
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setMaximumWidth(120)
        self.end_date_edit.dateChanged.connect(self.on_date_range_changed)
        control_layout.addWidget(self.end_date_edit)
        
        # Add some spacing
        control_layout.addWidget(QLabel("  "))
        
        # CSV Export buttons
        export_selected_button = QPushButton("Export Selected Data")
        export_selected_button.clicked.connect(self.export_selected_data)
        export_selected_button.setMaximumWidth(150)
        control_layout.addWidget(export_selected_button)
        
        export_all_button = QPushButton("Export All Data")
        export_all_button.clicked.connect(self.export_all_data)
        export_all_button.setMaximumWidth(150)
        control_layout.addWidget(export_all_button)
        
        # PM Size checkboxes
        pm_label = QLabel("PM Sizes to Graph (ft³):")
        control_layout.addWidget(pm_label)
        
        # Create checkbox layout
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout()
        checkbox_widget.setLayout(checkbox_layout)
        
        # Create checkboxes for each PM size
        self.pm_checkboxes = {}
        pm_sizes = [("PM0.5", "num_pm0_5_ft3", True), 
                    ("PM1", "num_pm1_ft3", True), 
                    ("PM2.5", "num_pm2_5_ft3", True), 
                    ("PM4", "num_pm4_ft3", True), 
                    ("PM10", "num_pm10_ft3", True)]
        
        for display_name, data_key, default_checked in pm_sizes:
            checkbox = QCheckBox(display_name)
            checkbox.setChecked(default_checked)
            checkbox.stateChanged.connect(self.update_graph)
            self.pm_checkboxes[data_key] = checkbox
            checkbox_layout.addWidget(checkbox)
        
        control_layout.addWidget(checkbox_widget)
        
        control_layout.addStretch()
        main_layout.addLayout(control_layout)
        
        # Create horizontal splitter for table and graph
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left side - Historical data table
        table_widget = QWidget()
        table_layout = QVBoxLayout()
        table_widget.setLayout(table_layout)
        
        table_label = QLabel("Historical Data Table")
        table_label.setAlignment(Qt.AlignCenter)
        table_label.setStyleSheet("font-weight: bold; margin: 5px;")
        table_layout.addWidget(table_label)
        
        self.hist_table = QTableWidget()
        
        # Define columns for historical data (excluding room_name and sensor_number)
        self.hist_columns = [
            "Timestamp", "ISO Timestamp",
            "PM1 Mass", "PM2.5 Mass", "PM4 Mass", "PM10 Mass",
            "PM0.5 Count", "PM1 Count", "PM2.5 Count", "PM4 Count", "PM10 Count",
            "Particle Size (μm)",
            "PM0.5 (ft³)", "PM1 (ft³)", "PM2.5 (ft³)", "PM4 (ft³)", "PM10 (ft³)",
            "Bin 0.3-0.5", "Bin 0.5-1.0", "Bin 1.0-2.5", "Bin 2.5-4.0", "Bin 4.0-10",
            "PM1 (μg/m³)", "PM2.5 (μg/m³)", "PM4 (μg/m³)", "PM10 (μg/m³)"
        ]
        
        self.hist_table.setColumnCount(len(self.hist_columns))
        self.hist_table.setHorizontalHeaderLabels(self.hist_columns)
        self.hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.hist_table.horizontalHeader().setStretchLastSection(False)
        self.hist_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.hist_table.setAlternatingRowColors(True)
        self.hist_table.setSortingEnabled(True)
        
        table_layout.addWidget(self.hist_table)
        splitter.addWidget(table_widget)
        
        # Right side - Graph
        graph_widget = QWidget()
        graph_layout = QVBoxLayout()
        graph_widget.setLayout(graph_layout)
        
        graph_label = QLabel("Historical Data Graph")
        graph_label.setAlignment(Qt.AlignCenter)
        graph_label.setStyleSheet("font-weight: bold; margin: 5px;")
        graph_layout.addWidget(graph_label)
        
        # Create matplotlib figure and canvas
        self.figure = Figure(figsize=(8, 6), dpi=80)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        # Add navigation toolbar for zoom, pan, and reset functionality
        self.toolbar = NavigationToolbar(self.canvas, graph_widget)
        self.toolbar.setStyleSheet("QToolBar QToolButton { background-color: white; }")
        
        graph_layout.addWidget(self.toolbar)
        graph_layout.addWidget(self.canvas)
        
        splitter.addWidget(graph_widget)
        
        # Set initial splitter sizes (50/50 split)
        splitter.setSizes([800, 800])
        
        # Store historical data for graphing
        self.historical_data = []  # All data from API
        self.filtered_data = []    # Filtered data based on date range
        
    def on_date_range_changed(self):
        """Handle date range changes"""
        self.filter_data_by_date_range()
        self.populate_historical_table(self.filtered_data)
        self.update_graph()
    
    def filter_data_by_date_range(self):
        """Filter historical data based on selected date range"""
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        
        # Add one day to end_date to include the entire end day
        end_date = end_date + timedelta(days=1)
        
        self.filtered_data = []
        
        for record in self.historical_data:
            # Extract timestamp from record
            record_datetime = self.extract_timestamp_from_record(record)
            
            if record_datetime:
                record_date = record_datetime.date()
                if start_date <= record_date < end_date:
                    self.filtered_data.append(record)
    
    def extract_timestamp_from_record(self, record):
        """Extract datetime object from a record"""
        timestamp_value = None
        
        # Check for standard timestamp formats first
        if "timestamp_iso" in record:
            timestamp_value = record["timestamp_iso"]
        elif "timestamp" in record:
            timestamp_value = record["timestamp"]
        else:
            # Look for timestamp in raw data
            for key, value in record.items():
                if isinstance(value, str) and 'T' in value and ':' in value:
                    timestamp_value = value
                    break
                elif isinstance(key, str) and 'T' in key and ':' in key:
                    timestamp_value = key
                    break
            
            # If still no timestamp, try Unix timestamp
            if not timestamp_value:
                for key, value in record.items():
                    if isinstance(key, str) and key.replace('.', '').isdigit() and len(key) >= 10:
                        try:
                            timestamp_value = float(key)
                            break
                        except:
                            pass
                    elif isinstance(value, (int, float, str)) and str(value).replace('.', '').isdigit() and len(str(value)) >= 10:
                        try:
                            timestamp_value = float(value)
                            break
                        except:
                            pass
        
        if timestamp_value is not None:
            try:
                if isinstance(timestamp_value, str):
                    # Try ISO format
                    if 'T' in timestamp_value:
                        return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                    else:
                        # Try to parse as Unix timestamp string
                        return datetime.fromtimestamp(float(timestamp_value))
                else:
                    # Numeric timestamp
                    return datetime.fromtimestamp(float(timestamp_value))
            except (ValueError, TypeError, OSError):
                pass
        
        return None
    
    def load_historical_data(self):
        """Load historical data from the API"""
        try:
            # Make request for historical data
            url = f"{self.api_url}?room_name={self.room_name}&sensor_number={self.sensor_number}"
            response = requests.get(url, verify=False, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if data.get("status") == "success" and "historical_data" in data:
                self.historical_data = data["historical_data"]
            elif "historical_data" in data:  # Handle response without status field
                self.historical_data = data["historical_data"]
            else:
                QMessageBox.warning(self, "No Data", 
                                   f"No historical data found for {self.room_name}/{self.sensor_number}")
                return
            
            # Filter data and update displays
            self.filter_data_by_date_range()
            self.populate_historical_table(self.filtered_data)
            self.update_graph()
                
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Connection Error", 
                               "Could not connect to server. Make sure the server is running.")
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Request Error", f"Error fetching historical data: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
            
    def populate_historical_table(self, historical_data):
        """Populate the historical data table"""
        self.hist_table.setRowCount(0)  # Clear existing data
        
        for record in historical_data:
            row_position = self.hist_table.rowCount()
            self.hist_table.insertRow(row_position)
            
            # Check for standard data structure first
            if any(key in record for key in ['timestamp', 'timestamp_iso', 'num_pm0_5_ft3', 'mass_pm1']):
                # Standard structured format
                columns_data = [
                    record.get("timestamp", "N/A"),
                    record.get("timestamp_iso", "N/A"),
                    record.get("mass_pm1", "N/A"),
                    record.get("mass_pm2_5", "N/A"),
                    record.get("mass_pm4", "N/A"),
                    record.get("mass_pm10", "N/A"),
                    record.get("num_pm0_5", "N/A"),
                    record.get("num_pm1", "N/A"),
                    record.get("num_pm2_5", "N/A"),
                    record.get("num_pm4", "N/A"),
                    record.get("num_pm10", "N/A"),
                    record.get("typical_particle_size_um", "N/A"),
                    record.get("num_pm0_5_ft3", "N/A"),
                    record.get("num_pm1_ft3", "N/A"),
                    record.get("num_pm2_5_ft3", "N/A"),
                    record.get("num_pm4_ft3", "N/A"),
                    record.get("num_pm10_ft3", "N/A"),
                    record.get("bin_0_3_to_0_5", "N/A"),
                    record.get("bin_0_5_to_1_0", "N/A"),
                    record.get("bin_1_0_to_2_5", "N/A"),
                    record.get("bin_2_5_to_4_0", "N/A"),
                    record.get("bin_4_0_to_10", "N/A"),
                    record.get("mass_pm1_ug_m3", "N/A"),
                    record.get("mass_pm2_5_ug_m3", "N/A"),
                    record.get("mass_pm4_ug_m3", "N/A"),
                    record.get("mass_pm10_ug_m3", "N/A")
                ]
            else:
                # Raw CSV format - keys are timestamps and particle sizes
                # Try to extract timestamp information
                timestamp_unix = None
                timestamp_iso = None
                
                # Look for timestamp patterns in keys
                for key in record.keys():
                    if isinstance(key, str):
                        # Look for ISO timestamp format in keys
                        if 'T' in key and (':' in key or '-' in key) and len(key) > 15:
                            timestamp_iso = key
                        # Look for Unix timestamp (numeric string)
                        elif key.replace('.', '').isdigit() and len(key) >= 10:
                            try:
                                # Validate it's a reasonable Unix timestamp
                                ts = float(key)
                                if ts > 1000000000:  # After 2001
                                    timestamp_unix = key
                            except:
                                pass
                
                # Look for timestamp patterns in values if not found in keys
                if not timestamp_unix and not timestamp_iso:
                    for key, value in record.items():
                        if isinstance(value, str):
                            if 'T' in value and (':' in value or '-' in value) and len(value) > 15:
                                timestamp_iso = value
                            elif value.replace('.', '').isdigit() and len(value) >= 10:
                                try:
                                    ts = float(value)
                                    if ts > 1000000000:
                                        timestamp_unix = value
                                except:
                                    pass
                
                columns_data = [
                    timestamp_unix if timestamp_unix else "N/A",
                    timestamp_iso if timestamp_iso else "N/A"
                ]
                
                # Add particle measurement data
                # Look for numeric keys that might represent particle measurements
                particle_measurements = {}
                for key, value in record.items():
                    try:
                        # Skip timestamp keys we already processed
                        if key == timestamp_unix or key == timestamp_iso:
                            continue
                        # Skip non-numeric keys that are identifiers
                        if key in ['room_name', 'sensor_number']:
                            continue
                        
                        # Try to parse key as particle size
                        if isinstance(key, str) and key.replace('.', '').isdigit():
                            size = float(key)
                            if 0.1 <= size <= 50.0:  # Reasonable particle size range in micrometers
                                particle_measurements[size] = value
                    except (ValueError, TypeError):
                        continue
                
                # Sort particle measurements by size
                sorted_measurements = sorted(particle_measurements.items())
                
                # Fill in columns based on available data
                # For now, put the particle size data in the remaining columns
                remaining_cols = len(self.hist_columns) - 2  # Subtract timestamp columns
                for i in range(remaining_cols):
                    if i < len(sorted_measurements):
                        size, value = sorted_measurements[i]
                        columns_data.append(f"{size}μm: {value}")
                    else:
                        columns_data.append("N/A")
            
            # Set items in the table
            for col, value in enumerate(columns_data):
                if col >= len(self.hist_columns):
                    break
                    
                if value is None:
                    value = "N/A"
                elif isinstance(value, float):
                    value = f"{value:.6f}"
                self.hist_table.setItem(row_position, col, QTableWidgetItem(str(value)))
        
        # Sort by timestamp (most recent first) if we have timestamp data
        if self.hist_table.rowCount() > 0:
            try:
                self.hist_table.sortItems(0, Qt.DescendingOrder)
            except:
                # If sorting fails, that's okay
                pass
    
    def update_graph(self):
        """Update the graph based on selected PM sizes"""
        if not self.filtered_data:
            # Clear the plot if no data
            self.ax.clear()
            self.ax.set_title("No Data Available for Selected Date Range")
            self.ax.set_xlabel("Time")
            self.ax.set_ylabel("Particle Count (ft³)")
            self.canvas.draw()
            return
        
        # Get checked PM sizes
        checked_params = []
        for data_key, checkbox in self.pm_checkboxes.items():
            if checkbox.isChecked():
                checked_params.append(data_key)
        
        if not checked_params:
            # Clear the plot if no parameters selected
            self.ax.clear()
            self.ax.set_title("No PM Sizes Selected")
            self.ax.set_xlabel("Time")
            self.ax.set_ylabel("Particle Count (ft³)")
            self.canvas.draw()
            return
        
        # Fixed color mapping for each PM size to maintain consistency
        color_map = {
            "num_pm0_5_ft3": 'blue',
            "num_pm1_ft3": 'red', 
            "num_pm2_5_ft3": 'green',
            "num_pm4_ft3": 'orange',
            "num_pm10_ft3": 'purple'
        }
        
        # Clear the plot
        self.ax.clear()
        
        # Process each checked parameter
        legend_labels = []
        for data_key in checked_params:
            timestamps = []
            values = []
            
            for record in self.filtered_data:
                # Try to extract timestamp
                timestamp_value = None
                
                # Check for standard timestamp formats first
                if "timestamp_iso" in record:
                    timestamp_value = record["timestamp_iso"]
                elif "timestamp" in record:
                    timestamp_value = record["timestamp"]
                else:
                    # Look for timestamp in raw data
                    for key, value in record.items():
                        if isinstance(value, str) and 'T' in value and ':' in value:
                            timestamp_value = value
                            break
                        elif isinstance(key, str) and 'T' in key and ':' in key:
                            timestamp_value = key
                            break
                    
                    # If still no timestamp, try Unix timestamp
                    if not timestamp_value:
                        for key, value in record.items():
                            if isinstance(key, str) and key.replace('.', '').isdigit() and len(key) >= 10:
                                try:
                                    timestamp_value = float(key)
                                    break
                                except:
                                    pass
                            elif isinstance(value, (int, float, str)) and str(value).replace('.', '').isdigit() and len(str(value)) >= 10:
                                try:
                                    timestamp_value = float(value)
                                    break
                                except:
                                    pass
                
                # Try to extract value for the current parameter
                param_value = None
                
                if data_key in record:
                    param_value = record[data_key]
                
                # Process timestamp and add to data if we have both timestamp and value
                if timestamp_value is not None and param_value is not None:
                    try:
                        if isinstance(timestamp_value, str):
                            # Try ISO format
                            if 'T' in timestamp_value:
                                dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                            else:
                                # Try to parse as Unix timestamp string
                                dt = datetime.fromtimestamp(float(timestamp_value))
                        else:
                            # Numeric timestamp
                            dt = datetime.fromtimestamp(float(timestamp_value))
                        
                        # Convert to Mountain Time
                        dt_mountain = convert_to_mountain(dt)
                        timestamps.append(dt_mountain)
                        values.append(float(param_value))
                    except (ValueError, TypeError, OSError):
                        continue
            
            # Plot this parameter if we have data
            if timestamps and values:
                # Sort by timestamp
                sorted_data = sorted(zip(timestamps, values))
                timestamps, values = zip(*sorted_data)
                
                # Get display name for legend
                display_name = {
                    "num_pm0_5_ft3": "PM0.5",
                    "num_pm1_ft3": "PM1", 
                    "num_pm2_5_ft3": "PM2.5",
                    "num_pm4_ft3": "PM4",
                    "num_pm10_ft3": "PM10"
                }.get(data_key, data_key)
                
                # Plot line
                color = color_map[data_key]
                self.ax.plot(timestamps, values, color=color, linewidth=2, marker='o', 
                           markersize=3, label=display_name, alpha=0.8)
                legend_labels.append(display_name)
        
        # Set title and labels
        self.ax.set_title("PM Particle Concentrations Over Time")
        self.ax.set_xlabel("Time (Mountain Time)")
        self.ax.set_ylabel("Particle Count (ft³)")
        self.ax.grid(True, alpha=0.3)
        
        # Add legend if we have data
        if legend_labels:
            self.ax.legend(loc='upper right')
        
        # Format x-axis
        self.figure.autofmt_xdate()
        
        # Adjust layout and refresh
        self.figure.tight_layout()
        self.canvas.draw()
    
    def export_selected_data(self):
        """Export currently filtered/displayed data to CSV"""
        if not self.filtered_data:
            QMessageBox.information(self, "No Data", "No data available to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Selected Data", 
            f"particle_data_{self.room_name}_{self.sensor_number}_selected.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            self._export_to_csv(self.filtered_data, file_path)
    
    def export_all_data(self):
        """Export all historical data to CSV"""
        if not self.historical_data:
            QMessageBox.information(self, "No Data", "No data available to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export All Data", 
            f"particle_data_{self.room_name}_{self.sensor_number}_all.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            self._export_to_csv(self.historical_data, file_path)
    
    def _export_to_csv(self, data, file_path):
        """Helper method to write data to CSV file"""
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(self.hist_columns)
                
                # Write data rows
                for record in data:
                    row_data = []
                    
                    # Check for standard data structure first
                    if any(key in record for key in ['timestamp', 'timestamp_iso', 'num_pm0_5_ft3', 'mass_pm1']):
                        # Standard structured format
                        columns_data = [
                            record.get("timestamp", ""),
                            record.get("timestamp_iso", ""),
                            record.get("mass_pm1", ""),
                            record.get("mass_pm2_5", ""),
                            record.get("mass_pm4", ""),
                            record.get("mass_pm10", ""),
                            record.get("num_pm0_5", ""),
                            record.get("num_pm1", ""),
                            record.get("num_pm2_5", ""),
                            record.get("num_pm4", ""),
                            record.get("num_pm10", ""),
                            record.get("typical_particle_size_um", ""),
                            record.get("num_pm0_5_ft3", ""),
                            record.get("num_pm1_ft3", ""),
                            record.get("num_pm2_5_ft3", ""),
                            record.get("num_pm4_ft3", ""),
                            record.get("num_pm10_ft3", ""),
                            record.get("bin_0_3_to_0_5", ""),
                            record.get("bin_0_5_to_1_0", ""),
                            record.get("bin_1_0_to_2_5", ""),
                            record.get("bin_2_5_to_4_0", ""),
                            record.get("bin_4_0_to_10", ""),
                            record.get("mass_pm1_ug_m3", ""),
                            record.get("mass_pm2_5_ug_m3", ""),
                            record.get("mass_pm4_ug_m3", ""),
                            record.get("mass_pm10_ug_m3", "")
                        ]
                    else:
                        # Raw CSV format handling
                        timestamp_unix = None
                        timestamp_iso = None
                        
                        # Look for timestamp patterns
                        for key in record.keys():
                            if isinstance(key, str):
                                if 'T' in key and (':' in key or '-' in key) and len(key) > 15:
                                    timestamp_iso = key
                                elif key.replace('.', '').isdigit() and len(key) >= 10:
                                    try:
                                        ts = float(key)
                                        if ts > 1000000000:
                                            timestamp_unix = key
                                    except:
                                        pass
                        
                        columns_data = [timestamp_unix or "", timestamp_iso or ""]
                        
                        # Add particle data
                        particle_measurements = {}
                        for key, value in record.items():
                            try:
                                if key == timestamp_unix or key == timestamp_iso:
                                    continue
                                if key in ['room_name', 'sensor_number']:
                                    continue
                                if isinstance(key, str) and key.replace('.', '').isdigit():
                                    size = float(key)
                                    if 0.1 <= size <= 50.0:
                                        particle_measurements[size] = value
                            except (ValueError, TypeError):
                                continue
                        
                        sorted_measurements = sorted(particle_measurements.items())
                        remaining_cols = len(self.hist_columns) - 2
                        for i in range(remaining_cols):
                            if i < len(sorted_measurements):
                                size, value = sorted_measurements[i]
                                columns_data.append(f"{size}μm: {value}")
                            else:
                                columns_data.append("")
                    
                    # Clean the data for CSV
                    clean_row = []
                    for value in columns_data:
                        if value is None or value == "N/A":
                            clean_row.append("")
                        else:
                            clean_row.append(str(value))
                    
                    writer.writerow(clean_row)
            
            QMessageBox.information(self, "Export Complete", f"Data exported successfully to:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting data to CSV:\n{str(e)}")


def main():
    app = QApplication(sys.argv)
    viewer = ParticleDataViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()