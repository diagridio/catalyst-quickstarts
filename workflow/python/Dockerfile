# Use the official Python base image
FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Expose the port on which the application will run
EXPOSE 5001

# Copy requirements first so Docker cache is efficient
COPY requirements.txt .

# Install build deps, pip install and clean up
RUN apk add --no-cache --virtual .build-deps \
  build-base linux-headers \
  && pip install --no-cache-dir -r requirements.txt \
  && apk del .build-deps

# Copy the rest of the application code
COPY . .

ENV UVICORN_PORT=5001

# Run the FastAPI application using uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
