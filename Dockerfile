FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Run the application
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
