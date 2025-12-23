"""
ParticleSensor Core Module
Contains data processing and API interface functionality for particle sensor data.
"""

import requests
import json
from datetime import datetime
import warnings

# Disable SSL warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


class ParticleDataAPI:
    """Handle API communication for particle sensor data"""
    
    def __init__(self, api_url="https://nfhistory.nanofab.utah.edu/particle-data"):
        self.api_url = api_url
    
    def fetch_current_data(self, timeout=5):
        """Fetch current particle data from the API"""
        try:
            response = requests.get(self.api_url, verify=False, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching current data: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("Invalid JSON response from server")
    
    def fetch_historical_data(self, room_name, sensor_number, timeout=10):
        """Fetch historical data for a specific sensor"""
        try:
            url = f"{self.api_url}?room_name={room_name}&sensor_number={sensor_number}"
            response = requests.get(url, verify=False, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching historical data: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("Invalid JSON response from server")


class ParticleDataProcessor:
    """Process and format particle sensor data"""
    
    @staticmethod
    def format_timestamp(timestamp):
        """Format timestamp for display"""
        if not timestamp:
            return "N/A"
            
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                dt = datetime.fromtimestamp(timestamp)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(timestamp)
    
    @staticmethod
    def extract_particle_measurements(data):
        """Extract particle measurement data from API response"""
        measurements = []
        
        # Handle the API response structure
        if isinstance(data, dict) and "sensors" in data:
            data_list = data["sensors"]
        elif isinstance(data, list):
            data_list = data
        else:
            data_list = [data]
            
        for record in data_list:
            if not isinstance(record, dict):
                continue
                
            measurement = {
                'room_name': record.get("room_name", "N/A"),
                'sensor_number': record.get("sensor_number", "N/A"),
                'timestamp': ParticleDataProcessor.format_timestamp(record.get("timestamp")),
                'converted_values': record.get("converted_values", {})
            }
            measurements.append(measurement)
            
        return measurements
    
    @staticmethod
    def extract_historical_measurements(data):
        """Extract historical measurement data"""
        if data.get("status") == "success" and "historical_data" in data:
            return data["historical_data"]
        elif "historical_data" in data:
            return data["historical_data"]
        else:
            return []
    
    @staticmethod
    def get_particle_concentration_ft3(converted_values, particle_size):
        """Get particle concentration in ft³ for specified particle size"""
        num_conc = converted_values.get("number_concentrations_ft3", {})
        return num_conc.get(particle_size, "N/A")
    
    @staticmethod
    def parse_historical_record(record):
        """Parse a historical data record and extract meaningful values"""
        parsed = {
            'timestamp_unix': None,
            'timestamp_iso': None,
            'measurements': {}
        }
        
        # Extract timestamp information
        for key, value in record.items():
            if isinstance(key, str):
                # Look for ISO timestamp format
                if 'T' in key and (':' in key or '-' in key):
                    parsed['timestamp_iso'] = key
                # Look for Unix timestamp (numeric string)
                elif key.replace('.', '').isdigit() and len(key) >= 10:
                    parsed['timestamp_unix'] = key
                    
        # Check values for timestamp patterns
        for key, value in record.items():
            if isinstance(value, str):
                if 'T' in value and (':' in value or '-' in value):
                    parsed['timestamp_iso'] = value
                elif str(value).replace('.', '').isdigit() and len(str(value)) >= 10:
                    parsed['timestamp_unix'] = value
        
        # Extract measurement data
        if 'timestamp' in record:
            # Standard format
            parsed['measurements'] = {
                'mass_pm1': record.get("mass_pm1"),
                'mass_pm2_5': record.get("mass_pm2_5"),
                'mass_pm4': record.get("mass_pm4"),
                'mass_pm10': record.get("mass_pm10"),
                'num_pm0_5': record.get("num_pm0_5"),
                'num_pm1': record.get("num_pm1"),
                'num_pm2_5': record.get("num_pm2_5"),
                'num_pm4': record.get("num_pm4"),
                'num_pm10': record.get("num_pm10"),
                'mass_pm1_ug_m3': record.get("mass_pm1_ug_m3"),
                'mass_pm2_5_ug_m3': record.get("mass_pm2_5_ug_m3"),
                'mass_pm4_ug_m3': record.get("mass_pm4_ug_m3"),
                'mass_pm10_ug_m3': record.get("mass_pm10_ug_m3")
            }
        else:
            # Raw particle size data format
            particle_measurements = {}
            for key, value in record.items():
                try:
                    if isinstance(key, str) and key.replace('.', '').isdigit():
                        size = float(key)
                        if 0.1 <= size <= 50.0:  # Reasonable particle size range in micrometers
                            particle_measurements[size] = value
                except (ValueError, TypeError):
                    continue
            parsed['measurements'] = particle_measurements
        
        return parsed


class ParticleSensor:
    """Main particle sensor class that combines API and processing functionality"""
    
    def __init__(self, api_url="https://nfhistory.nanofab.utah.edu/particle-data"):
        self.api = ParticleDataAPI(api_url)
        self.processor = ParticleDataProcessor()
    
    def get_current_measurements(self):
        """Get current particle measurements"""
        try:
            data = self.api.fetch_current_data()
            return self.processor.extract_particle_measurements(data)
        except Exception as e:
            raise Exception(f"Failed to get current measurements: {str(e)}")
    
    def get_historical_measurements(self, room_name, sensor_number):
        """Get historical measurements for a specific sensor"""
        try:
            data = self.api.fetch_historical_data(room_name, sensor_number)
            return self.processor.extract_historical_measurements(data)
        except Exception as e:
            raise Exception(f"Failed to get historical measurements: {str(e)}")
    
    def get_sensor_list(self):
        """Get list of available sensors"""
        try:
            measurements = self.get_current_measurements()
            sensors = []
            for measurement in measurements:
                sensor_info = {
                    'room_name': measurement['room_name'],
                    'sensor_number': measurement['sensor_number']
                }
                if sensor_info not in sensors:
                    sensors.append(sensor_info)
            return sensors
        except Exception as e:
            raise Exception(f"Failed to get sensor list: {str(e)}")