# Turning on notifications — server setup

Everyone in the group now gets a notification when someone adds, edits or deletes an
expense they're in, or settles up with them. It reaches phones even when the browser is
closed, because it uses **Web Push**.

**Chrome only allows notifications on https**, and the app currently runs on
`http://13.235.142.203:5001`. So the app needs a hostname and a certificate. That's the
one-time setup below: about 15 minutes, all of it free.

Nothing here touches the billing app that already answers on port 80 — the new nginx
block only responds to the new hostname. The old `http://13.235.142.203:5001` and `:5002`
keep working exactly as they do now, including the Chrome extension.

---

## 1. A free hostname (DuckDNS)

1. Open <https://www.duckdns.org> and sign in (Google/GitHub — no card, no cost).
2. Create a subdomain, e.g. `oursplit`, and set its IP to **13.235.142.203**.
3. You now have `oursplit.duckdns.org`. Replace it everywhere below with whatever you chose.

> If the EC2 public IP isn't an Elastic IP, it changes when the instance is stopped and
> started — update the IP on duckdns.org when that happens.

## 2. Open port 443 in AWS

EC2 → Instances → the instance → Security → its security group → **Edit inbound rules** →
Add rule: **HTTPS / TCP / 443 / 0.0.0.0/0** (add `::/0` too if you use IPv6) → Save.

Port 80 is already open, which certbot needs in step 4.

## 3. nginx site for the new hostname

```bash
sudo tee /etc/nginx/sites-available/splitwise >/dev/null <<'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name oursplit.duckdns.org;

    # Django API (gunicorn)
    location /api/ {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # The service worker must never be served from cache
    location = /sw.js {
        proxy_pass http://127.0.0.1:5001/sw.js;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
    }

    # React app (vite preview)
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/splitwise /etc/nginx/sites-enabled/splitwise
sudo nginx -t && sudo systemctl reload nginx
```

Check both apps still work:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://13.235.142.203/          # billing app, still 200
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: oursplit.duckdns.org' http://127.0.0.1/
```

## 4. Certificate (Let's Encrypt, free, auto-renewing)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d oursplit.duckdns.org     # choose "redirect" when asked
sudo certbot renew --dry-run                     # confirms auto-renewal works
```

## 5. Deploy the app

On the machine you deploy from, before running `deploy.sh`, put the new address into
`frontend/src/config.js` so the old http link can point people at the new one:

```js
export const SECURE_APP_URL = 'https://oursplit.duckdns.org';
```

Then deploy as usual:

```bash
./deploy.sh
```

`sync.sh` installs `pywebpush`, runs the migration and creates the notification signing
key. Give the key a contact address once (any push service that has a problem with your
pushes would use it to reach you):

```bash
cd /home/ubuntu/splitwise/backend
source /home/ubuntu/splitwise/.venv/bin/activate
python manage.py ensure_vapid_keys --subject mailto:you@example.com
sudo systemctl restart splitwise_backend.service
```

> **Never delete `backend/push_keys/`.** Every phone's subscription is tied to that key.
> If it's lost, notifications stop until everyone turns them on again. It's outside git,
> so `git pull` and `sync.sh` leave it alone — but a fresh clone of the repo won't have it.

## 6. Check it works

```bash
curl -s https://oursplit.duckdns.org/api/push/public_key/     # {"public_key":"B..."}
curl -s -o /dev/null -w '%{http_code}\n' https://oursplit.duckdns.org/
```

Then on your phone: open `https://oursplit.duckdns.org`, log in, tap the **🔔** in the
top bar → **Turn on notifications** → Allow → **Send test**. The notification should
appear within a few seconds. Close the browser completely and have someone add an
expense — it should still arrive.

## 7. What to tell everyone

1. Open **https://oursplit.duckdns.org** (the old link still works but can't send
   notifications) and log in once — logins are stored per address.
2. Chrome menu **⋮ → Install app** (or *Add to Home screen*). Delete the old shortcut.
   The installed app opens without a browser bar.
3. Tap the **🔔** in the app → **Turn on notifications** → **Allow**.
4. iPhone: open the link in **Safari → Share → Add to Home Screen**, open the app from
   the Home Screen, *then* tap the bell. iOS doesn't allow it any other way (iOS 16.4+).

Each person turns it on per device, and can turn it off from the same bell.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Blocked request. This host is not allowed" | The hostname isn't in `preview.allowedHosts` in `frontend/vite.config.js` (`.duckdns.org` is). Add it and redeploy. |
| Bell says notifications need the secure address | The app was opened on `http://…:5001`. Use the https link. |
| `/api/push/public_key/` returns 503 | The key wasn't created: run `python manage.py ensure_vapid_keys` and restart the backend. |
| Test says "This device isn't registered" | Turn notifications off and on again in the bell (the subscription expired or the key changed). |
| Notifications arrive late on OnePlus/Oppo/Xiaomi | Phone settings → Apps → Chrome → Battery → allow background activity. |
| Nothing arrives at all on one phone | Check Chrome's own notification permission for the site, and that the phone isn't in Do Not Disturb / Focus. |

## What it costs

Nothing. nginx, certbot and the push libraries are open source; Let's Encrypt, DuckDNS
and the browsers' push services are free. Opening port 443 adds no AWS charge.
