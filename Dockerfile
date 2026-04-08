FROM public.ecr.aws/docker/library/python:3.10-slim-bookworm
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --default-timeout=120 -r requirements.txt

# Copy application code
COPY . .

# Handle LFS: if northwind.db is a pointer, fetch real file from GitHub
RUN FILE_SIZE=$(stat -c%s /app/northwind.db 2>/dev/null || echo "0") && \
    echo "northwind.db initial size: $FILE_SIZE bytes" && \
    if [ "$FILE_SIZE" -lt 10000 ]; then \
      echo "Detected LFS pointer, downloading real file..." && \
      LFS_URL="https://github.com/abhishelke1/BizAnalyst-Env/raw/main/northwind.db" && \
      curl -L -o /app/northwind.db "$LFS_URL" && \
      NEW_SIZE=$(stat -c%s /app/northwind.db) && \
      echo "Downloaded northwind.db: $NEW_SIZE bytes"; \
    fi && \
    FINAL_SIZE=$(stat -c%s /app/northwind.db) && \
    if [ "$FINAL_SIZE" -lt 10000 ]; then \
      echo "WARNING: northwind.db may be invalid (size: $FINAL_SIZE), continuing anyway..."; \
    else \
      echo "northwind.db verified: $FINAL_SIZE bytes"; \
    fi

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Create a non-root user for HuggingFace Spaces compatibility
RUN useradd -m -u 1000 user
USER user

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Expose port
EXPOSE 7860

# Start server
CMD ["uvicorn", "scout_server:app", "--host", "0.0.0.0", "--port", "7860"]
