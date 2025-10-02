# Dockerfile
FROM python:slim

# Install system dependencies (for Chrome + Selenium)
RUN apt-get update && apt-get install -y \
    curl unzip wget gnupg \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Setup working dir
WORKDIR /app

# Copy requirements (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose port for MCP
EXPOSE 8000

# Run MCP server
CMD ["python", "server.py"]
