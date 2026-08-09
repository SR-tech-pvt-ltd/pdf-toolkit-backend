# Use official Python image
FROM python:3.10-slim

# Install LibreOffice (Docker gives us the root access needed for this)
RUN apt-get update && apt-get install -y libreoffice --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your backend files into the container
COPY . .

# Expose the port that Render expects
EXPOSE 10000

# Start the Uvicorn server using Render's dynamic port
CMD uvicorn backend:app --host 0.0.0.0 --port ${PORT:-10000}