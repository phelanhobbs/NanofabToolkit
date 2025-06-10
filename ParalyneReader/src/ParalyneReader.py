import requests
import json

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
    else:
        raise Exception(f"Error fetching file list: {response.status_code} - {response.text}")
    
def download_file(filename):
    """Download a specific file from the Paralyne analog data directory."""
    response = requests.get(f"{base_url}/download/{filename}", verify=False)
    if response.status_code == 200:
        with open(filename, 'wb') as file:
            file.write(response.content)
        print(f"File '{filename}' downloaded successfully.")
    else:
        raise Exception(f"Error downloading file '{filename}': {response.status_code} - {response.text}")
    
list_files()
input_filename = input("Enter the filename to download: ")
if input_filename:
    try:
        download_file(input_filename)
    except Exception as e:
        print(e)


