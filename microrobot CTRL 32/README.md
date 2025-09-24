# 32 SIMPLE CONTROL: 4×8 Electromagnet Array Controller

Pixel-level control for a 4×8 electromagnet array.  
This code sets per-coil **magnitude (0–100%)** and **direction (+/−)** in real time.

## Features
- Addressable 4×8 grid (row–column indexing).
- Independent magnitude and polarity per pixel.

## Hardware
- Controller: Raspberry Pi Pico / Arduino (Communication: I2C) 
- PWM Driver: Adafruit 16-Channel 12-bit PWM/Servo Driver
- H bridge Motor Driver: Adafruit DRV8871 DC Motor Driver Breakout Board 
- Magnets: Uxcell DC24V 2.5KG Force Eelectric Lifting Magnet Electromagnet Solenoid Lift Holding 20mm x 15mm

## Hardware Connection
PC -> Arduino -> PWM Driver -> H bridge Motor Driver -> Magnets


## Install 

### Install Library
Arduino
- Adafruit PWM Servo Driver Library (for PCA9685)

Python (PC)
- Python 3.9 or newer
- Packages:
  ```bash
  pip install pyserial numpy pygame

### Flash .ino file to Pi Pico / Arduino
- Directory: magnet_control_arduino/magnet_control_arduino.ino
- Download Arduino IDE 
- Select Board and Upload

### 
