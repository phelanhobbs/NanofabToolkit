import sys
from auth import HSCCode, BaseURL, StartDayAppend, EndDayAppend
import requests
import os

def daysinMonth(months, yr):
    """
    Convert month number to day-month format.
    
    Args:
        months (int): Month number (1-12)
        yr (int): uses the year to determine if leap year or not
        
    Returns:
        int days: Number of days in the month
    """
    # Check for leap year
    leapyear = False
    if (yr % 4 == 0 and yr % 100 != 0) or (yr % 400 == 0):
        leapyear = True
    #determine number of days in month
    if months in [1, 3, 5, 7, 8, 10, 12]:
        days = 31
    elif months in [4, 6, 9, 11]:
        days = 30
    elif months == 2:
        days = 29 if leapyear else 28
    else:
        raise ValueError("Invalid month number. Must be between 1 and 12.")
    
    return days
 

def download_Metal(endpoint, month, year):
    """
    Download data from the specified endpoint and save as CSV.
    
    Args:
        endpoint (int or str): The endpoint to append to the BaseURL, or "all" to download all
        month (int): Month number (1-12)
        year (int): Year (e.g., 2025)
        
    Returns:
        str: Path to the saved file or None if download failed
    """
    startDay = 1
    endDay = daysinMonth(month, year)
    
    # Determine the base directory for downloads
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as compiled executable
        base_dir = os.path.dirname(sys.executable)
        download_dir = os.path.join(base_dir, 'downloads')
        print(f"Executable mode: Download directory is {download_dir}")
    else:
        # Running in a normal Python environment
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(current_file)
        precious_metal_dir = os.path.dirname(src_dir)
        project_dir = os.path.dirname(precious_metal_dir)
        download_dir = os.path.join(project_dir, 'downloads')
        print(f"Development mode: Download directory is {download_dir}")
    
    os.makedirs(download_dir, exist_ok=True)
    print(f"Ensured download directory exists at {download_dir}")
    
    # Special case for "all" - download all endpoints and combine results
    if endpoint == "all":
        # List of all endpoints to download
        endpoints = [768, 808, 809, 810, 811, 812, 813, 814]
        all_data = []
        combined_metadata = {}
        
        # First download each endpoint and collect data
        for ep in endpoints:
            try:
                print(f"Requesting data for endpoint {ep}...")
                header = {'Authorization': HSCCode}
                
                constructedURL = f"{BaseURL}{ep}{StartDayAppend}{year}-{month:02d}-{startDay:02d}{EndDayAppend}{year}-{month:02d}-{endDay:02d}"
                print(f"Requesting URL: {constructedURL}")
                
                response = requests.get(constructedURL, headers=header)
                print(f"Response status code: {response.status_code}")
                
                if response.status_code == 200:
                    # Get JSON data
                    json_data = response.json()
                    
                    # Skip if no data
                    if not json_data or len(json_data) == 0:
                        print(f"No data available for endpoint {ep}")
                        continue
                    
                    # Determine machine and metal for this endpoint
                    machine = None
                    metal = None
                    
                    if ep == 768:
                        machine = "Denton635"
                        metal = "Gold"
                    elif ep >= 808 and ep <= 810:
                        machine = "Denton635"
                        if ep == 808:
                            metal = "Iridium"
                        elif ep == 809:
                            metal = "Palladium"
                        elif ep == 810:
                            metal = "Platinum"
                    elif ep >= 811 and ep <= 814:
                        machine = "Denton18"
                        if ep == 811:
                            metal = "Gold"
                        elif ep == 812:
                            metal = "Iridium"
                        elif ep == 813:
                            metal = "Palladium"
                        elif ep == 814:
                            metal = "Platinum"
                    
                    # Add machine and metal fields to each record
                    for record in json_data:
                        record['Machine'] = machine
                        record['Metal'] = metal
                        all_data.append(record)
                    
                    # Add metadata about this endpoint
                    combined_metadata[ep] = {
                        'machine': machine,
                        'metal': metal,
                        'record_count': len(json_data)
                    }
                    
                else:
                    print(f"Download failed for endpoint {ep} with status code: {response.status_code}")
            
            except Exception as e:
                print(f"Error downloading data for endpoint {ep}: {e}")
        
        # Create combined filenames
        base_filename = f"all_metals_{month}_{year}"
        
        # Save combined metadata as JSON
        metadata_filepath = os.path.join(download_dir, f"{base_filename}_metadata.json")
        with open(metadata_filepath, 'w') as f:
            import json
            metadata = {
                'month': month,
                'year': year,
                'endpoints': combined_metadata,
                'total_records': len(all_data)
            }
            json.dump(metadata, f, indent=2)
        print(f"Saved metadata to {metadata_filepath}")
        
        # Save all the data as one combined CSV
        csv_filepath = os.path.join(download_dir, f"{base_filename}.csv")
        
        if all_data:
            with open(csv_filepath, 'w', newline='') as f:
                import csv
                # Get all possible field names from all records
                fieldnames = set()
                for record in all_data:
                    fieldnames.update(record.keys())
                
                # Convert to sorted list for consistent column order
                fieldnames = sorted(list(fieldnames))
                
                # Ensure Machine and Metal are first columns for easy reading
                if 'Machine' in fieldnames:
                    fieldnames.remove('Machine')
                if 'Metal' in fieldnames:
                    fieldnames.remove('Metal')
                
                # Reorder columns to put Machine and Metal first
                fieldnames = ['Machine', 'Metal'] + fieldnames
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for record in all_data:
                    writer.writerow(record)
            
            print(f"Saved combined CSV data to {csv_filepath}")
            
            # Verify the file was created
            if os.path.exists(csv_filepath):
                print(f"Combined CSV file exists at {csv_filepath}")
                return csv_filepath
            else:
                print(f"ERROR: Combined CSV file was not created at {csv_filepath}")
                return None
        else:
            print("No data found for any endpoints.")
            return None
    
    # Regular single endpoint download (original functionality)
    else:
        try:
            header = {'Authorization': HSCCode}
            
            constructedURL = f"{BaseURL}{endpoint}{StartDayAppend}{year}-{month:02d}-{startDay:02d}{EndDayAppend}{year}-{month:02d}-{endDay:02d}"
            print(f"Requesting URL: {constructedURL}")
            
            response = requests.get(constructedURL, headers=header)
            print(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                # Determine base filename
                machine = None
                metal = None
                
                # Determine machine first
                if endpoint == 768:
                    machine = "Denton635"
                    metal = "gold"
                elif endpoint >= 808 and endpoint <= 810:
                    machine = "Denton635"
                    if endpoint == 808:
                        metal = "Iridium"
                    elif endpoint == 809:
                        metal = "Palladium"
                    elif endpoint == 810:
                        metal = "Platinum"
                elif endpoint >= 811 and endpoint <= 814:
                    machine = "Denton18"
                    if endpoint == 811:
                        metal = "Gold"
                    elif endpoint == 812:
                        metal = "Iridium"
                    elif endpoint == 813:
                        metal = "Palladium"
                    elif endpoint == 814:
                        metal = "Platinum"
                
                # Base filename
                base_filename = f"{machine}_{metal}_{month}_{year}"
                
                # Get JSON data
                json_data = response.json()
                
                # Save as JSON (preserve original data)
                json_filepath = os.path.join(download_dir, f"{base_filename}.json")
                with open(json_filepath, 'w') as f:
                    import json
                    json.dump(json_data, f, indent=2)
                
                print(f"Saved JSON data to {json_filepath}")
                
                # Convert to CSV
                csv_filepath = os.path.join(download_dir, f"{base_filename}.csv")
                with open(csv_filepath, 'w', newline='') as f:
                    import csv
                    if json_data and len(json_data) > 0:
                        # Get field names from the first record
                        fieldnames = json_data[0].keys()
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for record in json_data:
                            writer.writerow(record)
                
                print(f"Saved CSV data to {csv_filepath}")
                
                # Verify the file was actually created
                if os.path.exists(csv_filepath):
                    print(f"CSV file exists at {csv_filepath}")
                    return csv_filepath
                else:
                    print(f"ERROR: CSV file was not created at {csv_filepath}")
                    return None
            else:
                print(f"Download failed with status code: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error downloading file: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
     
    if len(sys.argv) != 4:
        print("Usage: python RetrieveMonthsMetals.py <endpoint> <month> <year>")
        print("Example: python RetrieveMonthsMetals.py 768 5 2025")
        #sys.exit(1)
    
    try:
        endpoint = int(sys.argv[1])
        month = int(sys.argv[2])
        year = int(sys.argv[3])
        
        # Validate inputs
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        
       
        downloaded_file = download_Metal(endpoint, month, year)
        if downloaded_file:
            print(f"File downloaded successfully: {downloaded_file}")
        else:
            print("File download failed.")
    
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)