FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY ../requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app:/app/backend

# Expose port (if needed for health checks)
EXPOSE 8080

# Run the data processor
CMD ["python", "src/cli.py"]