# Use the official Python base image
FROM --platform=$BUILDPLATFORM python:3.14-alpine

# Set the working directory inside the container
WORKDIR /app

# Expose the port on which the application will run
EXPOSE 5001

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project file to the working directory
COPY pyproject.toml .

# Install the Python dependencies
RUN uv pip install --system .

# Copy the application code to the working directory
COPY . .

ENV UVICORN_PORT 5001

# Run the FastAPI application using uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]