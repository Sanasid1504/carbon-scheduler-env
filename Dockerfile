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
ENV API_BASE_URL="https://api.openai.com/v1"
ENV MODEL_NAME="gpt-4"
# HF_TOKEN should be set at runtime (no default)

# Expose port for Hugging Face Spaces
EXPOSE 7860

# Run FastAPI server (for OpenEnv API compliance)
CMD ["python", "api_server.py"]

# Alternative commands:
# Run Streamlit UI: CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
# Run main demo: docker run carbon-scheduler python main.py
# Run inference: docker run -e HF_TOKEN=xxx carbon-scheduler python inference.py medium
# Interactive: docker run -it carbon-scheduler bash

