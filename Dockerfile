# Use the official Python 3.11 slim image as a base
FROM python:3.11-slim

# Set a working directory inside the container
WORKDIR /app

# --- NEW: Create the workspace directory ---
RUN mkdir -p /app/workspace

# Upgrade pip and install the necessary libraries
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    requests \
    beautifulsoup4 \
    lxml \
    pandas \
    numpy \
    matplotlib \
    scipy \
    scikit-learn

# This line is optional but good practice.
# It copies your code into the image for self-containment.
COPY . /app