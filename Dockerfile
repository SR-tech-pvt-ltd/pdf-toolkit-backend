# Use an official lightweight Python image
FROM python:3.10-slim

# Prevent Python from writing pyc files and keep stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install LibreOffice, OpenCV dependencies, and Java
# FIXED: Replaced obsolete 'libgl1-mesa-glx' with modern 'libgl1'
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    default-jre \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Expose the port that FastAPI will run on
EXPOSE 5000

# Command to start the Uvicorn server
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "5000"]
