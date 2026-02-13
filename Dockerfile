# Build para Render
# Este arquivo está na raiz do repo mission-control

FROM python:3.11-slim

WORKDIR /app

# Copia requirements
COPY requirements-api.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY api.py main.py

EXPOSE 8000

CMD ["python", "main.py"]
