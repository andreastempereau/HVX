#!/bin/bash
# Start the helmet system with Docker Compose

set -e

echo "Starting Helmet OS..."

# Check if images exist, build if not
if ! docker images | grep -q helmet-base; then
    echo "Base images not found, building..."
    ./deploy/scripts/build.sh
fi

# Create necessary directories
mkdir -p logs recordings models

# Set up X11 forwarding for UI (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xhost +local:root 2>/dev/null || echo "Warning: Could not set up X11 forwarding"
fi

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to initialize..."
sleep 10

# Check service health
echo "Checking service status..."
docker-compose ps

echo ""
echo "Helmet OS started successfully!"
echo ""
echo "Services:"
echo "  Video Service:       localhost:50051"
echo "  Perception Service:  localhost:50052"
echo "  Voice Service:       localhost:50053"
echo "  Orchestrator:        localhost:50054"
echo ""
echo "To view logs: docker-compose logs -f [service-name]"
echo "To stop:      docker-compose down"