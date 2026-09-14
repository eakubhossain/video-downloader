# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install ffmpeg (required for yt-dlp video/audio merging)
# and clean up apt cache to keep image size small
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port (Render sets the PORT environment variable)
EXPOSE 10000

# Run uvicorn when the container launches
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
