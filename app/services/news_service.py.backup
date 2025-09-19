import datetime
from dotenv import load_dotenv
import os
import feedparser
import re
from bs4 import BeautifulSoup
from langchain_anthropic import ChatAnthropic

load_dotenv()

# Postavite API ključ za Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Definicija RSS feedova za različite zemlje i kategorije
RSS_FEEDS = {
    "Hrvatska": [
        "https://vijesti.hrt.hr/rss",
        "https://www.index.hr/rss/vijesti",
        "https://www.tportal.hr/rss",
        "https://www.24sata.hr/feeds/news.xml",
        "https://www.vecernji.hr/feeds/latest",
    ],
    "Svijet": [
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.theguardian.com/world/rss",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.france24.com/en/rss",
    ],
    "Ekonomija": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "https://www.ft.com/world/economy?format=rss",
        "https://www.economist.com/finance-and-economics/rss.xml",
        "https://www.theguardian.com/business/economics/rss",
        "https://www.forbes.com/business/feed/",
    ],
    "Sport_HR": [  # Interni naziv za hrvatske sportske vijesti
        "https://www.index.hr/rss/sport",
        "https://sportske.jutarnji.hr/rss",
        "https://www.24sata.hr/feeds/sport.xml",
        "https://gol.dnevnik.hr/feeds/category/4.xml",
        "https://sportnet.rtl.hr/rss/sve-vijesti/",
    ],
    "Sport_World": [  # Interni naziv za svjetske sportske vijesti
        "https://www.espn.com/espn/rss/news",
        "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
        "https://www.skysports.com/rss/0,20514,11979,00.xml",
        "https://feeds.bbci.co.uk/sport/rss.xml",
        "https://api.foxsports.com/v1/rss?partnerKey=zBaFxRyGKCfxBagJG9b8pqLyndmvo7UU",
    ],
    "Slovenija": [
        "https://www.rtvslo.si/feeds/01.xml",
        "https://www.24ur.com/rss",
        "https://www.dnevnik.si/rss",
        "https://www.delo.si/rss/",
        "https://www.slovenskenovice.si/feed/",
    ],
    "Mađarska": [
        "https://www.origo.hu/contentpartner/rss/hircentrum/origo.xml",
        "https://hvg.hu/rss",
        "https://index.hu/24ora/rss/",
        "https://444.hu/feed",
        "https://magyarnarancs.hu/rss",
    ],
    "Italija": [
        "https://www.repubblica.it/rss/homepage/rss2.0.xml",
        "https://www.corriere.it/rss/homepage.xml",
        "https://www.ansa.it/sito/ansait_rss.xml",
        "https://www.ilfattoquotidiano.it/feed/",
        "https://www.lastampa.it/rss.xml",
    ],
    "Austrija": [
        "https://www.derstandard.at/rss",
        "https://www.krone.at/rss",
        "https://www.orf.at/rss/news",
        "https://www.tt.com/rss",
        "https://kurier.at/rss",
    ],
}

# Izvorni jezik za svaku kategoriju (potrebno za prevođenje)
IZVORNI_JEZIK = {
    "Hrvatska": "hr",
    "Svijet": "en",
    "Ekonomija": "en",
    "Sport_HR": "hr",
    "Sport_World": "en",
    "Sport": "mixed",
    "Slovenija": "sl",
    "Mađarska": "hu",
    "Italija": "it",
    "Austrija": "de",
    "Regija": "mixed",  # Nova kategorija s miješanim jezicima
}

def ocisti_html(html_tekst):
    """Uklanja HTML tagove iz teksta"""
    if not html_tekst:
        return ""
    
    # Koristi BeautifulSoup za čišćenje HTML-a
    soup = BeautifulSoup(html_tekst, 'html.parser')
    tekst = soup.get_text(separator=' ', strip=True)
    
    # Dodatno čišćenje
    tekst = re.sub(r'\s+', ' ', tekst)  # Uklanja višestruke razmake
    tekst = tekst.strip()
    
    return tekst

