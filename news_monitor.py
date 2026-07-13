import os
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# === CONFIGURAZIONE ===
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Finestra temporale: controlla solo articoli delle ultime 4 ore
HOURS_BACK = 4

# Feed RSS da monitorare
# Google News RSS permette query con keyword (come NewsAPI ma gratis!)
FEEDS = [
    # Google News - query mirate su Iran + petrolio/guerra
    "https://news.google.com/rss/search?q=Iran+(oil+OR+war+OR+sanctions+OR+Hormuz+OR+tanker+OR+crude+OR+attack)&hl=en&gl=US&ceid=US:en",
    # Google News - query più ampia sul Medio Oriente
    "https://news.google.com/rss/search?q=%22Middle+East%22+(oil+OR+crude+OR+OPEC+OR+sanctions)&hl=en&gl=US&ceid=US:en",
    # Reuters - World News (fonte diretta, altissima qualità)
    "https://www.reutersagency.com/feed/",
    # Al Jazeera - Middle East (copertura eccellente sulla regione)
    "https://www.aljazeera.com/xml/middleeast.rss",
]

# Keyword che indicano impatto sul petrolio (per filtrare i risultati dei feed generici)
OIL_IMPACT_KEYWORDS = [
    "oil", "crude", "brent", "wti", "petroleum", "barrel", "sanction",
    "tanker", "hormuz", "export", "opec", "pipeline", "refinery",
    "embargo", "blockade", "strike", "tehran", "iran",
    "surge", "spike", "price", "market", "energy"
]

# Falsi positivi da escludere
EXCLUDE_KEYWORDS = [
    "kushinagar", "air force one", "ram temple", "modi", "airfare",
    "cryptocurrency", "crypto", "boomerang", "twitter", "censor",
    "referee", "world cup", "fifa", "bollywood", "nfl", "nba",
    "fashion", "celebrity", "recipe", "cooking"
]

def translate_to_italian(text):
    """Traduce un testo da inglese a italiano usando MyMemory API (gratis)"""
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
    """Fa il parsing delle date dai feed RSS (formati diversi)"""
    if not date_str:
        return None
    
    # Formato standard RSS (RFC 2822)
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    
    # Formato ISO (alcuni feed)
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
    """Scarica e parsifica tutti i feed RSS"""
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
                    'source': source_name,
                    'feed_url': feed_url
                })
        except Exception as e:
            print(f"  ✗ Errore feed {feed_url[:50]}: {e}")
    
    return all_entries

def is_recent(published_str, hours=4):
    """Controlla se l'articolo è delle ultime X ore"""
    pub_date = parse_feed_date(published_str)
    if pub_date is None:
        # Se non riusciamo a parsare la data, includiamo per sicurezza
        # (alcuni feed non hanno data)
        return True
    
    # Assicuriamoci che abbia il timezone
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(hours=hours)
    return pub_date >= cutoff_date

def filter_articles(entries):
    """Filtra articoli per data, keyword e falsi positivi"""
    relevant = []
    seen_links = set()
    
    for entry in entries:
        link = entry.get('link', '')
        
        # Evita duplicati (stesso articolo da feed diversi)
        if link in seen_links:
            continue
        
        # Filtro 1: deve essere recente
        if not is_recent(entry.get('published', ''), HOURS_BACK):
            continue
        
        # Prepara il testo per il filtraggio
        title = entry.get('title', '') or ''
        description = entry.get('description', '') or ''
        text = f"{title} {description}".lower()
        
        # Filtro 2: escludi falsi positivi
        if any(exclude in text for exclude in EXCLUDE_KEYWORDS):
            continue
        
        # Filtro 3: verifica keyword positive
        if any(keyword in text for keyword in OIL_IMPACT_KEYWORDS):
            seen_links.add(link)
            relevant.append(entry)
    
    return relevant

def send_telegram_message(text):
    """Invia un messaggio al bot Telegram"""
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
    print(f"Finestra temporale: ultime {HOURS_BACK} ore")
    
    # Scarica tutti i feed
    all_entries = fetch_all_feeds()
    print(f"\n📊 Totale articoli grezzi: {len(all_entries)}")
    
    # Filtra
    relevant = filter_articles(all_entries)
    print(f"✅ Articoli rilevanti dopo filtri: {len(relevant)}")
    
    if not relevant:
        print("Nessuna notizia rilevante. Esco.")
        return
    
    # Ordina per data (più recenti prima) - approssimativo
    # Invia massimo 5 notizie per evitare spam
    to_send = relevant[:5]
    print(f"\n📤 Invio {len(to_send)} notifiche a Telegram...")
    
    for article in to_send:
        title_en = article.get("title", "Senza titolo")
        description_en = article.get("description", "") or ""
        url = article.get("link", "")
        source = article.get("source", "Fonte sconosciuta")
        
        # Pulisci la descrizione (spesso contiene HTML)
        import re
        description_en = re.sub(r'<[^>]+>', '', description_en)
        description_en = description_en.strip()[:300]
        
        # Traduci
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
