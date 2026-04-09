ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}
WORKDIR /app
EXPOSE 8001
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
CMD ["python", "main.py"]
