FROM public.ecr.aws/docker/library/python:3.11-slim-bookworm
WORKDIR /app

# Install curl for potential fallback download
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --default-timeout=120 -r requirements.txt

# Copy application code
COPY . .

# Verify northwind.db exists and is a valid SQLite file (not an LFS pointer)
# LFS pointers are small text files (~130 bytes), real DB is ~24MB
RUN if [ ! -f /app/northwind.db ]; then \
      echo "ERROR: northwind.db not found" && exit 1; \
    fi && \
    FILE_SIZE=$(stat -c%s /app/northwind.db) && \
    echo "northwind.db size: $FILE_SIZE bytes" && \
    if [ "$FILE_SIZE" -lt 10000 ]; then \
      echo "ERROR: northwind.db appears to be an LFS pointer (size: $FILE_SIZE)" && \
      cat /app/northwind.db && \
      exit 1; \
    fi && \
    echo "northwind.db verified: $FILE_SIZE bytes"

EXPOSE 7860
ENV PYTHONUNBUFFERED=1

# SCOUT AI Server - autonomous business analyst
CMD ["uvicorn", "scout_server:app", "--host", "0.0.0.0", "--port", "7860"]
