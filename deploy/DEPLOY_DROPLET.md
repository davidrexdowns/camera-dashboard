# gizzagawk.com on droplet + storage on edge-1 (NetBird only)

## Architecture

```text
Internet → gizzagawk.com (170.64.229.136:443) → k3s-control dashboard
k3s-control ──NetBird──► edge-1 (100.103.209.30:8080)  latest/*.jpg
k3s-control ──NetBird──► pi4-2 / pi4-3               camera on/off (SSH)
Pis ──NetBird──► edge-1                              push latest frames
WSL                                             AI models only (not in this path)
```

| Traffic | Path |
|---------|------|
| Public UI | `https://gizzagawk.com` |
| Frame bytes | `100.103.209.30:8080` (overlay only) |
| Pi control | `100.103.113.117` / `100.103.175.87` (overlay SSH) |

---

## Part 1 — edge-1 storage (`100.103.209.30`)

SSH to edge-1:

```bash
ssh david@192.168.3.11
```

Copy and run setup (from your dev machine):

```bash
scp ~/camera_dashboard/deploy/edge-1-storage-setup.sh david@192.168.3.11:~/
ssh david@192.168.3.11 'bash ~/edge-1-storage-setup.sh'
```

Test from **droplet** (after Part 2) or any NetBird peer:

```bash
curl -I http://100.103.209.30:8080/
```

Allow david to receive rsync from Pis:

```bash
# on edge-1
mkdir -p ~/.ssh && chmod 700 ~/.ssh
# add pi root public keys to ~/.ssh/authorized_keys if Pis push via rsync
```

---

## Part 2 — droplet (`k3s-control`)

### Copy app

From WSL (SSH key working):

```bash
rsync -avz --exclude 'static/*.jpg' --exclude .venv \
  ~/camera_dashboard/ root@170.64.229.136:/opt/camera_dashboard/
```

### Install on droplet

```bash
ssh root@170.64.229.136

cd /opt/camera_dashboard
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn

cp deploy/.env.droplet.example .env

# SSH to Pis (one-time)
ssh-keyscan -H 100.103.113.117 100.103.175.87 >> ~/.ssh/known_hosts
ssh-copy-id root@100.103.113.117
ssh-copy-id root@100.103.175.87

systemctl enable --now camera-dashboard   # after copying service file below
```

```bash
cp /opt/camera_dashboard/deploy/camera-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now camera-dashboard
curl -s http://127.0.0.1:8000/health
curl -I http://100.103.209.30:8080/    # storage reachable over NetBird
```

### Caddy + domain

DNS **A** records:

| Name | Value |
|------|--------|
| `@` | `170.64.229.136` |
| `www` | `170.64.229.136` |

```bash
apt install -y caddy
cp /opt/camera_dashboard/deploy/Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy
```

Open `https://gizzagawk.com`

---

## Part 3 — Pis push latest to edge-1

On **pi4-2** (root):

```bash
export STORAGE_USER=david
export CAMERA_ID=pi4-2
# copy pi-push-latest-to-edge1.sh to the Pi, then:
bash pi-push-latest-to-edge1.sh
```

Repeat on **pi4-3** with `CAMERA_ID=pi4-3`.

Optional: systemd timer every 5s while camera runs (ask if you want this automated).

---

## Verify

1. `curl -I http://100.103.209.30:8080/latest/pi4-2.jpg` from droplet
2. `https://gizzagawk.com` → Turn ON → Show Latest Frame

---

## Your NetBird IPs (reference)

| Host | NetBird IP |
|------|------------|
| k3s-control | 100.103.86.154 |
| edge-1 | 100.103.209.30 |
| pi4-2 | 100.103.113.117 |
| pi4-3 | 100.103.175.87 |
| david (WSL via Windows) | 100.103.163.168 |
