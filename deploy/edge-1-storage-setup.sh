#!/usr/bin/env bash
# Run ON edge-1 (100.103.209.30) as user with sudo.
set -euo pipefail

sudo apt update
sudo apt install -y nginx

sudo mkdir -p /data/frames/latest /data/frames/archive /data/frames/datasets
sudo chown -R "${USER}:${USER}" /data/frames

sudo tee /etc/nginx/sites-available/gizz-frames >/dev/null <<'EOF'
server {
    listen 8080;
    server_name _;

    location / {
        root /data/frames;
        autoindex on;
        add_header Cache-Control "no-store";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/gizz-frames /etc/nginx/sites-enabled/gizz-frames
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl restart nginx

# SSH + frames on overlay/LAN only (avoid locking yourself out)
sudo ufw allow from 100.103.0.0/16 to any port 22 proto tcp comment 'ssh netbird'
sudo ufw allow from 192.168.3.0/24 to any port 22 proto tcp comment 'ssh lan'
sudo ufw allow from 100.103.0.0/16 to any port 8080 proto tcp comment 'gizz frames netbird'
sudo ufw --force enable

echo "Test from another NetBird peer:"
echo "  curl -I http://100.103.209.30:8080/latest/"
