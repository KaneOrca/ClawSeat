# Arena Pretext UI Deployment Guide

This document provides instructions for deploying the `arena-pretext-ui` frontend to staging or production.

## API Base URL Strategy

The application uses a **runtime same-origin strategy** by default.

- **Same-Origin (Recommended)**: If the frontend and backend are served from the same domain/host (e.g., via Caddy reverse proxy), no environment variables are needed. The app will automatically request `/api/...` relative to the current page.
- **Cross-Origin Override**: If you need to hit a backend on a different host, set `VITE_API_BASE_URL` during the build.

## Environment Variables

The following environment variables can be set during the build process:

- `VITE_API_BASE_URL`: The base URL for the Arena Backend API. 
  - **Default**: `""` (Empty string, results in same-origin relative paths)
  - **Example**: `https://arena-api.example.com`

## Build Instructions

To create a production build:

```bash
cd /Users/ywf/coding/arena-pretext-ui
npm install
npm run build
```

The build artifacts will be generated in the `dist/` directory.

## Caddy / Web Server Configuration

### Static File Serving

The contents of the `dist/` directory should be served as static files.

### History Fallback (Recommended)

To support future URL-based routing and prevent 404s on refresh, include a history fallback rule.

Example Caddy configuration:

```caddy
:80 {
    root * /path/to/arena-pretext-ui/dist
    file_server
    
    # Handle API requests (if backend is on the same host)
    handle /api/* {
        reverse_proxy localhost:3001
    }

    # Proxy challenge assets if they are managed by the backend
    handle /challenges/* {
        reverse_proxy localhost:3001
    }

    # Fallback to index.html for any other requests
    try_files {path} /index.html
}
```

## Smoke Test (Staging)

1. Deploy the `dist/` folder to the VPS.
2. If using same-origin (recommended), ensure Caddy is correctly reverse-proxying `/api` to the backend.
3. Verify that the "Initialize Agent" button on the Home view successfully registers a new agent.
4. Verify that the Leaderboard and Watch views correctly fetch real-time data.
