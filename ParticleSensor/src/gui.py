#!/usr/bin/env python3
"""
Particle Data Viewer GUI
A simple GUI application to view particle sensor data from the API endpoint.
"""

import sys
import warnings
import requests
import json
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QFrame, QLabel, QMessageBox,
                             QHeaderView, QComboBox, QSplitter)
from PyQt5.QtCore import Qt

# Disable SSL warnings using warnings module
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


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
                        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        dt = datetime.fromtimestamp(timestamp)
                        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
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
        
        # Refresh button
        refresh_button = QPushButton("Refresh Historical Data")
        refresh_button.clicked.connect(self.load_historical_data)
        refresh_button.setMaximumWidth(200)
        control_layout.addWidget(refresh_button)
        
        # Graph parameter selection
        graph_label = QLabel("Graph Parameter:")
        control_layout.addWidget(graph_label)
        
        self.graph_param_combo = QComboBox()
        self.graph_param_combo.addItems([
            "PM1 Mass", "PM2.5 Mass", "PM4 Mass", "PM10 Mass",
            "PM0.5 Count", "PM1 Count", "PM2.5 Count", "PM4 Count", "PM10 Count",
            "PM0.5 (ft³)", "PM1 (ft³)", "PM2.5 (ft³)", "PM4 (ft³)", "PM10 (ft³)",
            "PM1 (μg/m³)", "PM2.5 (μg/m³)", "PM4 (μg/m³)", "PM10 (μg/m³)"
        ])
        self.graph_param_combo.setCurrentText("PM2.5 (μg/m³)")
        # Debug: Add a debug slot to verify signal connection
        def debug_combo_changed(text):
            print(f"DEBUG: Combo box changed to: {text}")
            self.update_graph()
        
        self.graph_param_combo.currentTextChanged.connect(debug_combo_changed)
        control_layout.addWidget(self.graph_param_combo)
        
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
        graph_layout.addWidget(self.canvas)
        
        splitter.addWidget(graph_widget)
        
        # Set initial splitter sizes (50/50 split)
        splitter.setSizes([800, 800])
        
        # Store historical data for graphing
        self.historical_data = []
        
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
                self.populate_historical_table(self.historical_data)
                self.update_graph()
            elif "historical_data" in data:  # Handle response without status field
                self.historical_data = data["historical_data"]
                self.populate_historical_table(self.historical_data)
                self.update_graph()
            else:
                QMessageBox.warning(self, "No Data", 
                                   f"No historical data found for {self.room_name}/{self.sensor_number}")
                
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
            
            # Try to extract timestamp information
            # Look for timestamp patterns in the data
            timestamp_unix = None
            timestamp_iso = None
            
            # Check for various timestamp formats in the record
            for key, value in record.items():
                if isinstance(key, str):
                    # Look for ISO timestamp format
                    if 'T' in key and (':' in key or '-' in key):
                        timestamp_iso = key
                    # Look for Unix timestamp (numeric string)
                    elif key.replace('.', '').isdigit() and len(key) >= 10:
                        timestamp_unix = key
                        
            # Also check values for timestamp patterns
            for key, value in record.items():
                if isinstance(value, str):
                    if 'T' in value and (':' in value or '-' in value):
                        timestamp_iso = value
                    elif str(value).replace('.', '').isdigit() and len(str(value)) >= 10:
                        timestamp_unix = value
            
            # Use standard column mapping if available, otherwise try to parse the raw data
            if 'timestamp' in record:
                # Standard format
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
                # Raw particle size data format - try to extract meaningful values
                # This is for CSV files with particle sizes as column headers
                columns_data = [
                    timestamp_unix if timestamp_unix else "N/A",
                    timestamp_iso if timestamp_iso else "N/A"
                ]
                
                # Add particle measurement data
                # Look for numeric keys that might represent particle measurements
                particle_measurements = {}
                for key, value in record.items():
                    try:
                        # Skip non-numeric keys that are identifiers
                        if key in ['room_name', 'sensor_number'] or isinstance(key, str) and not key.replace('.', '').isdigit():
                            if key not in ['room_name', 'sensor_number'] and 'T' not in key and len(key) > 10:
                                continue
                        
                        # Try to parse as float for particle size
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
        """Update the graph based on selected parameter"""
        try:
            print(f"DEBUG: update_graph() called")  # Debug line
            
            if not self.historical_data:
                print("DEBUG: No historical data available")  # Debug line
                return
                
            selected_param = self.graph_param_combo.currentText()
            print(f"DEBUG: Selected parameter: {selected_param}")  # Debug line
            
            # Map display names to data keys
            param_map = {
                "PM1 Mass": "mass_pm1",
                "PM2.5 Mass": "mass_pm2_5", 
                "PM4 Mass": "mass_pm4",
                "PM10 Mass": "mass_pm10",
                "PM0.5 Count": "num_pm0_5",
                "PM1 Count": "num_pm1",
                "PM2.5 Count": "num_pm2_5",
                "PM4 Count": "num_pm4",
                "PM10 Count": "num_pm10",
                "PM0.5 (ft³)": "num_pm0_5_ft3",
                "PM1 (ft³)": "num_pm1_ft3",
                "PM2.5 (ft³)": "num_pm2_5_ft3",
                "PM4 (ft³)": "num_pm4_ft3",
                "PM10 (ft³)": "num_pm10_ft3",
                "PM1 (μg/m³)": "mass_pm1_ug_m3",
                "PM2.5 (μg/m³)": "mass_pm2_5_ug_m3",
                "PM4 (μg/m³)": "mass_pm4_ug_m3",
                "PM10 (μg/m³)": "mass_pm10_ug_m3"
            }
            
            data_key = param_map.get(selected_param)
            print(f"DEBUG: Data key: {data_key}")  # Debug line
            
            # Extract timestamps and values
            timestamps = []
            values = []
            
            for record in self.historical_data:
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
                
                # Try to extract value for the selected parameter
                param_value = None
                
                if data_key and data_key in record:
                    param_value = record[data_key]
                else:
                    # For raw data format, try to find a reasonable value to plot
                    # For now, let's plot the first numeric particle measurement we can find
                    for key, value in record.items():
                        try:
                            if isinstance(key, str) and key.replace('.', '').isdigit():
                                size = float(key)
                                if 0.1 <= size <= 50.0:  # Reasonable particle size range
                                    param_value = float(value) if value is not None else None
                                    break
                        except (ValueError, TypeError):
                            continue
                
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
                            
                        timestamps.append(dt)
                        values.append(float(param_value))
                    except (ValueError, TypeError, OSError):
                        continue
            
            print(f"DEBUG: Found {len(timestamps)} data points")  # Debug line
            
            if not timestamps or not values:
                # Clear the plot if no data
                print("DEBUG: No valid data points found, clearing plot")  # Debug line
                self.ax.clear()
                self.ax.set_title(f"No Data Available for {selected_param}")
                self.ax.set_xlabel("Time")
                self.ax.set_ylabel(selected_param)
                self.canvas.draw()
                return
                
            # Sort by timestamp
            sorted_data = sorted(zip(timestamps, values))
            timestamps, values = zip(*sorted_data)
            
            # Clear and plot
            print("DEBUG: Updating plot with new data")  # Debug line
            self.ax.clear()
            self.ax.plot(timestamps, values, 'b-o', linewidth=2, markersize=4)
            self.ax.set_title(f"{selected_param} Over Time")
            self.ax.set_xlabel("Time")
            self.ax.set_ylabel(selected_param)
            self.ax.grid(True, alpha=0.3)
            
            # Format x-axis
            self.figure.autofmt_xdate()
            
            # Adjust layout and refresh
            self.figure.tight_layout()
            self.canvas.draw()
            print("DEBUG: Graph update completed successfully")  # Debug line
            
        except Exception as e:
            print(f"ERROR in update_graph: {str(e)}")  # Debug line
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Graph Update Error", f"Error updating graph: {str(e)}")


def main():
    app = QApplication(sys.argv)
    viewer = ParticleDataViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()