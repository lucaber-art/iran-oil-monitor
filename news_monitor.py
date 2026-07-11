import os
import requests
from datetime import datetime, timedelta, timezone

# === CONFIGURAZIONE ===
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Keyword per cercare notizie sulla guerra in Iran con impatto sul petrolio
SEARCH_QUERY = '(Iran OR "Middle East" OR "Strait of Hormuz" OR Tehran) AND (oil OR crude OR sanctions OR war OR attack OR conflict OR tanker)'
LANGUAGE = "en"
HOURS_BACK = 2  # Cerca articoli delle ultime 2 ore

# Keyword che indicano impatto sul prezzo del petrolio (per filtrare i risultati)
OIL_IMPACT_KEYWORDS = [
    "oil", "crude", "brent", "wti", "petroleum", "barrel", "sanction",
    "tanker", "hormuz", "export", "opec", "pipeline", "refinery",
    "embargo", "blockade", "attack", "strike", "war", "conflict",
    "surge", "spike", "price", "market"
]

def translate_to_italian(text):
    """Traduce un testo da inglese a italiano usando MyMemory API (gratis)"""
    try:
        url = "https://api.mymemory.translated.net/get"
        response = requests.get(url, params={
            "q": text[:450],  # limite API
            "langpair": "en|it"
        }, timeout=5)
        if response.status_code == 200:
            translated = response.json().get("responseData", {}).get("translatedText", "")
            if translated and translated.lower() != text.lower():
                return translated
    except Exception as e:
        print(f"Errore traduzione: {e}")
    return text  # fallback: restituisce l'originale

def fetch_news():
    """Recupera le notizie da NewsAPI delle ultime N ore"""
    url = "https://newsapi.org/v2/everything"
    from_date = (datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)).strftime("%Y-%m-%dT%H:%M:%S")
    
    params = {
        "q": SEARCH_QUERY,
        "language": LANGUAGE,
        "from": from_date,
        "sortBy": "publishedAt",
        "pageSize": 20,
        "apiKey": NEWS_API_KEY
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if data.get("status") != "ok":
        raise Exception(f"NewsAPI error: {data.get('message')}")
    
    return data.get("articles", [])

def filter_relevant_articles(articles):
    """Filtra solo articoli che parlano di petrolio/mercato"""
    relevant = []
    for article in articles:
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
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
    print(f"Articoli rilevanti per il petrolio: {len(relevant)}")
    
    if not relevant:
        print("Nessuna notizia rilevante. Esco.")
        return
    
    # Invia ogni articolo come messaggio separato
    for article in relevant:
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
