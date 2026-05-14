FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONPATH=/app

#ЗАМЕНА ПОРТА
EXPOSE 5000

CMD ["python", "-m", "app.main"]