# Daily 9:00 AM Personal Intelligence Dashboard

A zero-database, zero-LLM morning intelligence briefing generator designed for an **Ubuntu 24.04 home server**. It ingests live RSS news, spot metals rates, forex data, and local server vitals, compiling them into a responsive, dark-mode Tailwind CSS dashboard served on port **8089**.

Accessible across your home LAN (`http://192.168.29.89:8089`) or your secure Tailscale mesh (`http://ubuntu-server:8089`).

---

## 🏗 Architecture Overview

```
                      +------------------------------------------+
                      |               DATA SOURCES               |
                      +------------------------------------------+
                      | - Spot Metals (Gold & Silver APIs)       |
                      | - USD-to-INR Currency Exchange           |
                      | - Geopolitics & Iran/USA (Google News)   |
                      | - Markets & Finance (Economic Times)     |
                      | - Sports Desk (ESPNcricinfo & BBC)       |
                      | - IT & AI Jobs (Google Jobs & RemoteOK)  |
                      | - Ubuntu Host Vitals (psutil / sysfs)    |
                      +------------------------------------------+
                                           |
                                           v
    [ cron @ 09:00 IST ] ---> [ fetch_and_build.py (Python) ]
                                           |
                                  Jinja2 + Tailwind CSS
                                           v
                             /var/www/morning-dashboard/index.html
                                           |
                                           v
                           [ Static HTTP Server (Port 8089) ]
                                           |
                        +------------------+------------------+
                        |                                     |
               LAN (192.168.x.x:8089)             Tailscale Mesh (:8089)
```

---

## 📁 Repository Structure

| File | Purpose |
| :--- | :--- |
| `fetch_and_build.py` | Python ingestion engine (RSS, spot metals, forex, server vitals, HTML rendering). |
| `template.html` | Tailwind CSS dark-mode dashboard template with responsive card grid. |
| `serve.py` | Zero-dependency static file HTTP server on port 8089 with cache-busting headers. |
| `requirements.txt` | Python dependencies (`requests`, `feedparser`, `jinja2`, `psutil`). |
| `setup.sh` | Automated 1-click deployment script for Ubuntu 24.04 (venv, systemd, cron). |
| `deploy.sh` | 1-click rsync deployer script from your Mac to the Ubuntu server. |
| `morning-dashboard.service` | Systemd service unit to run the web server on port 8089 automatically on boot. |
| `nginx-morning-dashboard.conf` | Alternative Nginx site configuration (optional). |
| `morning-dashboard-cron` | Crontab snippet for the 09:00 AM IST daily run. |

---

## 🚀 1-Click Automated Setup (Ubuntu 24.04)

Clone or copy this directory to your Ubuntu home server and execute:

```bash
chmod +x setup.sh
sudo ./setup.sh
```

### What `setup.sh` does automatically:
1. Installs system packages: `python3`, `python3-venv`, `python3-pip`, `cron`, `curl`.
2. Creates `/opt/morning-dashboard` and sets up a PEP 668 compliant Python virtual environment (`/opt/morning-dashboard/venv`).
3. Creates `/var/www/morning-dashboard` for static files.
4. Installs and starts the `morning-dashboard.service` systemd unit on port `8089`.
5. Detects your server timezone and schedules the **09:00 AM IST** cron job:
   - If server timezone is `Asia/Kolkata` (IST): `0 9 * * *`
   - If server timezone is `UTC`: `30 3 * * *` (03:30 UTC = 09:00 IST)
6. Performs an immediate test fetch so the dashboard is live right away.

---

## 🌐 Network Access

Once deployed, access the dashboard from any browser:

