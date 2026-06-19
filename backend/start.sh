#!/bin/bash
echo "Fetching latest yt-dlp patch..."
pip install --upgrade yt-dlp

echo "Starting Uvicorn..."
# Port is read from the PORT environment variable injected by Render
uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
