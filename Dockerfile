# 1. Use an official, lightweight Python environment
FROM python:3.11-slim

# 2. Install LibreOffice required for Word/Excel/PPT to PDF conversions
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 3. Set the working directory inside the server
WORKDIR /app

# 4. Copy your requirements file and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy your backend.py file into the server
COPY . .

# 6. Boot up the Uvicorn server on Render's required port
CMD ["sh", "-c", "uvicorn backend:app --host 0.0.0.0 --port ${PORT:-10000}"]
