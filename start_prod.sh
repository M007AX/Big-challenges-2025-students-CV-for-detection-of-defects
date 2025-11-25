#!/bin/bash
set -e

# Переходим в корень проекта (можно убрать, если не нужен)
cd /home/sirius/PycharmProjects/Big-challenges-2025-students-CV-for-detection-of-defects1

# Запуск systemd сервиса (созданного и настроенного ранее)
sudo systemctl start camera_app.service
echo "✓ camera_app запущен через Gunicorn"

# Пауза для запуска сервиса
sleep 2

# Проверка доступности backend'a
if curl -s http://127.0.0.1:5000/ > /dev/null; then
    echo "✓ Backend жив на http://127.0.0.1:5000"
else
    echo "✗ Backend не отвечает!"
    exit 1
fi

# Перезагрузка nginx, чтобы обновить конфигурацию и прокси
sudo systemctl reload nginx
echo "✓ nginx перезагружен"

echo ""
echo "========================================="
echo "Приложение доступно по адресу:"
echo "http://localhost"
echo "========================================="
