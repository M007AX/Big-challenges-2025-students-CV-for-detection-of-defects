import serial
import time
import asyncio

# Инициализация порта COM3
# Важно: Убедитесь, что скорость передачи данных (9600) совпадает
# со скоростью, установленной в Arduino с помощью Serial.begin()

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
#ser = serial.Serial('COM3', 115200, timeout=1)
time.sleep(2)
# Пример отправки данных
data_to_send1 = "7,90,100"
data_to_send2 = "7,-90,100"

def rotation(ser):
    try:

        signal = "brak"
        ser.write(signal.encode())
    except serial.SerialException as e:
        print(f"Ошибка при подключении к порту: {e}")


while input() == "1":
    rotation(ser)

ser.close()

