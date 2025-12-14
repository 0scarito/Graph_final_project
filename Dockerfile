FROM python:3.11-slim

WORKDIR /code

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app /code/app

# Copy scripts folder for data ingestion
COPY scripts /code/scripts

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

