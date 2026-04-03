FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OPENAI_API_KEY=""
ENV API_BASE_URL="https://api.openai.com/v1"
ENV MODEL_NAME="gpt-4"

# Default command: run main demo
CMD ["python", "main.py"]

# Alternative commands:
# Run inference: docker run -e OPENAI_API_KEY=xxx carbon-scheduler python inference.py medium
# Interactive: docker run -it carbon-scheduler bash
