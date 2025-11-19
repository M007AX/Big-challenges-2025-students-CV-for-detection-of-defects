import serial
import time

# Инициализация порта COM3
# Важно: Убедитесь, что скорость передачи данных (9600) совпадает
# со скоростью, установленной в Arduino с помощью Serial.begin()
try:
    ser = serial.Serial('COM3', 115200, timeout=1)
    time.sleep(2) # Даем время на установление соединения

    # Пример отправки данных
    data_to_send1 = "7,90,100"

    ser.write(data_to_send1.encode())
    print(f"Отправлено: {data_to_send1}")

    data_to_send2 = "7,-90,100"

    ser.write(data_to_send2.encode())
    print(f"Отправлено: {data_to_send2}")

    # Можно также отправить строку, преобразовав её в байты
    # ser.write("Hello Arduino".encode('utf-8'))

    # Проверка ответа (если Arduino что-то отправляет в ответ)
    # response = ser.readline()
    # print(f"Ответ от Arduino: {response.decode('utf-8')}")

except serial.SerialException as e:
    print(f"Ошибка при подключении к порту: {e}")

finally:
    if 'ser' in locals() and ser.isOpen():
        ser.close()
        print("Соединение закрыто.")
