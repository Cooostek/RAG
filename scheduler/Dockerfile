#Для чего тут всё это
#легкий старт
#быстрая сборка

#базовый образ для контейнера
#slim - облегченная версия

FROM python:3.11-slim

WORKDIR /app

#кеширование
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt


# app модуль придет через volume из docker-compose
ENV PYTHONPATH=/app/backend:/app

#задаёт единственный процесс — запуск планировщика
CMD ["python", "run_scheduler.py"]