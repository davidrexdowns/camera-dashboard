# camera_dashboard

FastAPI + HTMX dashboard for **gizzagawk.com** — Pi camera on/off, latest frames, multi-camera dataset recording, upload to edge-1 storage.

## Stack role

| Host | Role |
|------|------|
| **Droplet** (`k3s-control`) | Runs this app behind Caddy (NetBird-only) |
| **edge-1** | Frame + dataset storage (HTTP `:8080`, see `deploy/edge-1-storage-setup.sh`) |
| **Pi4-2 / Pi4-3** | `edge-client` captures JPEGs; SSH systemctl for on/off |
| **WSL** | Use [gawkagent](https://github.com/davidrexdowns/gawkagent) for local control + Isaac exports |

## Quick start (dev)

```bash
cd camera_dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp deploy/.env.droplet.example .env   # edit Pi / storage URLs
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Deploy

See [deploy/DEPLOY_DROPLET.md](deploy/DEPLOY_DROPLET.md) for droplet + edge-1 setup.

## Related repos

- [gawkagent](https://github.com/davidrexdowns/gawkagent) — WSL companion + V-JEPA / Isaac Lab exports
- [edge-client](https://github.com/davidrexdowns/edge-client) — Pi frame capture
- [lan-pipe-2](https://github.com/davidrexdowns/lan-pipe-2) — Caddy / droplet compose
