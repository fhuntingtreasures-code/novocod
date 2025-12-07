import os
import time
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PRODUCT_URLS = [
    # Produtos originais
    "https://mercadolivre.com/sec/2THbjvB",
    "https://mercadolivre.com/sec/1u3kd9j",
    "https://mercadolivre.com/sec/1vLVUPn",
    "https://mercadolivre.com/sec/2Yw346j",
    "https://mercadolivre.com/sec/2bR51rv",
    "https://mercadolivre.com/sec/2uL8hKK",
    "https://mercadolivre.com/sec/2437HL5",
    "https://mercadolivre.com/sec/1axQoSC",
    "https://mercadolivre.com/sec/183HpZX",
    "https://mercadolivre.com/sec/18BU8FD",
    # Produtos femininos (maquiagem, roupas, sapatos, etc.)
    "https://mercadolivre.com/sec/2beXprk",
    "https://mercadolivre.com/sec/1aqQLqv",
    "https://mercadolivre.com/sec/31YsKvo",
    "https://mercadolivre.com/sec/2AVifSy",
    "https://mercadolivre.com/sec/1nmWvuU",
    "https://mercadolivre.com/sec/2uK4uTq",
    "https://mercadolivre.com/sec/2JgrUn9",
    "https://mercadolivre.com/sec/1Vv9N1F",
    "https://mercadolivre.com/sec/1JktrMb",
    "https://mercadolivre.com/sec/1AWpUYN",
    "https://mercadolivre.com/sec/1NGNRJu",
    "https://mercadolivre.com/sec/1yckZsz",
    "https://mercadolivre.com/sec/2LZqRKT",
    "https://mercadolivre.com/sec/2T4am8T",
    "https://mercadolivre.com/sec/1cFAv8j",
    "https://mercadolivre.com/sec/2RqPpxE",
    "https://mercadolivre.com/sec/1z3dwkc",
    "https://mercadolivre.com/sec/2dxpd2v",
    "https://mercadolivre.com/sec/2LCkd5x",
    "https://mercadolivre.com/sec/1LUtnGi",
    "https://mercadolivre.com/sec/2b56rSp",
    "https://mercadolivre.com/sec/1aiUHvX",
    "https://mercadolivre.com/sec/24rfdVW",
    "https://mercadolivre.com/sec/1AcMHsC",
    "https://mercadolivre.com/sec/1oVARBt",
    "https://mercadolivre.com/sec/316uyQT",
    "https://mercadolivre.com/sec/1iVGviS",
]

HISTORY_FILE = "ml_history.json"
MIN_DISCOUNT_PERCENT = 20
SLEEP_SECONDS = 1800

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def save_history(hist):
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f, indent=2)


def extract_price(soup):
    price = try_extract_from_meta(soup)
    if price is not None:
        return price
    
    price = try_extract_andes_money(soup)
    if price is not None:
        return price
    
    price = try_extract_from_json_ld(soup)
    if price is not None:
        return price
    
    price = try_extract_from_text_patterns(soup)
    if price is not None:
        return price
    
    return None


def try_extract_from_meta(soup):
    meta = soup.select_one('meta[itemprop="price"]')
    if meta and meta.get('content'):
        try:
            return float(meta['content'])
        except ValueError:
            pass
    
    og_price = soup.select_one('meta[property="product:price:amount"]')
    if og_price and og_price.get('content'):
        try:
            return float(og_price['content'])
        except ValueError:
            pass
    return None


def try_extract_andes_money(soup):
    price_container = soup.select_one('.ui-pdp-price__second-line .andes-money-amount')
    if not price_container:
        price_container = soup.select_one('.andes-money-amount--cents-superscript')
    if not price_container:
        price_container = soup.select_one('.andes-money-amount')
    
    if price_container:
        fraction = price_container.select_one('.andes-money-amount__fraction')
        cents = price_container.select_one('.andes-money-amount__cents')
        
        if fraction:
            fraction_text = fraction.get_text().strip()
            fraction_text = re.sub(r'[^\d]', '', fraction_text)
            
            if fraction_text:
                price_value = float(fraction_text)
                
                if cents:
                    cents_text = cents.get_text().strip()
                    cents_text = re.sub(r'[^\d]', '', cents_text)
                    if cents_text:
                        price_value += float(cents_text) / 100
                
                return price_value
    return None


def try_extract_from_json_ld(soup):
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                if 'offers' in data:
                    offers = data['offers']
                    if isinstance(offers, dict) and 'price' in offers:
                        return float(offers['price'])
                    elif isinstance(offers, list) and offers and 'price' in offers[0]:
                        return float(offers[0]['price'])
                if 'price' in data:
                    return float(data['price'])
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


def try_extract_from_text_patterns(soup):
    price_patterns = [
        r'R\$\s*([\d.,]+)',
        r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
    ]
    
    price_elements = soup.select('.price, .ui-pdp-price, [class*="price"]')
    for elem in price_elements:
        text = elem.get_text()
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                price_text = match.group(1)
                price_text = price_text.replace('.', '').replace(',', '.')
                try:
                    price = float(price_text)
                    if price > 0:
                        return price
                except ValueError:
                    continue
    return None


