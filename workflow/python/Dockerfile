# Use a base image
FROM python:3.12

# Set the working directory 
WORKDIR /app

# Install necessary components for virtual environment
RUN apt-get update && apt-get install -y python3-venv && rm -rf /var/lib/apt/lists/*

# Create a Python virtual environment
RUN python -m venv venv

# List contents to verify creation
RUN ls -la venv/bin/

# Install Diagrid CLI 
RUN curl -o- https://downloads.diagrid.io/cli/install.sh | bash
RUN mv ./diagrid /usr/local/bin/diagrid
RUN chmod +x /usr/local/bin/diagrid

# Copy sample code
COPY . .

# Activate virtual environment and update pip and install certifi
RUN . venv/bin/activate \
  && pip install --upgrade pip \
  && pip install certifi \
  && pip install --no-cache-dir -r requirements.txt

# Ensure Python uses the correct certificates
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Create the directory for Diagrid credentials
RUN mkdir -p /root/.diagrid

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/

# Set the config file name
ENV CONFIG_FILE="dev-workflow-python-project-container.yaml"

# Make the entrypoint script executable
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["entrypoint.sh"]

# Expose the application port
EXPOSE 5001
