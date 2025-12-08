FROM python:3.11-slim

WORKDIR /app

# Install server dependencies (kept separate for better layer caching)
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir -r ./server/requirements.txt

# Copy the entire repo (less fragile than piecemeal copies)
COPY . .

# Ensure README is available for sdk packaging
RUN cp README.md sdk/README.md || true

# Install the SDK in editable mode so runagent_pulse is importable
RUN pip install --no-cache-dir -e ./sdk

# Ensure package resolution when running in container
ENV PYTHONPATH="/app:/app/sdk"

# Create volume mount point for SQLite
VOLUME /app/data

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run server
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]


