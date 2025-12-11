FROM python:3.11-slim

WORKDIR /app

# Install git (needed for installing runagent from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install server dependencies (kept separate for better layer caching)
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir -r ./server/requirements.txt

# Install runagent from GitHub (latest version with all features)
# This ensures we get the latest API including user_id and persistent_memory support
RUN pip install --no-cache-dir git+https://github.com/runagent-dev/runagent.git

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


