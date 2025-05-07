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
        endpoint (int or str): The endpoint to append to the BaseURL
        month (int): Month number (1-12)
        year (int): Year (e.g., 2025)
        
    Returns:
        str: Path to the saved file or None if download failed
    """

    startDay = 1
    endDay = daysinMonth(month, year)
    
    try:
        header = {'Authorization': HSCCode}

        constructedURL = f"{BaseURL}{endpoint}{StartDayAppend}{year}-{month:02d}-{startDay:02d}{EndDayAppend}{year}-{month:02d}-{endDay:02d}"
        response = requests.get(constructedURL, headers=header)

        if response.status_code == 200:
            # Create directory if it doesn't exist
            os.makedirs('downloads', exist_ok=True)

            # Determine base filename
            # If endpoint is a string, all metals are downloaded
            if isinstance(endpoint, str):
                base_filename = f"all_{month}_{year}"
            else:

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
            json_filepath = os.path.join('downloads', f"{base_filename}.json")
            with open(json_filepath, 'w') as f:
                import json
                json.dump(json_data, f, indent=2)
            
            # Convert to CSV
            csv_filepath = os.path.join('downloads', f"{base_filename}.csv")
            with open(csv_filepath, 'w', newline='') as f:
                import csv
                if json_data and len(json_data) > 0:
                    # Get field names from the first record
                    fieldnames = json_data[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for record in json_data:
                        writer.writerow(record)
            
            return csv_filepath
        else:
            print(f"Download failed with status code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error downloading file: {e}")
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