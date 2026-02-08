FROM python:3.11-slim

WORKDIR /app

# Install network tools for debugging and multicast support
RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# (NEXUS-0 SDK uses standard libraries mostly, but uvicorn/fastapi/psutil are needed for the bridge)
RUN pip install fastapi "uvicorn[standard]" psutil httpx cryptography websockets

# Copy SDK and Bridge
COPY nx0mesh_sdk.py .
COPY bridge_server.py .
COPY web/ ./web/

# Defaults
ENV NX0_NAME="Node-X"
ENV NX0_TYPE="Bridge"
ENV NX0_ZONE="NEXUS-0"
ENV NX0_EGO="100"
ENV PORT=8080

EXPOSE 8080

# The bridge_server handles both the SDK pulse and the Web UI
CMD ["python", "bridge_server.py"]
