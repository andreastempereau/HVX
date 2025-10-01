#!/bin/bash
# Stop the helmet system

echo "Stopping Helmet OS..."

# Stop all services
docker-compose down

# Clean up containers (optional)
if [[ "$1" == "--clean" ]]; then
    echo "Cleaning up containers and images..."
    docker-compose down --rmi all --volumes --remove-orphans
fi

echo "Helmet OS stopped."