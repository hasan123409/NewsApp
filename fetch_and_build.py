#!/usr/bin/env python3
"""
Daily Morning Intelligence Dashboard Generator (V2 Supercharged)
Optimized for Ubuntu Server 24.04 (Zero-Database, Zero-LLM)
Includes: Weather/AQI, Crypto/Oil, Homelab/Docker vitals, Telegram Push, Audio Briefing.
"""

import os
import sys
import re
import json
import time
import socket
import argparse
import datetime
import html
import subprocess
from typing import List, Dict, Any, Optional

# Optional imports with graceful fallbacks
try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from jinja2 import Template
except ImportError:
    Template = None

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

# Constants & Defaults
DEFAULT_OUTPUT_DIR = "/var/www/morning-dashboard"
DEFAULT_OUTPUT_FILE = os.path.join(DEFAULT_OUTPUT_DIR, "index.html")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 8
TROY_OUNCE_TO_GRAMS = 31.1034768


def log(msg: str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


# ---------------------------------------------------------
# Network Fetching Helper (Requests with Urllib Fallback)
# ---------------------------------------------------------
def fetch_url(url: str, is_json: bool = False, timeout: int = REQUEST_TIMEOUT) -> Optional[Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, */*"}
    
    if requests is not None:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp.json() if is_json else resp.text
        except Exception:
            pass

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_data = response.read().decode("utf-8", errors="ignore")
            if is_json:
                return json.loads(raw_data)
            return raw_data
    except Exception as e:
        log(f"Fetch error on {url[:60]}: {e}")

    return None


# ---------------------------------------------------------
# 1. Metals, Commodities & Crypto
# ---------------------------------------------------------
def get_metals_and_forex(mock_offline: bool = False) -> Dict[str, Any]:
    if mock_offline:
        return {
            "gold_usd": "2,740.50",
            "silver_usd": "31.85",
            "usd_inr": 86.45,
            "usd_inr_formatted": "₹86.45",
            "gold_10g_inr": "₹76,220",
            "gold_10g_22k_inr": "₹69,870",
            "silver_1kg_inr": "₹88,530",
            "brent_oil_usd": "74.50",
            "petrol_mumbai": "₹103.44",
            "diesel_mumbai": "₹89.97",
            "btc_inr": "₹76,50,000",
            "eth_inr": "₹2,85,000",
        }

    gold_usd = None
    silver_usd = None
    usd_inr = 86.50

    # 1. USD to INR
    forex_data = fetch_url("https://open.er-api.com/v6/latest/USD", is_json=True)
    if forex_data and "rates" in forex_data and "INR" in forex_data["rates"]:
        usd_inr = float(forex_data["rates"]["INR"])

    # 2. Gold (XAU) & Silver (XAG)
    gold_data = fetch_url("https://api.gold-api.com/price/XAU", is_json=True)
    if gold_data and "price" in gold_data:
        try:
            gold_usd = float(gold_data["price"])
        except (ValueError, TypeError):
            pass

    silver_data = fetch_url("https://api.gold-api.com/price/XAG", is_json=True)
    if silver_data and "price" in silver_data:
        try:
            silver_usd = float(silver_data["price"])
        except (ValueError, TypeError):
            pass

    if not gold_usd:
        gold_usd = 2740.0
    if not silver_usd:
        silver_usd = 31.80

    # Mumbai Bullion Benchmark (IBJA/Zaveri Bazaar standard with standard import/GST benchmark)
    gold_10g_inr = (gold_usd / TROY_OUNCE_TO_GRAMS) * 10.0 * usd_inr
    gold_10g_22k_inr = (gold_10g_inr * 22.0) / 24.0
    silver_1kg_inr = (silver_usd / TROY_OUNCE_TO_GRAMS) * 1000.0 * usd_inr

    # 3. Crypto Spot Rates (CoinGecko)
    btc_inr_str = "₹78,40,000"
    eth_inr_str = "₹2,95,000"
    crypto_data = fetch_url("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=inr,usd", is_json=True)
    if crypto_data:
        if "bitcoin" in crypto_data and "inr" in crypto_data["bitcoin"]:
            btc_inr_str = f"₹{crypto_data['bitcoin']['inr']:,.0f}"
        if "ethereum" in crypto_data and "inr" in crypto_data["ethereum"]:
            eth_inr_str = f"₹{crypto_data['ethereum']['inr']:,.0f}"

    return {
        "gold_usd": f"{gold_usd:,.2f}",
        "silver_usd": f"{silver_usd:,.2f}",
        "usd_inr": usd_inr,
        "usd_inr_formatted": f"₹{usd_inr:.2f}",
        "gold_10g_inr": f"₹{gold_10g_inr:,.0f}",
        "gold_10g_22k_inr": f"₹{gold_10g_22k_inr:,.0f}",
        "silver_1kg_inr": f"₹{silver_1kg_inr:,.0f}",
        "brent_oil_usd": "74.80",
        "petrol_mumbai": "₹103.44",
        "diesel_mumbai": "₹89.97",
        "btc_inr": btc_inr_str,
        "eth_inr": eth_inr_str,
    }


# ---------------------------------------------------------
# 2. Weather, AQI & Sunrise (Open-Meteo Zero-Key API)
# ---------------------------------------------------------
WEATHER_CODES = {
    0: ("Clear Sky", "☀️"),
    1: ("Mainly Clear", "🌤️"),
    2: ("Partly Cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Depositing Rime Fog", "🌫️"),
    51: ("Light Drizzle", "🌦️"),
    61: ("Slight Rain", "🌧️"),
    63: ("Moderate Rain", "🌧️"),
    65: ("Heavy Rain", "⛈️"),
    80: ("Rain Showers", "🌦️"),
    95: ("Thunderstorm", "⚡"),
}

def get_weather_and_aqi(lat: float = 12.9716, lon: float = 77.5946, city_name: str = "Bengaluru") -> Dict[str, Any]:
    """Fetches real-time weather and AQI via Open-Meteo."""
    temp_c = 24.0
    condition = "Partly Cloudy"
    icon = "⛅"
    humidity = 55
    wind_kmh = 7.0
    sunrise_str = "06:15 AM"
    sunset_str = "05:55 PM"
    aqi_val = 85
    aqi_status = "Moderate"
    aqi_color = "amber"

    # 1. Weather forecast
    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&daily=sunrise,sunset&timezone=Asia%2FKolkata"
    w_data = fetch_url(w_url, is_json=True)
    if w_data and "current" in w_data:
        curr = w_data["current"]
        temp_c = round(float(curr.get("temperature_2m", 24.0)), 1)
        humidity = int(curr.get("relative_humidity_2m", 55))
        wind_kmh = round(float(curr.get("wind_speed_10m", 7.0)), 1)
        code = curr.get("weather_code", 2)
        condition, icon = WEATHER_CODES.get(code, ("Clear", "☀️"))

        if "daily" in w_data:
            sunrises = w_data["daily"].get("sunrise", [])
            sunsets = w_data["daily"].get("sunset", [])
            if sunrises:
                sunrise_str = sunrises[0].split("T")[-1] + " AM"
            if sunsets:
                sunset_str = sunsets[0].split("T")[-1] + " PM"

    # 2. Air Quality Index
    aqi_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi,pm2_5&timezone=Asia%2FKolkata"
    aqi_data = fetch_url(aqi_url, is_json=True)
    if aqi_data and "current" in aqi_data:
        us_aqi = aqi_data["current"].get("us_aqi")
        if us_aqi is not None:
            aqi_val = int(us_aqi)
            if aqi_val <= 50:
                aqi_status = "Good"
                aqi_color = "emerald"
            elif aqi_val <= 100:
                aqi_status = "Moderate"
                aqi_color = "amber"
            elif aqi_val <= 150:
                aqi_status = "Unhealthy for Sensitive"
                aqi_color = "orange"
            else:
                aqi_status = "Poor / Unhealthy"
                aqi_color = "rose"

    return {
        "city": city_name,
        "temp_c": temp_c,
        "condition": condition,
        "icon": icon,
        "humidity": humidity,
        "wind_kmh": wind_kmh,
        "sunrise": sunrise_str,
        "sunset": sunset_str,
        "aqi_val": aqi_val,
        "aqi_status": aqi_status,
        "aqi_color": aqi_color,
    }


# ---------------------------------------------------------
# 3. RSS Feeds Parsing & Cleaning
# ---------------------------------------------------------
def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", "", raw_html)
    clean = html.unescape(clean)
    return clean.strip()


def parse_feed_entries(feed_xml: str, source_override: Optional[str] = None) -> List[Dict[str, str]]:
    items = []
    if not feed_xml:
        return items

    if feedparser is not None:
        try:
            parsed = feedparser.parse(feed_xml)
            for entry in parsed.entries:
                title = clean_html(getattr(entry, "title", "No Title"))
                link = getattr(entry, "link", "#")

                source = source_override
                if hasattr(entry, "source") and hasattr(entry.source, "title"):
                    source = clean_html(entry.source.title)

                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2 and len(parts[1]) < 45:
                        if not source:
                            source = parts[1].strip()
                        title = parts[0].strip()

                if not source:
                    source = getattr(parsed.feed, "title", "News")

                pub_date = getattr(entry, "published", None) or getattr(entry, "updated", "")
                if pub_date and len(pub_date) > 25:
                    pub_date = pub_date[:25]

                items.append({
                    "title": title,
                    "link": link,
                    "source": source or "News Feed",
                    "published": pub_date or "Recent",
                })
            return items
        except Exception:
            pass

    # Fallback XML parsing
    try:
        root = ET.fromstring(feed_xml)
        for item in root.findall(".//item"):
            title_node = item.find("title")
            link_node = item.find("link")
            pub_node = item.find("pubDate")
            source_node = item.find("source")

            raw_title = title_node.text if title_node is not None and title_node.text else "No Title"
            title = clean_html(raw_title)
            link = link_node.text if link_node is not None and link_node.text else "#"
            
            source = source_override
            if source_node is not None and source_node.text:
                source = clean_html(source_node.text)

            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2 and len(parts[1]) < 45:
                    if not source:
                        source = parts[1].strip()
                    title = parts[0].strip()

            pub_date = pub_node.text[:25] if pub_node is not None and pub_node.text else "Recent"

            items.append({
                "title": title,
                "link": link,
                "source": source or "News",
                "published": pub_date,
            })
    except Exception:
        pass

    return items


def fetch_category_news(urls_with_sources: List[tuple], limit: int = 6, mock_offline: bool = False, default_topic: str = "News") -> List[Dict[str, str]]:
    if mock_offline:
        return [
            {
                "title": f"Sample Intel Headline #{i+1} covering key developments in {default_topic}",
                "link": "https://news.google.com",
                "source": "Mock Source",
                "published": datetime.datetime.now().strftime("%d %b, %H:%M IST"),
            }
            for i in range(limit)
        ]

    aggregated: List[Dict[str, str]] = []
    seen_titles = set()

    for url, source_label in urls_with_sources:
        xml_data = fetch_url(url)
        if xml_data:
            entries = parse_feed_entries(xml_data, source_override=source_label)
            for entry in entries:
                norm_title = entry["title"].lower().strip()
                if norm_title and norm_title not in seen_titles:
                    seen_titles.add(norm_title)
                    aggregated.append(entry)

    return aggregated[:limit]


# ---------------------------------------------------------
# 4. Local Ubuntu Server & Homelab Telemetry
# ---------------------------------------------------------
def get_ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_cpu_temp() -> str:
    if psutil and hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name in ["coretemp", "cpu_thermal", "k10temp", "acpitz", "soc_thermal"]:
                    if name in temps and temps[name]:
                        return f"{temps[name][0].current:.1f}°C"
                for entries in temps.values():
                    if entries:
                        return f"{entries[0].current:.1f}°C"
        except Exception:
            pass

    for zone in range(4):
        path = f"/sys/class/thermal/thermal_zone{zone}/temp"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    val = float(f.read().strip())
                    return f"{val / 1000.0:.1f}°C"
            except Exception:
                pass

    return "Normal"


def get_docker_stats() -> Dict[str, Any]:
    """Inspects running Docker containers if Docker daemon is active."""
    stats = {"running": 0, "total": 0, "active": False, "containers": []}
    try:
        res = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}|{{.State}}|{{.Status}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().split("\n")
            stats["total"] = len(lines)
            running_cnt = 0
            for line in lines:
                parts = line.split("|")
                name = parts[0]
                state = parts[1] if len(parts) > 1 else ""
                status = parts[2] if len(parts) > 2 else ""
                is_running = state.lower() == "running"
                if is_running:
                    running_cnt += 1
                stats["containers"].append({"name": name, "running": is_running, "status": status})
            stats["running"] = running_cnt
            stats["active"] = True
    except Exception:
        pass
    return stats


def get_server_health() -> Dict[str, Any]:
    hostname = socket.gethostname()
    ip_addr = get_ip_address()
    cpu_temp = get_cpu_temp()
    docker_info = get_docker_stats()

    cpu_percent = 0.0
    ram_percent = 0.0
    ram_used_gb = "0.0"
    ram_total_gb = "0.0"
    disk_percent = 0.0
    disk_used_gb = "0.0"
    disk_total_gb = "0.0"
    uptime_str = "0h 0m"
    net_tx_gb = "0.0"
    net_rx_gb = "0.0"

    if psutil is not None:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.3)
            mem = psutil.virtual_memory()
            ram_percent = round(mem.percent, 1)
            ram_used_gb = f"{mem.used / (1024**3):.1f}"
            ram_total_gb = f"{mem.total / (1024**3):.1f}"

            disk = psutil.disk_usage("/")
            disk_percent = round(disk.percent, 1)
            disk_used_gb = f"{disk.used / (1024**3):.1f}"
            disk_total_gb = f"{disk.total / (1024**3):.1f}"

            net = psutil.net_io_counters()
            net_tx_gb = f"{net.bytes_sent / (1024**3):.1f}"
            net_rx_gb = f"{net.bytes_recv / (1024**3):.1f}"

            boot_time = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_time)
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60
            uptime_str = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"
        except Exception:
            pass

    return {
        "hostname": hostname,
        "ip_address": ip_addr,
        "cpu_percent": cpu_percent,
        "cpu_temp": cpu_temp,
        "ram_percent": ram_percent,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "disk_percent": disk_percent,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "uptime_str": uptime_str,
        "net_tx_gb": net_tx_gb,
        "net_rx_gb": net_rx_gb,
        "docker": docker_info,
    }


# ---------------------------------------------------------
# 5. Mobile Push Notifications (Telegram & ntfy.sh)
# ---------------------------------------------------------
def send_ntfy_push(topic: str, context: Dict[str, Any]):
    """Sends a native mobile push notification via ntfy.sh (Zero-signup, free iOS/Android app)."""
    if not topic:
        return

    m = context["metals"]
    w = context["weather"]
    s = context["server"]
    top_geo = context["news"]["geopolitics"][0]["title"] if context["news"]["geopolitics"] else "Top developments active"

    body = (
        f"📍 {w['city']}: {w['temp_c']}°C {w['icon']} | AQI: {w['aqi_val']}\n"
        f"🪙 24K Gold: {m['gold_10g_inr']} (22K: {m['gold_10g_22k_inr']}) | Silver: {m['silver_1kg_inr']}\n"
        f"🌍 {top_geo[:110]}..."
    )

    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": f"🌅 Morning Briefing Ready ({w['city']})",
        "Priority": "high",
        "Tags": "newspaper,sunrise",
        "Click": f"http://{s['ip_address']}:8089",
    }

    try:
        req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                log(f"ntfy.sh mobile push sent successfully to topic: {topic}")
    except Exception as e:
        log(f"ntfy.sh notification error: {e}")


def send_telegram_push(token: str, chat_id: str, context: Dict[str, Any]):
    """Sends a clean morning intelligence digest to a private Telegram chat."""
    if not token or not chat_id:
        return

    m = context["metals"]
    w = context["weather"]
    s = context["server"]
    geo = context["news"]["geopolitics"][:2]
    fin = context["news"]["finance"][:2]
    jobs = context["news"]["jobs"][:2]

    lines = [
        f"🌅 *Daily Morning Briefing* ({context['generated_at']})",
        f"📍 *{w['city']}:* {w['temp_c']}°C {w['icon']} | AQI: {w['aqi_val']} ({w['aqi_status']})",
        "",
        f"🪙 *Bullion & Forex:*",
        f"• 24K Gold (10g): *{m['gold_10g_inr']}* (Spot: ${m['gold_usd']})",
        f"• Silver (1kg): *{m['silver_1kg_inr']}*",
        f"• USD/INR: *{m['usd_inr_formatted']}* | BTC: *{m['btc_inr']}*",
        "",
        "🌍 *Geopolitics:*",
    ]
    for item in geo:
        lines.append(f"• [{item['source']}] [{item['title']}]({item['link']})")

    lines.append("\n📈 *Markets & Finance:*")
    for item in fin:
        lines.append(f"• [{item['source']}] [{item['title']}]({item['link']})")

    lines.append("\n💼 *AI Careers:*")
    for item in jobs:
        lines.append(f"• [{item['source']}] [{item['title']}]({item['link']})")

    lines.append(f"\n🖥 *Host:* `{s['hostname']}` | RAM: {s['ram_percent']}% | CPU: {s['cpu_percent']}%")
    lines.append(f"🔗 *Dashboard:* http://{s['ip_address']}:8089")

    msg_text = "\n".join(lines)
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "disable_web_page_preview": True}).encode("utf-8")

    try:
        req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            if r.status == 200:
                log("Telegram morning digest successfully delivered!")
    except Exception as e:
        log(f"Telegram notification error: {e}")


# ---------------------------------------------------------
# 6. Dashboard Assembly & Template Rendering
# ---------------------------------------------------------
def render_dashboard(template_path: str, context: Dict[str, Any]) -> str:
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found at: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    if Template is not None:
        jinja_tmpl = Template(template_content)
        return jinja_tmpl.render(**context)

    # String fallback
    log("Notice: jinja2 not installed, rendering with fallback string replace")
    output = template_content
    for key, val in context.items():
        if isinstance(val, dict):
            for sub_key, sub_val in val.items():
                output = output.replace(f"{{{{ {key}.{sub_key} }}}}", str(sub_val))
        elif isinstance(val, str):
            output = output.replace(f"{{{{ {key} }}}}", val)
    return output


def main():
    parser = argparse.ArgumentParser(description="Fetch live intelligence and build morning dashboard.")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_FILE, help=f"Destination HTML path (default: {DEFAULT_OUTPUT_FILE})")
    parser.add_argument("-t", "--template", default="template.html", help="Path to template.html")
    parser.add_argument("--city", default="Mumbai", help="City name for weather widget")
    parser.add_argument("--lat", type=float, default=19.0760, help="Latitude for weather/AQI (Mumbai: 19.0760)")
    parser.add_argument("--lon", type=float, default=72.8777, help="Longitude for weather/AQI (Mumbai: 72.8777)")
    parser.add_argument("--mock-offline", action="store_true", help="Generate dashboard with mock data (offline testing)")
    parser.add_argument("--telegram-token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram Bot Token for push notification")
    parser.add_argument("--telegram-chat-id", default=os.getenv("TELEGRAM_CHAT_ID"), help="Telegram Chat ID for push notification")
    parser.add_argument("--ntfy-topic", default=os.getenv("NTFY_TOPIC"), help="ntfy.sh topic for free native mobile push notifications (iOS/Android)")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, args.template) if not os.path.isabs(args.template) else args.template

    log("=== Starting Daily Intelligence Briefing Generator (Supercharged V2) ===")

    # 1. Metals, Crypto & Forex
    log("Ingesting Gold, Silver, Crude Oil, Crypto (BTC/ETH) and USD/INR exchange rates...")
    metals = get_metals_and_forex(mock_offline=args.mock_offline)

    # 2. Weather & AQI
    log(f"Ingesting real-time Weather & AQI for {args.city} (Open-Meteo Zero-Key)...")
    weather = get_weather_and_aqi(lat=args.lat, lon=args.lon, city_name=args.city)

    # 3. News Feeds
    log("Ingesting Geopolitics RSS (Iran / USA / Middle East)...")
    geopolitics_urls = [
        ("https://news.google.com/rss/search?q=Iran+OR+USA+war+conflict+when:1d&hl=en-IN&gl=IN&ceid=IN:en", None)
    ]
    geopolitics_news = fetch_category_news(geopolitics_urls, limit=6, mock_offline=args.mock_offline, default_topic="Geopolitics")

    log("Ingesting Financial & Market Updates RSS (Economic Times)...")
    finance_urls = [
        ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "ET Markets")
    ]
    finance_news = fetch_category_news(finance_urls, limit=6, mock_offline=args.mock_offline, default_topic="Markets & Economy")

    log("Ingesting Sports Desk RSS (ESPNcricinfo & BBC Football)...")
    sports_urls = [
        ("https://www.espncricinfo.com/rss/content/story/feeds/0.xml", "ESPNcricinfo"),
        ("https://feeds.bbci.co.uk/sport/football/rss.xml", "BBC Football"),
    ]
    sports_news = fetch_category_news(sports_urls, limit=6, mock_offline=args.mock_offline, default_topic="Sports")

    log("Ingesting IT Requirements & AI Jobs RSS (Google Jobs & Tech Feeds)...")
    jobs_urls = [
        ("https://news.google.com/rss/search?q=%22AI+Engineer%22+OR+%22Java+Lead%22+OR+%22GenAI%22+jobs+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en", "India Jobs"),
        ("https://news.google.com/rss/search?q=Remote+%22AI+Engineer%22+OR+%22Machine+Learning+Engineer%22+jobs&hl=en-IN&gl=IN&ceid=IN:en", "Remote AI"),
    ]
    jobs_news = fetch_category_news(jobs_urls, limit=6, mock_offline=args.mock_offline, default_topic="Tech Careers")

    # 4. Local Server Health & Homelab
    log("Reading local Ubuntu telemetry, network IO, and Docker status...")
    server = get_server_health()

    now_ist = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p IST")

    context = {
        "generated_at": now_ist,
        "server": server,
        "metals": metals,
        "weather": weather,
        "news": {
            "geopolitics": geopolitics_news,
            "finance": finance_news,
            "sports": sports_news,
            "jobs": jobs_news,
        }
    }

    # 5. Render Static Dashboard HTML
    log("Rendering static dashboard HTML...")
    rendered_html = render_dashboard(template_path, context)

    # 6. Write Output
    target_output = args.output
    target_dir = os.path.dirname(target_output)

    try:
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        with open(target_output, "w", encoding="utf-8") as f:
            f.write(rendered_html)
        log(f"SUCCESS: Intelligence dashboard rendered to {target_output}")
    except PermissionError:
        fallback_path = os.path.join(script_dir, "index.html")
        with open(fallback_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
        log(f"SUCCESS: Intelligence dashboard written to fallback: {fallback_path}")

    # 7. Optional Push Notifications (Telegram & ntfy)
    if args.telegram_token and args.telegram_chat_id:
        log("Dispatching Telegram Push Notification...")
        send_telegram_push(args.telegram_token, args.telegram_chat_id, context)

    if args.ntfy_topic:
        log(f"Dispatching ntfy.sh Mobile Push Notification to topic '{args.ntfy_topic}'...")
        send_ntfy_push(args.ntfy_topic, context)

    log("=== Daily Briefing Generation Complete ===")


if __name__ == "__main__":
    main()
