# Use the official Python base image
FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Expose the port on which the application will run
EXPOSE 8001

# Copy requirements first so Docker cache is efficient
COPY requirements.txt .

# Install build deps, pip install and clean up
RUN apk add --no-cache --virtual .build-deps \
  build-base linux-headers \
  && pip install --no-cache-dir -r requirements.txt \
  && apk del .build-deps

# Copy the rest of the application code
COPY . .



# Run the Durable Agent
CMD ["python", "main.py"]

