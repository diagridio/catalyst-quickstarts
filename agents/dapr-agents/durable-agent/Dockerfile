FROM python:3.12-slim
WORKDIR /app
EXPOSE 5001
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY . .
CMD ["python", "main.py"]
