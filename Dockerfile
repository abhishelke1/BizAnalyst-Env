FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 7860
ENV PYTHONUNBUFFERED=1

# SCOUT AI Server - autonomous business analyst
CMD ["uvicorn", "scout_server:app", "--host", "0.0.0.0", "--port", "7860"]