def dohvati_vijesti_iz_rss(kategorija, broj_vijesti=5):
    """
    Dohvaća vijesti iz RSS feedova za zadanu kategoriju,
    s jednakom distribucijom iz različitih izvora
    """
    try:
        feedovi = RSS_FEEDS.get(kategorija, [])
        if not feedovi:
            return None
        
        # Rječnik za praćenje vijesti iz svakog izvora
        vijesti_po_izvoru = {}
        broj_feedova = len(feedovi)
        
        # Dohvati vijesti iz svih feedova
        for feed_url in feedovi:
            try:
                feed = feedparser.parse(feed_url)
                feed_izvor = feed.feed.get('title', 'Nepoznat izvor')
                vijesti_po_izvoru[feed_izvor] = []
                
                for entry in feed.entries:
                    naslov = entry.get('title', 'Naslov nije dostupan')
                    
                    # Pokušaj dohvatiti opis na različite načine jer feedovi koriste različite formate
                    tekst = ''
                    if 'description' in entry:
                        tekst = entry.description
                    elif 'summary' in entry:
                        tekst = entry.summary
                    elif 'content' in entry and len(entry.content) > 0:
                        tekst = entry.content[0].value
                    else:
                        tekst = 'Opis nije dostupan'
                    
                    # Očisti HTML tagove iz teksta
                    tekst = ocisti_html(tekst)
                    
                    # Provjera da li vijest ima dovoljno sadržaja
                    if len(tekst) < 20 and 'nije dostupan' not in tekst:
                        tekst = 'Sadržaj nije dostupan. Kliknite na link za više informacija.'
                    
                    link = entry.get('link', '#')
                    
                    vijesti_po_izvoru[feed_izvor].append({
                        'naslov': naslov,
                        'tekst': tekst,
                        'izvor': feed_izvor,
                        'link': link
                    })
            
            except Exception as e:
                print(f"Greška pri dohvaćanju feeda {feed_url}: {str(e)}")
                continue
        
        # Uravnoteženi odabir vijesti iz svih izvora
        balansirane_vijesti = []
        
        # Odaberi samo aktivne izvore (one koji su vratili barem jednu vijest)
        aktivni_izvori = [izvor for izvor, vijesti in vijesti_po_izvoru.items() if vijesti]
        
        if not aktivni_izvori:
            return None
            
        # Izračunaj koliko vijesti uzeti iz svakog izvora
        vijesti_po_aktivnom_izvoru = max(1, min(int(broj_vijesti / len(aktivni_izvori)), 2))
        
        # Uzmi određeni broj vijesti iz svakog izvora
        for izvor in aktivni_izvori:
            vijesti_izvora = vijesti_po_izvoru[izvor][:vijesti_po_aktivnom_izvoru]
            balansirane_vijesti.extend(vijesti_izvora)
            
        # Ako nemamo dovoljno vijesti, dodaj još iz izvora s najviše vijesti
        if len(balansirane_vijesti) < broj_vijesti:
            najveci_izvor = max(vijesti_po_izvoru.items(), key=lambda x: len(x[1]))[0]
            vec_dodane = sum(1 for v in balansirane_vijesti if v['izvor'] == najveci_izvor)
            
            dodaj_jos = min(broj_vijesti - len(balansirane_vijesti), 
                            len(vijesti_po_izvoru[najveci_izvor]) - vec_dodane)
                            
            if dodaj_jos > 0:
                dodatne_vijesti = vijesti_po_izvoru[najveci_izvor][vec_dodane:vec_dodane+dodaj_jos]
                balansirane_vijesti.extend(dodatne_vijesti)
        
        # Ograniči na traženi broj vijesti
        return balansirane_vijesti[:broj_vijesti]
    
    except Exception as e:
        print(f"Greška pri dohvaćanju RSS vijesti: {str(e)}")
        return None

def prevedi_vijesti(vijesti, izvorni_jezik, ciljni_jezik="hr"):
    """
    Prevodi vijesti koristeći Anthropic model ako nisu na hrvatskom jeziku
    """
    # Ako nema vijesti, vraćamo None
    if vijesti is None:
        return None
        
    # Ako su vijesti već na hrvatskom, ne prevodimo ih
    if izvorni_jezik == "hr":
        return vijesti
    
    # Ako je mixed jezik, preskačemo prevođenje
    if izvorni_jezik == "mixed":
        return vijesti
    
    try:
        client = ChatAnthropic(
            anthropic_api_key=ANTHROPIC_API_KEY,
            model_name="claude-3-haiku-20240307"
        )
        
        prevedene_vijesti = []
        
        for vijest in vijesti:
            naslov = vijest['naslov']
            tekst = vijest['tekst']
            
            prompt = f"""
            Prevedi sljedeći naslov i tekst vijesti s {izvorni_jezik} jezika na hrvatski jezik. 
            Zadrži sve informacije i stil, samo prevedi sadržaj.
            
            Naslov: {naslov}
            Tekst: {tekst}
            
            Format odgovora:
            Naslov: [prevedeni naslov]
            Tekst: [prevedeni tekst]
            """
            
            odgovor = client.invoke(prompt)
            prijevod = odgovor.content
            
            # Parsiranje prevedenog naslova i teksta
            prevedeni_naslov = naslov  # defaultna vrijednost ako ekstrakcija ne uspije
            prevedeni_tekst = tekst    # defaultna vrijednost ako ekstrakcija ne uspije
            
            if "Naslov:" in prijevod:
                prevedeni_naslov = prijevod.split("Naslov:")[1].split("\n")[0].strip()
            
            if "Tekst:" in prijevod:
                prevedeni_tekst = prijevod.split("Tekst:")[1].strip()
            
            prevedene_vijesti.append({
                'naslov': prevedeni_naslov,
                'tekst': prevedeni_tekst,
                'izvor': vijest['izvor'] + " (prevedeno)",
                'link': vijest['link']
            })
        
        return prevedene_vijesti
    except Exception as e:
        print(f"Greška pri prevođenju vijesti: {str(e)}")
        return vijesti  # Ako prijevod ne uspije, vrati originalne vijesti

