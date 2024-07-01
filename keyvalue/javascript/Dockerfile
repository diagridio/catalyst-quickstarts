# Use a base image
FROM node:lts

# Set the working directory 
WORKDIR /app

# Install Diagrid CLI 
RUN curl -o- https://downloads.diagrid.io/cli/install.sh | bash


# Ensure the Diagrid CLI is executable globally
RUN mv ./diagrid /usr/local/bin/diagrid || echo "Diagrid binary not found!"

RUN chmod +x /usr/local/bin/diagrid

# Copy sample code
COPY . .

# Install Node.js dependencies
RUN npm install

# Create the directory for Diagrid credentials
RUN mkdir -p /root/.diagrid

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/

# Make the entrypoint script executable
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["entrypoint.sh"]

# Expose the application port
EXPOSE 5001
