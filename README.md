## NanofabToolKit

Below are some tools developed by Phe Hobbs for the University of Utah's Nanofab department.
Information about us can be found at nanofab.utah.edu


# ALDPeakCounter

The ALDpeakcounter takes a csv file from and graphs the file while also providing a numerical count of local maximums.
This graph is zoomable and allows for multiple charts in order for users to draw comparisons, which can performed using the x-axis translation tool.
Additionally, by adjusting the peak detection parameters, it is possible to make the counting more or less sensitive allowing for quick reads of the number of peaks in the provided csv.

# DentonDecoder

The Denton Decoder program loads in one or more .dat file from the Denton635 machine and converts it to a (much) more readable csv.
After conversion, it then allows a user to graph any of the columns produced.
As with the ALD peak counter, this program allows users to translate their graphs left and right for ease of comparisons.

# PreciousMetalReader

The Precious Metal Reader allows users to automatically and easily download the total usage for four precious metals.
This downloads the information from cores.utah.edu and automatically converts it to a csv split by users alongside their personal usage of the metals per tool.
These metals are Iridium, Gold, Platinum, and Palladium and the tools are the Denton16, Denton635, and TMV.
A module named "auth.py" with the authentication code must be provided.

## Project Structure

```
NanofabToolKit
├── .git                            # Git Information
├── .gitignore                      # Ignored files
├── ALDPeakCounter                  # Counts peaks in csv
│   ├── src
│   │   ├── assets
│   │   │   ├── icon.ico                # Contains the icon for the ALDPeakCounter
│   │   │   └── icon.py                 # Contains code to ensure icon is loaded correctly
│   │   ├── gui.py                      # Defines the GUI of the ALDPeakCounter
│   │   └── peakcounter.py              # Backend of the peakcounter, actually does the counting
│   ├── main.py                         # Entry Point of the ALDPeakCounter program
│   └── requirements.txt                # List of dependencies that needs to be installed to run the program
├── DentonDecoder                   # Decodes DAT files and displays them
│   ├── src
│   │   ├── assets
│   │   │   ├── icon.ico                # Contains the icon for the decoder
│   │   │   └── icon.py                 # Contains code to ensure icon is loaded correctly
│   │   ├── gui.py                      # Defines the GUI of the DentonDecoder
│   │   ├── DentonDecoder.py            # Decodes .dat files into a more readable csv
│   │   └── DentonGrapher.py            # Graphs out the resulting csv
│   ├── main.py                         # Entry Point of the DentonDecoder program
│   └── requirements.txt                # List of dependencies that needs to be installed to run the program
├── PreciousMetalReader             # Downloads the list of precious metals from the U's cores website
│   ├── src
│   │   ├── assets
│   │   │   ├── icon.ico                # Contains the icon for the metal downloader tool
│   │   │   └── icon.py                 # Contains code to ensure icon is loaded correctly
│   │   ├── gui.py                      # Defines the GUI of the PreciousMetalReader
│   │   ├── RetrieveMonthlyMetals.py    # Downloads the information from the cores website
│   │   └── auth.py                     # MUST BE ADDED BY USER. CODE CONTAINS API ENDPOINT CODE IN ORDER TO DOWNLOAD FROM SITE
│   ├── main.py                         # Entry Point of the PreciousMetalReader program
│   └── requirements.txt                # List of dependencies that needs to be installed to run the program (none in this case)
├── ParalyneReader                  # Downloads and graphs the log files of the paralyne machine
│   ├── src
│   │   ├── assets
│   │   │   ├── icon.ico                # Contains the icon for the paralyne tool
│   │   │   └── icon.py                 # Contains code to ensure icon is loaded correctly
│   │   ├── gui.py                      # Defines the GUI of the ParalyneReader
│   │   └── ParalyneReader.py           # Backend for the tool, downloads files from the server
│   ├── main.py                         # Entry Point of the PreciousMetalReader program
│   └── requirements.txt                # List of dependencies that needs to be installed to run the program (none in this case)
├── LICENSE                         #MIT LICENSE 
└── README.MD                       #README definining how this program works (this file you're reading now)
```

## Installation

1. Clone the repository:
   ```
   git clone git@github.com:phelanhobbs/NanofabToolKit.git
   cd NanofabToolKit
   ```

2. Install the required dependencies:
   ```
   pip install -r /[toolname]/requirements.txt
   ```

3. (RetrieveMonthlyMetals only) Add the auth.py file to the program (you will need to ask for this)
    ```
    echo "HSCCode = '[code]'" > /RetrieveMonthlyMetals/src/auth.py
    ```

## Usage

1. Run the application:
   ```
   python /[toolname]/main.py
   ```

2. Working with the application:

# ALDPeakCounter

- Add data files using the file selection dialog
- Set peak detection parameters (height, prominence, distance, width)
- Process the files to detect peaks
- Apply offsets to adjust data as needed
- View results in both text format and interactive plots
- Reset offsets if necessary

# DentonDecoder

- Add data files using the file selection dialog
- Set graphing parameters (column to graph, log scale)
- Hit Generate Graph to generate the graphing
- Use the time alignment section to move data left and right
- Reset offsets if necessary

## Building an Executable

To build a standalone executable, after creating a spec file:

   ```
   pip install pyinstaller 
   pyinstaller ./[toolname]/[name].spec
   ```
   
## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
