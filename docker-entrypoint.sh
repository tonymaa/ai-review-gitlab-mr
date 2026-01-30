#!/bin/sh
set -e

# Create necessary directories if they don't exist
mkdir -p /app/data /app/cache /app/logs

# Set proper permissions (if running as root in container)
if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /app/data /app/cache /app/logs 2>/dev/null || true
fi

# Print startup info
echo "=========================================="
echo "  GitLab AI Review - Web Server"
echo "=========================================="
echo ""
echo "Server will start on: http://0.0.0.0:19000"
echo "API docs available at: http://0.0.0.0:19000/docs"
echo ""

# Check Python and dependencies
echo "Checking Python environment..."
python --version || exit 1

# Execute the main command
exec "$@"
