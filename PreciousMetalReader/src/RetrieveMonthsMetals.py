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
    Download a file from the specified endpoint.
    
    Args:
        endpoint (str): The endpoint to append to the BaseURL
        
    Returns:
        str: Path to the downloaded file or None if download failed
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

            # Use endpoint as filename
            filename = f"{machine}_{metal}_{month}_{year}.csv"
            filepath = os.path.join('downloads', filename)
            
            # Save the file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return filepath
        else:
            print(f"Download failed with status code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None

# Example usage for the specific endpoint "768"
if __name__ == "__main__":

    endpoint = 768 
    month = 4
    year = 2025
     
    if len(sys.argv) != 4:
        print("Usage: python RetrieveMonthsMetals.py <endpoint> <month> <year>")
        print("Example: python RetrieveMonthsMetals.py 768 5 2025")
        #sys.exit(1)
    
    try:
        #endpoint = int(sys.argv[1])
        #month = int(sys.argv[2])
        #year = int(sys.argv[3])
        
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