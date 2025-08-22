# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements if exists, else skip
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy server.py and other source files
COPY server.py ./

# Run the server
CMD ["python", "server.py"]