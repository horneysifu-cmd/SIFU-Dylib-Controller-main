# SIFU Dylib Controller — isolated VPS deployment

This deployment uses a new directory, systemd unit, database directory and Nginx site. It does not modify the older `/root/sifu-license` project.

## Requirements
- Ubuntu VPS with Python 3.12+, Nginx and Git installed.
- A hostname pointed to this VPS. Use HTTPS before entering the admin token.
- Review the service and Nginx templates before installing.

## Install
Run the following on the VPS as a sudo-capable user, after replacing the repository URL if it changes:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv nginx
sudo mkdir -p /opt/sifu-dylib-controller /var/lib/sifu-dylib-controller
sudo git clone https://github.com/horneysifu-cmd/SIFU-Dylib-Controller-main.git /opt/sifu-dylib-controller
sudo python3 -m venv /opt/sifu-dylib-controller/backend/.venv
sudo /opt/sifu-dylib-controller/backend/.venv/bin/pip install --upgrade pip
sudo /opt/sifu-dylib-controller/backend/.venv/bin/pip install -r /opt/sifu-dylib-controller/backend/requirements.txt
sudo chown -R www-data:www-data /var/lib/sifu-dylib-controller
sudo install -m 0644 /opt/sifu-dylib-controller/deploy/sifu-dylib-controller.service /etc/systemd/system/sifu-dylib-controller.service
```

Create the secret environment file. Generate a long token with the first command, then copy its output into the ADMIN_TOKEN value:

```bash
openssl rand -hex 32
sudo nano /etc/sifu-dylib-controller.env
```

Use this content, replacing the placeholder:
```ini
ADMIN_TOKEN=PASTE_THE_GENERATED_RANDOM_TOKEN_HERE
DATABASE_PATH=/var/lib/sifu-dylib-controller/licenses.db
ALLOWED_ORIGINS=
RATE_LIMIT_PER_MINUTE=30
ENABLE_DOCS=false
```

Secure and start the API:
```bash
sudo chown root:www-data /etc/sifu-dylib-controller.env
sudo chmod 640 /etc/sifu-dylib-controller.env
sudo systemctl daemon-reload
sudo systemctl enable --now sifu-dylib-controller
sudo systemctl status sifu-dylib-controller --no-pager
curl -fsS http://127.0.0.1:8765/health
```

Publish the dashboard with a separate Nginx site. Replace YOUR_HOSTNAME with the hostname you control:
```bash
sudo mkdir -p /var/www/sifu-dylib-controller/dashboard
sudo cp -a /opt/sifu-dylib-controller/dashboard/. /var/www/sifu-dylib-controller/dashboard/
sudo sed 's/YOUR_HOSTNAME/your.hostname.example/g' /opt/sifu-dylib-controller/deploy/nginx.conf.example | sudo tee /etc/nginx/sites-available/sifu-dylib-controller
sudo ln -s /etc/nginx/sites-available/sifu-dylib-controller /etc/nginx/sites-enabled/sifu-dylib-controller
sudo nginx -t
sudo systemctl reload nginx
```

After enabling HTTPS for the hostname, open the dashboard, go to Settings, enter the same HTTPS origin as API Base URL and paste the generated admin token. The token is stored only in the current browser session.

## Important
- Do not expose the admin token over plain HTTP. Configure TLS first.
- Keep the database directory private and back it up.
- This initial API uses single-process in-memory rate limiting. Keep one Uvicorn worker until rate limiting is moved to a shared store.
- Device references are client-supplied identifiers, not hardware attestation.
- Do not run these commands against the old `/root/sifu-license` project.