def extract_title(soup):
    title_selectors = [
        'h1.ui-pdp-title',
        'h1[class*="title"]',
        'meta[property="og:title"]',
        'title',
    ]
    
    for selector in title_selectors:
        if selector.startswith('meta'):
            elem = soup.select_one(selector)
            if elem and elem.get('content'):
                return elem['content'].strip()
        else:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text().strip()
    return "Produto Mercado Livre"


def fetch_product_info(url):
    try:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        
        if response.status_code != 200:
            print(f"  HTTP {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        title = extract_title(soup)
        price = extract_price(soup)
        final_url = response.url
        
        if price is None:
            print(f"  Preco nao encontrado na pagina")
            return None
        
        return {
            "title": title,
            "price": price,
            "url": final_url,
            "original_url": url
        }
        
    except requests.RequestException as e:
        print(f"  Erro de requisicao: {e}")
        return None
    except Exception as e:
        print(f"  Erro: {e}")
        return None


def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def send_telegram(text, use_html=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML" if use_html else "Markdown",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"  Telegram erro: {response.status_code} - {response.text}")
            return False
        return True
    except Exception as e:
        print(f"  Telegram erro: {e}")
        return False


def format_message(title, old_price, new_price, discount, link):
    title_short = title[:100] + "..." if len(title) > 100 else title
    return (
        f"*OFERTA MERCADO LIVRE!*\n"
        f"*{title_short}*\n\n"
        f"De ~R$ {old_price:,.2f}~ por *R$ {new_price:,.2f}*\n"
        f"*Desconto*: {discount:.0f}%\n\n"
        f"[Ver oferta]({link})\n\n"
        f"Pode acabar a qualquer momento!"
    )


def format_product_message(title, price, link):
    title_short = title[:100] + "..." if len(title) > 100 else title
    title_escaped = escape_html(title_short)
    return (
        f"<b>{title_escaped}</b>\n\n"
        f"<b>Preco:</b> R$ {price:,.2f}\n\n"
        f"<a href=\"{link}\">Comprar agora</a>"
    )


def post_all_products():
    print("\n" + "=" * 50)
    print("POSTANDO TODOS OS PRODUTOS NO CANAL...")
    print("=" * 50)
    
    products_posted = 0
    
    for url in PRODUCT_URLS:
        url_key = get_url_key(url)
        print(f"\nBuscando: {url_key}")
        
        try:
            data = fetch_product_info(url)
            if not data:
                print(f"  Falha ao obter informacoes")
                continue
            
            title = data["title"]
            price = data["price"]
            affiliate_url = data["original_url"]
            
            print(f"  {title[:50]}...")
            print(f"  Preco: R$ {price:,.2f}")
            
            msg = format_product_message(title, price, affiliate_url)
            if send_telegram(msg, use_html=True):
                products_posted += 1
                print(f"  POSTADO NO CANAL!")
            else:
                print(f"  Falha ao postar")
            
            time.sleep(2)
            
        except Exception as e:
            print(f"  Erro: {e}")
    
    print(f"\n{products_posted} produtos postados no canal!")
    print("=" * 50)


def get_url_key(url):
    return url.split('/')[-1]


def main_loop():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERRO: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID devem estar configurados como secrets.")
        print("Configure-os no painel de Secrets do Replit antes de executar o bot.")
        return
    
    print("BOT DE PROMOCOES ML INICIADO (Web Scraping)")
    print(f"Monitorando {len(PRODUCT_URLS)} produtos")
    print(f"Desconto minimo: {MIN_DISCOUNT_PERCENT}%")
    print(f"Intervalo: {SLEEP_SECONDS/60:.0f} minutos")
    print("-" * 50)
    
    post_all_products()
    
    history = load_history()

    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Varredura iniciada...")

        for url in PRODUCT_URLS:
            url_key = get_url_key(url)
            print(f"\nVerificando: {url_key}")
            
            try:
                data = fetch_product_info(url)
                if not data:
                    print(f"  Falha ao obter informacoes")
                    continue

                title = data["title"]
                current_price = data["price"]
                affiliate_url = data["original_url"]

                print(f"  {title[:50]}...")
                print(f"  Preco atual: R$ {current_price:,.2f}")

                if url_key not in history:
                    history[url_key] = {"prices": [], "title": title}
                    print(f"  Primeiro registro - adicionado ao historico")

                prices = history[url_key]["prices"]
                prices.append(current_price)
                history[url_key]["title"] = title

                if len(prices) > 200:
                    prices.pop(0)

                if len(prices) < 2:
                    print(f"  Aguardando mais dados de preco...")
                    continue

                avg_price = sum(prices[:-1]) / len(prices[:-1])
                discount = (avg_price - current_price) / avg_price * 100

                print(f"  Media historica: R$ {avg_price:,.2f}")
                print(f"  Desconto: {discount:.1f}%")

                if discount >= MIN_DISCOUNT_PERCENT:
                    msg = format_message(title, avg_price, current_price, discount, affiliate_url)
                    send_telegram(msg)
                    print(f"  ENVIADO PARA O CANAL!")

            except Exception as e:
                print(f"  Erro no produto: {e}")

        save_history(history)
        print(f"\nAguardando {SLEEP_SECONDS/60:.0f} minutos...")
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main_loop()
