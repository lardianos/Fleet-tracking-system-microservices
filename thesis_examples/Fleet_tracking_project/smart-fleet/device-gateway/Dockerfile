FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV GATEWAY_HOST=0.0.0.0
ENV GATEWAY_PORT=7494

CMD ["python", "/app/src/main.py"]