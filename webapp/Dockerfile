FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy webapp source
COPY . .

# Cloud Run sets PORT env var (default 8080)
ENV PORT=8080

EXPOSE ${PORT}

CMD exec gunicorn --bind :${PORT} --workers 1 --threads 4 --timeout 120 app_remote:app