def generiraj_hrvatska_vijesti():
    """Dohvaća najnovije vijesti iz Hrvatske iz RSS feedova"""
    try:
        return dohvati_vijesti_iz_rss("Hrvatska")
    except Exception as e:
        raise Exception(f"Greška pri generiranju vijesti iz Hrvatske: {str(e)}")

def generiraj_svijet_vijesti():
    """Dohvaća i prevodi najnovije svjetske vijesti iz RSS feedova"""
    try:
        vijesti = dohvati_vijesti_iz_rss("Svijet")
        return prevedi_vijesti(vijesti, "en", "hr")
    except Exception as e:
        raise Exception(f"Greška pri generiranju svjetskih vijesti: {str(e)}")

def generiraj_ekonomija_vijesti():
    """Dohvaća i prevodi najnovije ekonomske vijesti iz RSS feedova"""
    try:
        vijesti = dohvati_vijesti_iz_rss("Ekonomija", broj_vijesti=7)
        return prevedi_vijesti(vijesti, "en", "hr")
    except Exception as e:
        raise Exception(f"Greška pri generiranju ekonomskih vijesti: {str(e)}")

def generiraj_sport_vijesti():
    """
    Dohvaća kombinaciju hrvatskih i svjetskih sportskih vijesti
    Ukupno 10 vijesti (5 HR + 5 svjetskih, prevedenih)
    """
    try:
        # Dohvaćamo hrvatske sportske vijesti (5)
        hr_vijesti = dohvati_vijesti_iz_rss("Sport_HR", broj_vijesti=5)
        
        # Dohvaćamo svjetske sportske vijesti (5) i prevodimo ih
        world_vijesti = dohvati_vijesti_iz_rss("Sport_World", broj_vijesti=5)
        prevedene_world_vijesti = prevedi_vijesti(world_vijesti, "en", "hr")
        
        # Spajamo dvije liste vijesti
        sve_vijesti = []
        
        if hr_vijesti:
            sve_vijesti.extend(hr_vijesti)
            
        if prevedene_world_vijesti:
            sve_vijesti.extend(prevedene_world_vijesti)
            
        # Ako nemamo nijednu vijest, vraćamo None
        if not sve_vijesti:
            return None
            
        return sve_vijesti
    except Exception as e:
        raise Exception(f"Greška pri generiranju sportskih vijesti: {str(e)}")

def generiraj_regija_vijesti():
    """
    Dohvaća najvažnije vijesti iz Slovenije, Mađarske, Italije i Austrije
    Po 2 najvažnije vijesti iz svake zemlje (ukupno 8)
    """
    try:
        sve_vijesti = []
        zemlje = {
            "Slovenija": ("sl", "Slovenija"),
            "Mađarska": ("hu", "Mađarska"), 
            "Italija": ("it", "Italija"),
            "Austrija": ("de", "Austrija")
        }
        
        for zemlja, (jezik, naziv) in zemlje.items():
            # Dohvati 4 vijesti iz svake zemlje za bolji odabir
            vijesti = dohvati_vijesti_iz_rss(zemlja, broj_vijesti=4)
            
            if vijesti:
                # Prevedi vijesti
                prevedene_vijesti = prevedi_vijesti(vijesti, jezik, "hr")
                
                if prevedene_vijesti:
                    # Uzmi prve 2 vijesti
                    najvaznije_vijesti = prevedene_vijesti[:2]
                    
                    # Dodaj oznaku zemlje u izvor
                    for vijest in najvaznije_vijesti:
                        vijest['izvor'] = f"[{naziv}] {vijest['izvor']}"
                    
                    sve_vijesti.extend(najvaznije_vijesti)
        
        # Osiguraj se da ukupno ne vraćamo više od 8 vijesti
        if len(sve_vijesti) > 8:
            sve_vijesti = sve_vijesti[:8]
        
        # Ako nemamo nijednu vijest, vraćamo None
        if not sve_vijesti:
            return None
            
        return sve_vijesti
    except Exception as e:
        raise Exception(f"Greška pri generiranju regionalnih vijesti: {str(e)}")

