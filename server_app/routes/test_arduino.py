import serial
import time



ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
time.sleep(2)

signal = "brak"
ser.write(signal.encode())

ser.close()