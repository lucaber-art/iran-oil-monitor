import os
import requests
from datetime import datetime, timedelta, timezone

# === CONFIGURAZIONE ===
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Query di ricerca
SEARCH_QUERY = "Iran AND (oil OR war OR sanctions OR Hormuz OR tanker OR attack OR crude)"
LANGUAGE = "en"
HOURS_BACK = 6  # ✅ Ottimizzato: solo notizie delle ultime 4 ore

# Keyword che indicano impatto sul prezzo del petrolio
OIL_IMPACT_KEYWORDS = [
    "oil", "crude", "brent", "wti", "petroleum", "barrel", "sanction",
    "tanker", "hormuz", "export", "opec", "pipeline", "refinery",
    "embargo", "blockade", "attack", "strike", "war", "conflict",
    "surge", "spike", "price", "market", "tehran"
]

# Parole chiave per escludere articoli non pertinenti (falsi positivi)
EXCLUDE_KEYWORDS = [
    "kushinagar", "air force one", "ram temple", "modi", "airfare",
    "cryptocurrency", "crypto", "boomerang", "twitter", "censor",
    "referee", "world cup", "fifa", "bollywood", "nfl", "nba"
]

def translate_to_italian(text):
    """Traduce un testo da inglese a italiano usando MyMemory API (gratis)"""
    if not text:
        return ""
    try:
        url = "https://api.mymemory.translated.net/get"
        response = requests.get(url, params={
            "q": text[:450],
            "langpair": "en|it"
        }, timeout=10)
        if response.status_code == 200:
            translated = response.json().get("responseData", {}).get("translatedText", "")
            if translated and translated.lower() != text.lower():
                return translated
    except Exception as e:
        print(f"Errore traduzione: {e}")
    return text

def fetch_news():
    """Recupera le notizie da NewsAPI"""
    url = "https://newsapi.org/v2/everything"
    
    params = {
        "q": SEARCH_QUERY,
        "language": LANGUAGE,
        "sortBy": "publishedAt",
        "pageSize": 50,  # Ridotto da 100 a 50 per velocità
        "apiKey": NEWS_API_KEY
    }
    
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    if data.get("status") != "ok":
        print(f"⚠️ NewsAPI error: {data}")
        raise Exception(f"NewsAPI error: {data.get('message')}")
    
    return data.get("articles", [])

def parse_date(published_str):
    """Fa il parsing della data"""
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(published_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None

def is_recent(published_str, hours=4):
    """Controlla se l'articolo è stato pubblicato nelle ultime X ore"""
    pub_date = parse_date(published_str)
    if pub_date is None:
        return True  # Se non possiamo parsare la data, includiamo per sicurezza
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(hours=hours)
    return pub_date >= cutoff_date

def filter_relevant_articles(articles):
    """Filtra solo articoli recenti e rilevanti per il petrolio"""
    relevant = []
    
    for article in articles:
        # Filtro 1: deve essere recente
        if not is_recent(article.get('publishedAt', ''), HOURS_BACK):
            continue
        
        # Filtro 2: deve contenere keyword rilevanti
        title = article.get('title', '') or ''
        description = article.get('description', '') or ''
        text = f"{title} {description}".lower()
        
        # Filtro 3: escludi falsi positivi
        if any(exclude in text for exclude in EXCLUDE_KEYWORDS):
            continue
        
        # Filtro 4: verifica presenza keyword positive
        if any(keyword in text for keyword in OIL_IMPACT_KEYWORDS):
            relevant.append(article)
    
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
    print(f"[{datetime.now(timezone.utc)}] Avvio monitoraggio...")
    
    articles = fetch_news()
    print(f"Trovati {len(articles)} articoli totali")
    
    relevant = filter_relevant_articles(articles)
    print(f"Articoli rilevanti (ultime {HOURS_BACK} ore): {len(relevant)}")
    
    if not relevant:
        print("Nessuna notizia rilevante. Esco.")
        return
    
    # Invia massimo 5 notizie per evitare spam
    max_notifications = 5
    to_send = relevant[:max_notifications]
    
    print(f"Invio {len(to_send)} notifiche a Telegram...")
    
    for article in to_send:
        title_en = article.get("title", "Senza titolo")
        description_en = article.get("description", "") or ""
        url = article.get("url", "")
        source = article.get("source", {}).get("name", "Fonte sconosciuta")
        published = article.get("publishedAt", "")[:16].replace("T", " ")
        
        # Traduci titolo e descrizione
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
            f"📡 Fonte: {source} | 🕐 {published} UTC"
        )
        
        try:
            send_telegram_message(message)
            print(f"✓ Inviato: {title_en[:60]}...")
        except Exception as e:
            print(f"✗ Errore invio: {e}")

if __name__ == "__main__":
    main()
