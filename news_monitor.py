import os
import requests
import feedparser
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# === CONFIGURAZIONE ===
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HOURS_BACK = 4  # Controlla le ultime 4 ore

# Feed RSS da monitorare (100% gratis, nessun limite)
FEEDS = [
    "https://news.google.com/rss/search?q=Iran+(oil+OR+war+OR+sanctions+OR+Hormuz+OR+tanker+OR+crude+OR+attack)&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=%22Middle+East%22+(oil+OR+crude+OR+OPEC+OR+sanctions)&hl=en&gl=US&ceid=US:en",
    "https://www.aljazeera.com/xml/middleeast.rss",
]

OIL_IMPACT_KEYWORDS = [
    "oil", "crude", "brent", "wti", "petroleum", "barrel", "sanction",
    "tanker", "hormuz", "export", "opec", "pipeline", "refinery",
    "embargo", "blockade", "strike", "tehran", "iran", "energy"
]

EXCLUDE_KEYWORDS = [
    "kushinagar", "air force one", "ram temple", "modi", "airfare",
    "cryptocurrency", "crypto", "boomerang", "twitter", "censor",
    "referee", "world cup", "fifa", "bollywood", "nfl", "nba"
]

def translate_to_italian(text):
    if not text:
        return ""
    try:
        url = "https://api.mymemory.translated.net/get"
        response = requests.get(url, params={"q": text[:450], "langpair": "en|it"}, timeout=10)
        if response.status_code == 200:
            translated = response.json().get("responseData", {}).get("translatedText", "")
            if translated and translated.lower() != text.lower():
                return translated
    except Exception as e:
        print(f"Errore traduzione: {e}")
    return text

def parse_feed_date(date_str):
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None

def fetch_all_feeds():
    all_entries = []
    for feed_url in FEEDS:
        try:
            print(f"📡 Scaricamento feed: {feed_url[:60]}...")
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                print(f"  ⚠️ Feed non valido o vuoto")
                continue
            source_name = feed.feed.get('title', 'Fonte sconosciuta')
            print(f"  ✓ Trovati {len(feed.entries)} articoli da {source_name}")
            for entry in feed.entries:
                all_entries.append({
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'description': entry.get('summary', entry.get('description', '')),
                    'published': entry.get('published', entry.get('updated', '')),
                    'source': source_name
                })
        except Exception as e:
            print(f"  ✗ Errore feed: {e}")
    return all_entries

def is_recent(published_str, hours=4):
    pub_date = parse_feed_date(published_str)
    if pub_date is None:
        return True
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    cutoff_date = datetime.now(timezone.utc) - timedelta(hours=hours)
    return pub_date >= cutoff_date

def filter_articles(entries):
    relevant = []
    seen_links = set()
    for entry in entries:
        link = entry.get('link', '')
        if link in seen_links:
            continue
        if not is_recent(entry.get('published', ''), HOURS_BACK):
            continue
        title = entry.get('title', '') or ''
        description = entry.get('description', '') or ''
        text = f"{title} {description}".lower()
        if any(exclude in text for exclude in EXCLUDE_KEYWORDS):
            continue
        if any(keyword in text for keyword in OIL_IMPACT_KEYWORDS):
            seen_links.add(link)
            relevant.append(entry)
    return relevant

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()

def main():
    print(f"[{datetime.now(timezone.utc)}] Avvio monitoraggio RSS...")
    all_entries = fetch_all_feeds()
    print(f"\n📊 Totale articoli grezzi: {len(all_entries)}")
    
    relevant = filter_articles(all_entries)
    print(f"✅ Articoli rilevanti dopo filtri: {len(relevant)}")
    
    if not relevant:
        print("Nessuna notizia rilevante. Esco.")
        return
    
    to_send = relevant[:5]
    print(f"\n📤 Invio {len(to_send)} notifiche a Telegram...")
    
    for article in to_send:
        title_en = article.get("title", "Senza titolo")
        description_en = article.get("description", "") or ""
        url = article.get("link", "")
        source = article.get("source", "Fonte sconosciuta")
        
        # Pulisce la descrizione dall'HTML
        description_en = re.sub(r'<[^>]+>', '', description_en).strip()[:300]
        
        title_it = translate_to_italian(title_en)
        desc_it = translate_to_italian(description_en) if description_en else ""
        
        message = (
            f"🛢️ <b>ALLERTA PETROLIO - IRAN</b>\n\n"
            f"📰 <b>{title_it}</b>\n\n"
        )
        if desc_it:
            message += f"{desc_it}\n\n"
        message += (
            f"🔗 <a href='{url}'>Leggi articolo originale</a>\n"
            f"📡 Fonte: {source}"
        )
        
        try:
            send_telegram_message(message)
            print(f"✓ Inviato: {title_en[:60]}...")
        except Exception as e:
            print(f"✗ Errore invio Telegram: {e}")

if __name__ == "__main__":
    main()
