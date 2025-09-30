FROM python:3.11-slim

# Install system dependencies (ffmpeg for audio conversion)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create audio storage directory
RUN mkdir -p /app/audio_storage

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "main.py"]