- **Local Machine:** [http://localhost:8089](http://localhost:8089)
- **Home LAN:** `http://<UBUNTU_LAN_IP>:8089` (e.g., `http://192.168.29.89:8089`)
- **Tailscale Mesh:** `http://<TAILSCALE_IP>:8089` or `http://<HOSTNAME>:8089`

---

## 🔧 Manual Operations & DevOps Commands

### 1. Trigger an Instant Refresh / Rebuild
You can generate a fresh edition anytime without waiting for the 09:00 AM cron trigger:

```bash
sudo /opt/morning-dashboard/venv/bin/python3 /opt/morning-dashboard/fetch_and_build.py -o /var/www/morning-dashboard/index.html
```

### 2. View Generator Logs
```bash
tail -f /var/log/morning-dashboard.log
```

### 3. Check or Restart Web Server Service
```bash
# Check status
systemctl status morning-dashboard

# Restart service
sudo systemctl restart morning-dashboard

# View web server access logs
journalctl -u morning-dashboard -f
```

### 4. Test Locally in Offline/Development Mode
If testing without active internet connectivity or outside the server:

```bash
python3 fetch_and_build.py --mock-offline -o ./test_index.html
python3 serve.py -p 8089 -d .
```

---

## 🧮 Data Sources & Calculation Logic

1. **Spot Metals, Commodities & Crypto:**
   - **XAU (Gold) & XAG (Silver):** Live API spot rates converted to 10g 24K and 1kg Bullion in INR.
   - **Forex (USD/INR):** Real-time currency exchange.
   - **Brent Crude Oil:** Global benchmark barrel price.
   - **Crypto Spot (BTC & ETH):** Live INR spot rates via CoinGecko.

2. **Weather & Air Quality (Zero-Key):**
   - **Open-Meteo:** Current Temperature, Humidity, Wind speed, Sunrise & Sunset.
   - **Open-Meteo Air Quality:** Real-time US AQI & PM2.5 tracking.

3. **RSS Intelligence Feeds:**
   - **Geopolitics (Iran/USA/Conflict):** Google News RSS (24h window).
   - **Finance & Markets:** Economic Times Markets RSS feed.
   - **Sports:** Interleaved top 6 headlines from ESPNcricinfo & BBC Football.
   - **IT & AI Jobs:** Filtered top 6 remote & domestic listings from Google News Tech Jobs & Remote AI.

4. **Homelab & Ubuntu Host Telemetry:**
   - CPU utilization (%) and CPU core temperature (`psutil` / sysfs thermal zones).
   - RAM and Root filesystem capacity (`/`).
   - Network Bandwidth (Total GB sent & received since boot).
   - Docker daemon inspection (`docker ps` container count).
   - Quick-launch bookmarks for Pi-hole, Plex, Portainer, and Tailscale.

5. **Client-Side Interactive Features:**
   - **🎙 1-Click Audio Briefing:** Native Web Speech API synthesis with animated audio waveform.
   - **⭐ Bookmark & Read-Later:** LocalStorage persistence for saving articles.
   - **✓ Mark as Read:** Checkmark action to dim read stories.
   - **🔍 Real-Time Search & Category Filter:** Instant headline filtering without page refresh.

---

## 📱 How to Get It On Your Phone (iOS & Android)

You do **NOT** need to build a native app (Kotlin/Swift) or pay app store developer fees. We built it as a **Progressive Web App (PWA)** with native push alerts:

### 1. Add as an "App" on Your Phone (Standalone Fullscreen PWA)
1. Open the URL in your phone's browser (Safari on iPhone, Chrome on Android):
   - Home Wi-Fi: `http://192.168.29.89:8089`
   - Anywhere on 4G/5G: `http://<Tailscale-IP>:8089` (via free Tailscale app on your phone)
2. Tap the browser menu:
   - **iPhone (Safari):** Tap the **Share** button (box with arrow) -> **Add to Home Screen** -> **Add**.
   - **Android (Chrome):** Tap the **⋮** (three dots) -> **Install app** or **Add to Home screen**.
3. It now has its own standalone app icon (**MorningIntel**) on your phone screen, opens fullscreen without browser URL bars, and feels like a native app!

---

### 2. Daily 09:00 AM Push Notifications to Your Phone
Receive an automated morning ping at **09:00 AM IST** with today's Mumbai weather, gold rate, and top headlines:

#### Option A: Free `ntfy` Push Notification (Easiest, No account needed)
1. Install the free **ntfy** app on your phone:
   - [iOS App Store](https://apps.apple.com/app/ntfy/id1625396347) / [Android Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
2. Open the app and subscribe to any private topic name (e.g. `mumbai-intel-briefing-user`).
3. Pass `--ntfy-topic mumbai-intel-briefing-user` to `fetch_and_build.py` in your cron:
   ```bash
   NTFY_TOPIC="mumbai-intel-briefing-user"
   ```
4. At 09:00 AM every morning, your phone buzzes with a banner notification. Tapping it opens your dashboard immediately!

#### Option B: Telegram Bot Notification
1. Message `@BotFather` on Telegram to create a bot and get your token.
2. Provide your token and chat ID via `--telegram-token` and `--telegram-chat-id`.
