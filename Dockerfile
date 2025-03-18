# Use Python 3.10 slim as base image for a smaller footprint
FROM python:3.10-slim

# Set working directory for the application
WORKDIR /app

# ===== Install Dependencies =====
# Copy only requirements file first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ===== Copy Application Code =====
# Copy application files
COPY app.py .

# ===== Start Application =====
# Run the monitoring service
CMD ["python", "app.py"] 