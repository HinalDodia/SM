# Use an official lightweight Python image
FROM python:3.9-slim

# Set system-level dependencies for XGBoost and health checks
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security (Hugging Face requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker caching
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app files and models
COPY --chown=user . .

# Hugging Face Spaces run on port 7860 by default
EXPOSE 7860

# Command to run your FastAPI app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]