FROM openjdk:11

# Install Python and other necessary packages
RUN apt-get update && apt-get install -y \
  curl \
  gnupg \
  maven \
  python3 \
  python3-pip \
  python3-venv \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy sample code
COPY . .

# Make scripts executable
RUN chmod +x /app/scaffold.py

# Install Diagrid CLI
RUN curl -o- https://downloads.diagrid.io/cli/install.sh | bash && \
  mv ./diagrid /usr/local/bin/diagrid && \
  chmod +x /usr/local/bin/diagrid

# Create the directory for Diagrid credentials
RUN mkdir -p /root/.diagrid

# Set the config file name 
ENV CONFIG_FILE="dev-invoke-java-project-container.yaml"

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh 

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Expose the application port
EXPOSE 5001
