#!/bin/bash
echo "Fetching latest yt-dlp patch..."
pip install -U https://github.com/ytdl-patched/ytdl-patched/archive/master.tar.gz

echo "Starting Uvicorn..."
# Port is read from the PORT environment variable injected by Render
uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
