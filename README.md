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
├── tests
│   └── test_peakCount.py # Unit tests for peak counting functionality
├── requirements.txt     # Project dependencies
├── main.py              # Entry point for the application
└── README.md            # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
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

2. Input the path to your pressure data file and set the parameters for peak detection (height, prominence, distance, width).

3. Click the "Count Peaks" button to analyze the data and visualize the detected peaks.

## Testing

To run the unit tests for the peak counting functionality, navigate to the `tests` directory and run:
```
pytest test_peakCount.py
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.