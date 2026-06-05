#!/bin/bash
set -e
cd "$(dirname "$0")"
docker rm -f we-mp-rss 2>/dev/null || true
docker run -d --name we-mp-rss -p 8001:8001 -v ./data:/app/data -e WERSS_AUTH_WEB=True rachelos/we-mp-rss:latest
echo "Started. Open http://localhost:8001"
docker logs -f we-mp-rss
