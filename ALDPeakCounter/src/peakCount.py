import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import argparse
import os

def count_peaks(file_path, height=None, prominence=None, distance=None, width=None, plot=False, quiet=False):
    """
    Count the number of peaks in pressure data from a text file.
    
    Parameters:
    file_path (str): Path to the text file
    height (float): Minimum height of peaks
    prominence (float): Minimum prominence of peaks
    distance (int): Minimum distance between peaks
    width (float): Required width of peaks
    plot (bool): Whether to display a plot
    quiet (bool): If True, only output the number of peaks
    
    Returns:
    tuple: (peak_count, pressure_times, pressures, peaks) - Returns data needed for plotting
    """
    # Initialize data lists
    pressure_times = []
    pressures = []
    
    # Read the data file
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        # Skip the header line
        for line in lines[1:]:
            # Split by tabs and remove empty strings
            values = [val.strip() for val in line.split('\t') if val.strip()]
            if len(values) >= 2:  # Ensure we have at least pressure time and pressure
                try:
                    pressure_time = float(values[0])
                    pressure = float(values[1])
                    pressure_times.append(pressure_time)
                    pressures.append(pressure)
                except ValueError:
                    continue  # Skip lines with non-numeric values
    except Exception as e:
        if not quiet:
            print(f"Error reading file: {e}")
        return 0, None, None, None
    
    if not pressure_times:
        if not quiet:
            print("No valid data points found")
        return 0, None, None, None
    
    # Convert to numpy arrays
    pressure_times = np.array(pressure_times)
    pressures = np.array(pressures)
    
    # Find peaks
    peaks, properties = find_peaks(pressures, height=height, prominence=prominence, 
                                  distance=distance, width=width)
    
    # Improved approach for detecting a final peak
    if len(pressures) > 10:  # Ensure we have enough data points
        # Look at the last N points to analyze the trend at the end
        window = 10
        end_segment = pressures[-window:]
        
        # Check if the end segment has a rising or plateau pattern
        is_rising = all(end_segment[i] <= end_segment[i+1] for i in range(len(end_segment)-1))
        
        # Calculate plateau by checking if points are within a small range of each other
        plateau_tolerance = 0.01 * (max(pressures) - min(pressures))  # 1% of full range
        is_plateau = all(abs(end_segment[i] - end_segment[i+1]) < plateau_tolerance 
                        for i in range(len(end_segment)-1))
        
        # Check if final segment is significantly higher than the rest of the data
        avg_pressure = np.mean(pressures[:-window])
        end_avg = np.mean(end_segment)
        is_elevated = end_avg > avg_pressure + 0.05 * (max(pressures) - min(pressures))  # 5% above average
        
        # Find the local maximum in the end segment
        if (is_rising or is_plateau or is_elevated) and len(peaks) > 0:
            # Find max value in end segment
            local_max_idx = np.argmax(end_segment) + (len(pressures) - window)
            
            # Check if the end peak meets criteria
            add_end_peak = True
            
            # Check if there's already a peak near the end
            if len(peaks) > 0 and (len(pressures) - peaks[-1] <= window):
                add_end_peak = False
                
            # Check height requirement
            if height is not None and pressures[local_max_idx] < height:
                add_end_peak = False
                
            # Check distance requirement
            if distance is not None and len(peaks) > 0:
                if local_max_idx - peaks[-1] < distance:
                    add_end_peak = False
            
            # Add the end peak if it meets all requirements
            if add_end_peak:
                peaks = np.append(peaks, local_max_idx)
    
    peak_count = len(peaks)
    
    # Display results
    if quiet:
        print(peak_count)
    else:
        print(f"Found {peak_count} peaks in the data file: {os.path.basename(file_path)}")
        if peak_count > 0:
            print(f"Peak times: {pressure_times[peaks]}")
            print(f"Peak pressures: {pressures[peaks]}")
    
    # Plot if requested (now handled by multi_file_plot if multiple files)
    if plot and not quiet and len(peaks) > 0:
        # Only plot if this is the only file being processed
        if not hasattr(count_peaks, 'multiple_files') or not count_peaks.multiple_files:
            plt.figure(figsize=(10, 6))
            plt.plot(pressure_times, pressures, label="Pressure")
            plt.plot(pressure_times[peaks], pressures[peaks], 'ro', label="Detected Peaks")
            plt.title(f"Pressure vs Time (Found {peak_count} peaks)")
            plt.xlabel("Pressure Time")
            plt.ylabel("Pressure")
            plt.grid(True)
            plt.legend()
            plt.show()
    
    return peak_count, pressure_times, pressures, peaks

