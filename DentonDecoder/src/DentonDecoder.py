import argparse
import csv
import struct
import os

def convertFile(filePath):
    """
    Converts a .dat file to a CSV file.
    Parameters:
    filePath (str): Path to the .dat file

    Returns:
    str: Path to the converted CSV file
    """
    # Open the .denton file in binary mode
    with open(filePath, 'rb') as f:
        data = f.read()

    # Create a new .csv file with the same name
    csvFilePath = filePath.replace('.dat', '.csv')
    decoded_values = []

    # Iterate through the data in 128 byte chunks
    i = 0
    while i < len(data):
        # Process the next 128 bytes
        chunk = data[i:i + 128]
        
        if len(chunk) >= 4:
            # Format of 0x08 0x00 0x?? 0x00 means next ?? bytes are chars
            if chunk[0] == 0x08 and chunk[1] == 0x00 and chunk[3] == 0x00:
                text_length = chunk[2]
                if 4 + text_length <= len(chunk):
                    text = chunk[4:4 + text_length].decode('ascii', errors='replace')
                    decoded_values.append(text)
            
            # Format of 0x05 0x00 means next 8 bytes are double
            elif chunk[0] == 0x05 and chunk[1] == 0x00 and len(chunk) >= 10:
                try:
                    # Extract the 8 bytes for the double value
                    double_bytes = chunk[2:10]
                    # Unpack as little-endian double
                    double_val = struct.unpack('<d', double_bytes)[0]
                    decoded_values.append(double_val)
                except struct.error as e:
                    print(f"Error unpacking double at position {i}: {e}")
                    # For debugging, print the bytes
                    print(f"Bytes: {[hex(b) for b in double_bytes]}")
                    decoded_values.append("ERROR")
            
            # Format of 0x03 0x00 means next 4 bytes are int
            elif chunk[0] == 0x03 and chunk[1] == 0x00 and len(chunk) >= 6:
                try:
                    # Extract the 4 bytes for the int value
                    int_bytes = chunk[2:6]
                    # Unpack as little-endian int
                    int_val = struct.unpack('<I', int_bytes)[0]
                    decoded_values.append(int_val)
                except struct.error as e:
                    print(f"Error unpacking int at position {i}: {e}")
                    # For debugging, print the bytes
                    print(f"Bytes: {[hex(b) for b in int_bytes]}")
                    decoded_values.append("ERROR")
 
        i += 128

    # Format the decoded values into a table structure
    # First 27 values become headers, rest become rows of 27 columns each
    headers = decoded_values[:27]
    data_rows = []
    
    # Process remaining values into rows of 27 columns each
    remaining_values = decoded_values[27:]
    for i in range(0, len(remaining_values), 27):
        row = remaining_values[i:i+27]
        # Pad row with empty strings if needed to ensure 27 columns
        while len(row) < 27:
            row.append("")
        data_rows.append(row)

    # Write content to a csv
    with open(csvFilePath, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)  # Write headers
        writer.writerows(data_rows)  # Write data rows
    
    return csvFilePath

def main():
    parser = argparse.ArgumentParser(description="Convert .dat files to CSV files")
    parser.add_argument("filePath", type=str, help="Path to the .dat file")
    parser.add_argument("--output", type=str, help="Path to the output CSV file")

    args = parser.parse_args()
    
    # Check if the input file exists
    if not os.path.isfile(args.filePath):
        print(f"Error: Input file '{args.filePath}' does not exist.")
        return 1
    
    # Check if the input file has the .dat extension
    if not args.filePath.lower().endswith('.dat'):
        print(f"Warning: Input file '{args.filePath}' does not have a .dat extension.")
    
    try:
        # Convert the file
        output_file = convertFile(args.filePath)
        
        # If an output path was specified, rename the file
        if args.output:
            if os.path.exists(output_file):
                # If the output file already exists, rename it
                if os.path.exists(args.output):
                    os.remove(args.output)
                os.rename(output_file, args.output)
                output_file = args.output
        
        print(f"Successfully converted '{args.filePath}' to '{output_file}'")
        return 0
    except Exception as e:
        print(f"Error converting file: {e}")
        return 1

if __name__ == "__main__":
    main()
