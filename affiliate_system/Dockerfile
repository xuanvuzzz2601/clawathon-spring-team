FROM python:3.10-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Create volume mount point for SQLite data
RUN mkdir -p /app/instance

EXPOSE 8080

ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PORT=8080

CMD ["python", "app.py"]
