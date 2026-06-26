# Secure, slim Python base image
FROM python:3.10-slim

# Set internal Python parameters
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create an unprivileged user first
RUN useradd -u 8888 -m appuser

# Set workspace directory
WORKDIR /app

# Install operational compiler utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency records and grant ownership to appuser
COPY requirements.txt /app/
RUN chown -R appuser:appuser /app

# Switch context to our secure user before installing pip packages
USER appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Install math frameworks directly into the appuser home space
RUN pip install --no-cache-dir --user --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

COPY regulations.py bias_audit.py incidents.py engine.py report.py verify_sources.py app.py main.py /app/
COPY data/ /app/data/

# Expose Streamlit's default network port
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
