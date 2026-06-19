FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py storage.py webhook_server.py ./
COPY cogs/ ./cogs/
COPY templates/ ./templates/
CMD ["python", "bot.py"]
