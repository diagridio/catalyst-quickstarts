# Use the official Python base image
FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Expose the port on which the application will run
EXPOSE 8001

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project file for dependency resolution
COPY pyproject.toml .

# Install build deps, dependencies, and clean up
RUN apk add --no-cache --virtual .build-deps \
  build-base linux-headers \
  && uv pip install --system . \
  && apk del .build-deps

# Copy the rest of the application code
COPY . .



# Run the Durable Agent
CMD ["python", "main.py"]

