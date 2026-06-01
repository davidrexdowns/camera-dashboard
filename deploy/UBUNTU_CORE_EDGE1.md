# edge-1 fresh install (Ubuntu Core)

Use this when rebuilding **edge-1** from scratch. The current script targets classic Ubuntu + nginx (`edge-1-storage-setup.sh`). Ubuntu Core uses snaps — adapt the steps below.

## What edge-1 does today

| Service | Port | Purpose |
|---------|------|---------|
| nginx (HTTP static) | 8080 | Serves `/data/frames/` — `latest/`, `archive/`, `datasets/` |
| ssh | 22 | rsync from Pis and WSL direct upload |

No dashboard runs on edge-1; camera control and dataset UI live on the **droplet** ([camera-dashboard](https://github.com/davidrexdowns/camera-dashboard)) or **WSL** ([gawkagent](https://github.com/davidrexdowns/gawkagent)).

## Before wiping the machine

1. Confirm datasets are backed up (or still on Pis / WSL cache):
   ```bash
   curl -s http://100.103.209.30:8080/datasets/ | head
   ```
2. Clone deploy scripts from GitHub on your dev machine:
   ```bash
   git clone https://github.com/davidrexdowns/camera-dashboard.git
   ```

## After Ubuntu Core install

1. **NetBird** — join the same mesh; note new overlay IP.
2. **Storage layout** — create writable data partition or bind mount:
   ```text
   /data/frames/latest/
   /data/frames/archive/
   /data/frames/datasets/
   ```
3. **HTTP file server** — options on Core:
   - **nginx snap** (`sudo snap install nginx`) with custom config pointing `root` at `/data/frames`, listen `8080`
   - Or a minimal **Python/Caddy snap** serving static files
4. **Firewall** — allow NetBird (`100.103.0.0/16`) and LAN (`192.168.3.0/24`) to ports 22 and 8080 only.
5. **SSH keys** — add Pi root keys and your WSL key to `authorized_keys` for rsync uploads.
6. **Update peers** — if overlay IP changes, update:
   - `STORAGE_BASE_URL` in camera-dashboard / gawkagent `.env`
   - Pi push scripts (`deploy/pi-push-latest-to-edge1.sh`)
   - Droplet `.env` on k3s-control

## Test

From any NetBird peer:

```bash
curl -I http://<edge-1-overlay-ip>:8080/latest/
```

Push a test file:

```bash
echo test > /tmp/pi4-2.jpg
rsync -av /tmp/pi4-2.jpg david@<edge-1>:/data/frames/latest/pi4-2.jpg
```

## Related repos

| Repo | Role |
|------|------|
| [camera-dashboard](https://github.com/davidrexdowns/camera-dashboard) | Droplet UI + `deploy/edge-1-storage-setup.sh` |
| [gawkagent](https://github.com/davidrexdowns/gawkagent) | WSL UI + exports |
| [edge-client](https://github.com/davidrexdowns/edge-client) | Pi frame capture |
