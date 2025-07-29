#this code is just used to check if the pico is connected to the network
#if it does, the LED on the pico will turn on

import network
import time
import machine
import ubinascii
from PicoHelperTools.picopass import passWD

########################################
#MESSAGE TO END USER               #####
#CHANGE PASSWORD                   #####
#PASSWORD WILL BE ON ULINK SITE    #####
                                   #####
########################################

#sets up WLAN information 
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
#reports mac address
mac = ubinascii.hexlify(network.WLAN().config('mac'),':').decode()
print(mac)
wlan.connect('ULink', passWD) 

#defines the LED and initializes it to be off
LED = machine.Pin("LED", machine.Pin.OUT)
LED.off()

#tries to connect to the network once per second
while not wlan.isconnected():
    time.sleep(1)
    print('Connecting to network...')

#turns the LED on and prints out the config information onto the console
LED.on()
print(wlan.ifconfig())