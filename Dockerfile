FROM python:3.12-slim

# Install ffmpeg and tesseract-ocr for OCR support
RUN apt-get update && apt-get install -y ffmpeg tesseract-ocr && apt-get clean

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of your code
COPY . .

# Run your Python application
CMD ["python", "bot.py"]