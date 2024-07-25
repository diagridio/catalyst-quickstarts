# Use an official Python base image
FROM python:3.12

# Set the working directory
WORKDIR /app

# Install necessary components for virtual environment
RUN apt-get update && apt-get install -y python3-venv && rm -rf /var/lib/apt/lists/*

# Copy sample code
COPY . .

# Install Diagrid CLI
RUN curl -o- https://downloads.diagrid.io/cli/install.sh | bash && \
  mv ./diagrid /usr/local/bin/diagrid && \
  chmod +x /usr/local/bin/diagrid

# Create the directory for Diagrid credentials
RUN mkdir -p /root/.diagrid

# Make scripts executable
RUN chmod +x /app/scaffold.py

# Set the config file name 
ENV CONFIG_FILE="dev-invoke-python-project-container.yaml"

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh 

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Expose the application port
EXPOSE 5001
