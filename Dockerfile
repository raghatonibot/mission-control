FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py main.py
COPY openclaw_client.py .
COPY workflows.py .

EXPOSE 8000

CMD ["python", "main.py"]
