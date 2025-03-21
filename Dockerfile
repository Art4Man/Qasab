FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /app/stored_pdfs && chmod 777 /app/stored_pdfs
RUN mkdir -p /app/web_serve && chmod 777 /app/web_serve

# Set environment variable for your bot token
# This should be overridden when running the container
ENV TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
ENV PUBLIC_URL="http://localhost:8000"

CMD ["python", "app.py"]
