# Use the official Python base image
FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Expose the port on which the application will run
EXPOSE 5001

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

ENV UVICORN_PORT=5001

# Run the FastAPI application using uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
