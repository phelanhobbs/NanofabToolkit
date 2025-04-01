# Peak Counter GUI

This project is a graphical user interface (GUI) application for counting peaks in pressure data. It allows users to input parameters for peak detection and visualize the results in an intuitive interface.

## Project Structure

```
peak-counter-gui
├── src
│   ├── gui.py          # GUI implementation for the peak counting program
│   ├── peakCount.py    # Peak counting logic
│   └── assets
│       └── icon.py     # Application icon definition
├── build               # Directory containing build artifacts
│   └── peak-counter    # Built application
├── dist                # Distribution packages 
│   └── peak-counter.exe  # Built application on windows 
├── tests
│   └── test_peakCount.py # Unit tests for peak counting functionality
├── requirements.txt     # Project dependencies
├── main.py              # Entry point for the application
└── README.md            # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone git@github.com:phelanhobbs/ALDPeakCounter.git
   cd peak-counter-gui
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python main.py
   ```

2. Working with the application:
- Add data files using the file selection dialog
- Set peak detection parameters (height, prominence, distance, width)
- Process the files to detect peaks
- Apply offsets to adjust data as needed
- View results in both text format and interactive plots
- Reset offsets if necessary

## Building an Executable

To build a standalone executable:

   ```
   pip install pyinstaller pyinstaller --onefile --windowed main.py
   ```
The executable will be created in the `dist` directory.

## Testing

To run the unit tests for the peak counting functionality:

   ```
   pytest test_peakCount.py
   ```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.