FROM python:3.12-slim

# Install ffmpeg, tesseract-ocr, tesseract language data for English, and ghostscript
RUN apt-get update && \
    apt-get install -y ffmpeg tesseract-ocr tesseract-ocr-eng ghostscript && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY . .

# Run your Python application
CMD ["python", "bot.py"]