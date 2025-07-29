The steps to create a working Pico powered monitoring tool are vary quite a lot and there are no hard set rules on how to create the tool
This is less of a "Guide" or "Instruction Set", more just writing up the internal thoughts I had when I created my various raspberry pi monitoring tools

1) Inspect the tool being monitored

Look at the device, are there I/O ports already, or are you going to tap into some other wire elsewhere?
Do you have any documentation or can you call up the company to get ladder diagrams?

2) Design your pico around the device being measured

If you are tapping into an analog signal (such as the case when building the paralyne device), you will need to use one of the three analog inputs
If you are tapping into an RX/TX connection, such as with the vacuum pump, the TX/RX GPIO pins (pins 1 and 2) are the best to used

Some tools offer a high voltage output, can that be stepped down to 5V DC and plugged into VSYS (pin 39) or will it need to be powered by USB

3) Simulate and test on computer and then on a breadboard for the circuit

Things that seem like they work on paper, or even in a sim, might not actually work when it comes to producing an actual working product
For instance, I needed to add schottky diodes to my original paralyne device because my original board resulted in the overall resistance of the device dropping, leading to unintended readings

4) Set up ULINK to work with the pico device

It requires the MAC address of the pico, I have provided a section of code to help determine that. Just run the code in this folder on the pico device and it will print to the console
From there, go to getconnected.utah.edu and follow the steps for an "other" device. Place the MAC address alongside a device name and keep note of the password.

5) Write your code to upload results up to the server

Should it be sent in batches or one at a time, what causes the system to start sending data. Questions that need to be asked before working serverside
Reminder that the picos only have 256kB of RAM, not much

6) Set up server to GET information

I always like just setting up an api endpoint, then from that constructing a file containing the information from that specified run

7) test

8) test

9) test more

5) If that works, design a PCB for the device to sit on and solder it together

There is a hotplate in the lab for this purpose
