# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install system dependencies (frotz)
RUN apt-get update && apt-get install -y frotz && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user and group
RUN addgroup --system app && adduser --system --group app

# Create and set permissions for the data directory
RUN mkdir -p /data/saves && chown -R app:app /data

# Switch to the non-root user
USER app

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "app:app"]
