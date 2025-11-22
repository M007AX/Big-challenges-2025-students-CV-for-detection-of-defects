import serial
import time
import asyncio

# Инициализация порта COM3
# Важно: Убедитесь, что скорость передачи данных (9600) совпадает
# со скоростью, установленной в Arduino с помощью Serial.begin()
"""
ser = serial.Serial('COM3', 115200, timeout=1)
time.sleep(2)
# Пример отправки данных
data_to_send1 = "7,90,100"
data_to_send2 = "7,-90,100"
"""
def rotation(ser, data_to_send1, data_to_send2):
    try:


        ser.write(data_to_send1.encode())
        print(f"Отправлено: {data_to_send1}")
        time.sleep(1.2)
        ser.write(data_to_send2.encode())
        print(f"Отправлено: {data_to_send2}")
    except serial.SerialException as e:
        print(f"Ошибка при подключении к порту: {e}")

"""
while input() == "1":
    rotation()
"""
"""
ser.close()
"""
