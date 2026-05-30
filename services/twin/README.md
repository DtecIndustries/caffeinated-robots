# Digital Twin

JS frontend that visualizes the production line and robot state in real time.

## What it does

- Renders a 3D scene of the production line (conveyor, stations, boxes) using Three.js
- Displays robot arm state (joint positions, current action) synced from the vision service
- Overlays the live MJPEG camera feed from the vision service inside the scene
- Reads state from the online DB (via Soda Straw) or falls back to a local DB / mock data for offline dev

## Stack

- JavaScript
- Three.js — 3D scene
- Vite — dev server and bundler
- Soda Straw — DB client (online or local)

## Running

```bash
npm install
cp ../../.env.example .env
npm run dev
```
