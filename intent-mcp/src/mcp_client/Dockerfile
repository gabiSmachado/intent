# Use official Python image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements if exists, else skip
COPY requirements.txt ./

RUN pip install -r requirements.txt

# Copy client.py into container
COPY client.py ./

# Set default command to run client.py
CMD ["python", "client.py"]