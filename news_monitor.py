import os
import requests
from datetime import datetime, timedelta, timezone

# === CONFIGURAZIONE ===
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Query semplificata
SEARCH_QUERY = "Iran AND (oil OR war OR sanctions OR Hormuz OR tanker OR attack OR crude)"
LANGUAGE = "en"
HOURS_BACK = 48  # Aumentato a 48 ore per il debug

# Keyword che indicano impatto sul prezzo del petrolio
OIL_IMPACT_KEYWORDS = [
    "oil", "crude", "brent", "wti", "petroleum", "barrel", "sanction",
    "tanker", "hormuz", "export", "opec", "pipeline", "refinery",
    "embargo", "blockade", "attack", "strike", "war", "conflict",
    "surge", "spike", "price", "market"
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
        "pageSize": 100,
        "apiKey": NEWS_API_KEY
    }
    
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    if data.get("status") != "ok":
        print(f"⚠️ NewsAPI status not ok: {data}")
        raise Exception(f"NewsAPI error: {data.get('message')}")
    
    return data.get("articles", [])

def parse_date(published_str):
    """Fa il parsing della data in vari formati"""
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z"
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

def is_recent(published_str, hours=48):
    """Controlla se l'articolo è stato pubblicato nelle ultime X ore"""
    pub_date = parse_date(published_str)
    if pub_date is None:
        print(f"  ⚠️ Errore parsing data: {published_str}")
        return True  # Includiamo per sicurezza
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(hours=hours)
    is_recent = pub_date >= cutoff_date
    
    if not is_recent:
        print(f"  ❌ Troppo vecchio: {published_str} (cutoff: {cutoff_date.isoformat()})")
    
    return is_recent

def filter_relevant_articles(articles, debug=True):
    """Filtra solo articoli recenti e rilevanti per il petrolio"""
    relevant = []
    
    for i, article in enumerate(articles[:10]):  # Debug: solo i primi 10
        title = article.get('title', 'N/A')
        published = article.get('publishedAt', 'N/A')
        description = article.get('description', '') or ''
        
        print(f"\n--- Articolo {i+1} ---")
        print(f"Titolo: {title[:80]}")
        print(f"Data: {published}")
        
        # Filtro 1: data
        if not is_recent(published, HOURS_BACK):
            print(f"  ❌ Scartato: troppo vecchio")
            continue
        
        # Filtro 2: keyword
        text = f"{title} {description}".lower()
        found_keywords = [kw for kw in OIL_IMPACT_KEYWORDS if kw in text]
        
        if not found_keywords:
            print(f"  ❌ Scartato: nessuna keyword trovata")
            print(f"  Testo: {text[:100]}...")
        else:
            print(f"  ✅ Rilevante! Keyword: {found_keywords}")
            relevant.append(article)
    
    # Ora filtriamo tutti gli articoli (non solo i primi 10)
    all_relevant = []
    for article in articles:
        if not is_recent(article.get('publishedAt', ''), HOURS_BACK):
            continue
        
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
        if any(keyword in text for keyword in OIL_IMPACT_KEYWORDS):
            all_relevant.append(article)
    
    return all_relevant

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
    print(f"Orario attuale UTC: {datetime.now(timezone.utc).isoformat()}")
    print(f"Cutoff (ultime {HOURS_BACK} ore): {(datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)).isoformat()}")
    
    articles = fetch_news()
    print(f"\n📊 Trovati {len(articles)} articoli totali da NewsAPI")
    
    relevant = filter_relevant_articles(articles, debug=True)
    print(f"\n✅ Articoli rilevanti e recenti per il petrolio: {len(relevant)}")
    
    if not relevant:
        print("❌ Nessuna notizia rilevante nelle ultime ore. Esco.")
        return
    
    print(f"\n📤 Invio {len(relevant)} notifiche a Telegram...")
    
    for article in relevant[:20]:
        title_en = article.get("title", "Senza titolo")
        description_en = article.get("description", "") or ""
        url = article.get("url", "")
        source = article.get("source", {}).get("name", "Fonte sconosciuta")
        published = article.get("publishedAt", "")[:16].replace("T", " ")
        
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