def generiraj_vijesti(kategorija, spinner_callback=None):
    """
    Generira vijesti prema odabranoj kategoriji.
    """
    try:
        # Dohvaćanje današnjeg datuma
        danas = datetime.datetime.now().strftime("%d.%m.%Y")
        
        # Mapping stare kategorije u nove (za kompatibilnost)
        kategorija_mapping = {
            "Hrvatske vijesti": "Hrvatska",
            "Svjetske vijesti": "Svijet",
            "Ekonomske vijesti": "Ekonomija",
            "Hrvatske sportske vijesti": "Sport",
            "Svjetske sportske vijesti": "Sport",
            "Slovenske vijesti": "Regija",
            "Mađarske vijesti": "Regija",
            "Talijanske vijesti": "Regija",
            "Austrijske vijesti": "Regija"
        }
        
        # Provjeri da li je kategorija u starom formatu i pretvori je
        if kategorija in kategorija_mapping:
            kategorija = kategorija_mapping[kategorija]
        
        # Generiranje vijesti ovisno o kategoriji
        if kategorija == "Hrvatska":
            vijesti = generiraj_hrvatska_vijesti()
            filename_prefix = "hrvatska"
        elif kategorija == "Svijet":
            vijesti = generiraj_svijet_vijesti()
            filename_prefix = "svijet"
        elif kategorija == "Ekonomija":
            vijesti = generiraj_ekonomija_vijesti()
            filename_prefix = "ekonomija"
        elif kategorija == "Sport":
            vijesti = generiraj_sport_vijesti()
            filename_prefix = "sport"
        elif kategorija == "Regija":
            vijesti = generiraj_regija_vijesti()
            filename_prefix = "regija"
        else:
            return f"Nepoznata kategorija: {kategorija}", None
        
        # Provjera jesu li vijesti dostupne
        if vijesti is None:
            return f"Trenutno nije moguće dohvatiti vijesti iz kategorije {kategorija}. Molimo pokušajte kasnije.", None
        
        # Formatiranje vijesti za prikaz
        rezultat = ""
        for vijest in vijesti:
            rezultat += f"NASLOV: {vijest['naslov']}\n"
            rezultat += f"{vijest['tekst']}\n"
            rezultat += f"Izvor: {vijest['izvor']} - {vijest['link']}\n\n"
        
        # Kreiranje direktorija za vijesti ako ne postoji
        if not os.path.exists("vijesti"):
            os.makedirs("vijesti")
        
        # Spremanje vijesti u datoteku
        filename = f"vijesti/{filename_prefix}_{datetime.datetime.now().strftime('%Y-%m-%d')}.txt"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(f"{kategorija.upper()} ZA {danas}\n\n")
            file.write(rezultat)
        
        return rezultat, filename
    
    except Exception as e:
        return f"Došlo je do pogreške: {str(e)}", None

def parse_news_content(content):
    """Parse news file content into individual articles for FastAPI"""
    articles = []
    lines = content.split('\n')
    current_article = {}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('NASLOV:'):
            # Save previous article if exists
            if current_article:
                articles.append(current_article)
            
            # Start new article
            current_article = {
                'naslov': line.replace('NASLOV:', '').strip(),
                'tekst': '',
                'izvor': '',
                'link': ''
            }
            i += 1
            
            # Get article text (everything until "Izvor:")
            article_text = []
            while i < len(lines) and not lines[i].strip().startswith('Izvor:'):
                if lines[i].strip():  # Skip empty lines
                    article_text.append(lines[i].strip())
                i += 1
            
            current_article['tekst'] = ' '.join(article_text)
            
            # Get source info
            if i < len(lines) and lines[i].strip().startswith('Izvor:'):
                source_line = lines[i].strip().replace('Izvor:', '').strip()
                if ' - ' in source_line:
                    source_parts = source_line.split(' - ', 1)
                    current_article['izvor'] = source_parts[0].strip()
                    current_article['link'] = source_parts[1].strip()
                else:
                    current_article['izvor'] = source_line
                    current_article['link'] = '#'
            i += 1
        else:
            i += 1
    
    # Don't forget the last article
    if current_article:
        articles.append(current_article)
    
    return articles