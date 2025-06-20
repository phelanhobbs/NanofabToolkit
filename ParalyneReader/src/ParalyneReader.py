import requests
import json
import os

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings()

base_url = "https://nfhistory.nanofab.utah.edu/api/paralyne/analog"


def list_files():
    """List all files in the Paralyne analog data directory."""
    response = requests.get(f"{base_url}/list", verify=False)
    if response.status_code == 200:
        resp = response.json()
        print("Available files:")
        for file_info in resp['files']:
            print(f"- {file_info['filename']} (Size: {file_info['size']} bytes, Modified: {file_info['modified']})")
        return resp['files']
    else:
        raise Exception(f"Error fetching file list: {response.status_code} - {response.text}")
    
def download_file(filename):
    """Download a specific file from the Paralyne analog data directory."""
    response = requests.get(f"{base_url}/download/{filename}", verify=False)
    if response.status_code == 200:
        # Create ParalyneLogs directory if it doesn't exist
        logs_dir = "ParalyneLogs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        # Get the absolute path where the file will be saved in ParalyneLogs directory
        file_path = os.path.abspath(os.path.join(logs_dir, filename))
        
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"File '{filename}' downloaded successfully to {file_path}.")
        
        # Return the full path to the downloaded file
        return file_path
    else:
        raise Exception(f"Error downloading file '{filename}': {response.status_code} - {response.text}")
    

def return_selected(filename):
    """Return the selected file information."""
    response = requests.get(f"{base_url}/return/{filename}", verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error fetching file info for '{filename}': {response.status_code} - {response.text}")
    
###
# 
# for testing purposes, you can uncomment the following lines to run the script directly 
#list_files()
#input_filename = input("Enter the filename to download: ")
#if input_filename:
#    try:
#        download_file(input_filename)
#    except Exception as e:
#        print(e)

