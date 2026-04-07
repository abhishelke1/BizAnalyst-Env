FROM public.ecr.aws/docker/library/python:3.10-slim-bookworm
WORKDIR /app

# Install git-lfs and curl for LFS file handling
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs curl && \
    rm -rf /var/lib/apt/lists/* && \
    git lfs install

# Install requirements first for better caching
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
      echo "ERROR: northwind.db is still invalid (size: $FINAL_SIZE)" && exit 1; \
    fi && \
    echo "northwind.db verified: $FINAL_SIZE bytes"

EXPOSE 7860
ENV PYTHONUNBUFFERED=1

# SCOUT AI Server - autonomous business analyst
CMD ["uvicorn", "scout_server:app", "--host", "0.0.0.0", "--port", "7860"]