def multi_file_plot(results, plot=True):
    """
    Plot multiple pressure datasets on a single graph.
    
    Parameters:
    results (list): List of tuples (filename, peak_count, pressure_times, pressures, peaks)
    plot (bool): Whether to display the plot
    """
    if not plot:
        return
        
    plt.figure(figsize=(12, 7))
    
    # Use a different color for each file
    colors = plt.cm.tab10.colors
    marker_styles = ['o', 's', '^', 'd', 'x', '+', '*', 'v', '<', '>']
    
    for i, (filename, peak_count, pressure_times, pressures, peaks) in enumerate(results):
        if pressure_times is None or pressures is None:
            continue
            
        color = colors[i % len(colors)]
        marker = marker_styles[i % len(marker_styles)]
        
        # Plot the pressure data
        label = f"{os.path.basename(filename)} ({peak_count} peaks)"
        plt.plot(pressure_times, pressures, label=label, color=color, alpha=0.7)
        
        # Plot the peaks as points
        if peaks is not None and len(peaks) > 0:
            plt.plot(pressure_times[peaks], pressures[peaks], marker=marker, 
                     linestyle='None', color=color, markersize=8)
    
    plt.title("Pressure vs Time (Multiple Files)")
    plt.xlabel("Pressure Time")
    plt.ylabel("Pressure")
    plt.grid(True)
    plt.legend()
    plt.show()

def main():
    parser = argparse.ArgumentParser(description='Count pressure peaks in one or more data files.')
    parser.add_argument('file_paths', type=str, nargs='+', help='Path(s) to the input data file(s)')
    parser.add_argument('--height', type=float, help='Minimum peak height')
    parser.add_argument('--prominence', type=float, default=0.01, help='Minimum peak prominence')
    parser.add_argument('--distance', type=int, default=10, help='Minimum samples between peaks')
    parser.add_argument('--width', type=float, help='Minimum peak width')
    parser.add_argument('--plot', action='store_true', help='Show plot of data with peaks')
    parser.add_argument('--quiet', action='store_true', help='Only output the number of peaks')
    
    args = parser.parse_args()
    
    # Set a flag for multiple files to prevent individual plots
    count_peaks.multiple_files = len(args.file_paths) > 1
    
    # Process each file and collect results for plotting
    results = []
    for file_path in args.file_paths:
        peak_count, pressure_times, pressures, peaks = count_peaks(
            file_path, 
            height=args.height, 
            prominence=args.prominence, 
            distance=args.distance, 
            width=args.width, 
            plot=False, 
            quiet=args.quiet
        )
        results.append((file_path, peak_count, pressure_times, pressures, peaks))
    
    # Plot all files together if requested and multiple files provided
    if args.plot and not args.quiet and count_peaks.multiple_files:
        multi_file_plot(results, plot=True)
    elif args.plot and not args.quiet and len(results) == 1:
        # If only one file, use the original plotting
        file_path, peak_count, pressure_times, pressures, peaks = results[0]
        if pressure_times is not None and pressures is not None and peaks is not None:
            plt.figure(figsize=(10, 6))
            plt.plot(pressure_times, pressures, label="Pressure")
            plt.plot(pressure_times[peaks], pressures[peaks], 'ro', label="Detected Peaks")
            plt.title(f"Pressure vs Time (Found {peak_count} peaks)")
            plt.xlabel("Pressure Time")
            plt.ylabel("Pressure")
            plt.grid(True)
            plt.legend()
            plt.show()

if __name__ == "__main__":
    main()