# Use an official Python base image
FROM python:3.11

# Install Node.js
RUN apt-get update && apt-get install -y curl gnupg && \
  curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
  apt-get install -y nodejs

# Set the working directory
WORKDIR /app

# Copy sample code
COPY . .

# Install Diagrid CLI
RUN curl -o- https://downloads.diagrid.io/cli/install.sh | bash && \
  mv ./diagrid /usr/local/bin/diagrid && \
  chmod +x /usr/local/bin/diagrid

# Create the directory for Diagrid credentials
RUN mkdir -p /root/.diagrid

# Make scripts executable
RUN chmod +x /app/scaffold.sh /app/scaffold.py

# Set the config file name 
ENV CONFIG_FILE="dev-pubsub-javascript-project-container.yaml"

# Install virtualenv
RUN pip install virtualenv

# Ensure the venv directory is clear before creating a new virtual environment
RUN if [ -d "/app/venv" ]; then rm -rf /app/venv; fi
RUN virtualenv --clear /app/venv

# Install PyYAML in the virtual environment
RUN /app/venv/bin/pip install pyyaml

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh 

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Expose the application port
EXPOSE 5001
