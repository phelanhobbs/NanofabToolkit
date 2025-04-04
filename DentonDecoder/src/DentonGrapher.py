import argparse
import datetime
import matplotlib.pyplot as plt
import numpy as np
import csv
from pathlib import Path

def create_graph(input_file, column_name="Chamber Pressure (Torr)", output_file=None, show_graph=True, log_scale=False):
    """
    Create a graph of a selected column vs time from a CSV log file.
    
    Args:
        input_file: Path to CSV log file
        column_name: Name of the column to graph (default: "Chamber Pressure (Torr)")
        output_file: Path to save the graph (optional)
        show_graph: If True, displays the graph (default: True)
        log_scale: If True, uses logarithmic scale for y-axis (default: False)
    """
    try:
        # Read the CSV file
        with open(input_file, 'r', errors='replace') as f:
            csv_reader = csv.reader(f)
            
            # Read header to get column indices
            headers = next(csv_reader)
            time_col = 0  # Time is in the first column
            
            # Find the column index for the requested column
            try:
                data_col = headers.index(column_name)
            except ValueError:
                print(f"Column '{column_name}' not found in CSV file.")
                print(f"Available columns: {', '.join(headers)}")
                return False
            
            # Data structures for the graph
            times = []
            values = []
            
            # Base time to convert timestamps to relative seconds
            base_time = None
            
            # Process each line
            for row in csv_reader:
                if not row or len(row) <= data_col:
                    continue
                
                # Extract timestamp
                time_str = row[time_col]
                try:
                    # Convert time string to datetime object
                    time_obj = datetime.datetime.strptime(time_str, "%H:%M:%S")
                    
                    # Set base time if not set
                    if base_time is None:
                        base_time = time_obj
                    
                    # Calculate seconds since base time
                    time_delta = (time_obj - base_time).total_seconds()
                    if time_delta < 0:  # Handle crossing midnight
                        time_delta += 24 * 60 * 60
                        
                    # Extract value from the selected column
                    try:
                        value = float(row[data_col])
                        
                        # Add to data lists
                        times.append(time_delta)
                        values.append(value)
                    except ValueError:
                        # Skip if value can't be converted to float
                        continue
                except ValueError:
                    # Skip if time can't be parsed
                    continue
        
        # Create the graph if we have data
        if times and values:
            # Create figure and axis
            fig, ax = plt.figure(figsize=(10, 6)), plt.gca()
            
            # Plot the data
            ax.plot(times, values)
            
            # Add labels and title
            ax.set_xlabel('Time (seconds since start)')
            ax.set_ylabel(column_name)
            ax.set_title(f'{column_name} vs Time - {Path(input_file).stem}')
            
            # Format y-axis to use scientific notation if not log scale
            if not log_scale:
                ax.ticklabel_format(axis='y', style='sci', scilimits=(0,0))
            else:
                ax.set_yscale('log')
            
            # Add grid
            ax.grid(True)
            
            # Save the figure if requested
            if output_file:
                plt.savefig(output_file)
                print(f"Graph saved to: {output_file}")
            
            # Show the graph if requested
            if show_graph:
                plt.show()
            else:
                plt.close(fig)
            
            # If very few data points, warn the user
            if len(times) < 10:
                print(f"Warning: Only {len(times)} data points were found for plotting.")
            
            return True
        else:
            print(f"No valid time and {column_name} data found in the file.")
            return False
        
    except Exception as e:
        print(f"Error processing file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Create time series graph from CSV log file")
    parser.add_argument("input_file", help="Path to the CSV log file")
    parser.add_argument("-c", "--column", default="Chamber Pressure (Torr)",
                        help="Column name to graph (default: 'Chamber Pressure (Torr)')")
    parser.add_argument("-o", "--output", help="Output graph file path (optional)")
    parser.add_argument("--no-display", action="store_true", 
                        help="Don't display the graph, just save it if output is specified")
    parser.add_argument("--log", action="store_true",
                        help="Use logarithmic scale for y-axis")
    
    args = parser.parse_args()
    
    # If no output file is specified and no display, specify a default output
    if args.no_display and not args.output:
        args.output = Path(args.input_file).with_suffix('.png')
    
    create_graph(
        args.input_file,
        column_name=args.column,
        output_file=args.output, 
        show_graph=not args.no_display,
        log_scale=args.log
    )

if __name__ == "__main__":
    main()