import datetime
from dotenv import load_dotenv
import os
import feedparser
import re
from bs4 import BeautifulSoup
from langchain_anthropic import ChatAnthropic

load_dotenv()

# Get API key from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# RSS Feeds configuration (keep your existing RSS_FEEDS dictionary)
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
    "Sport_HR": [
        "https://www.index.hr/rss/sport",
        "https://sportske.jutarnji.hr/rss",
        "https://www.24sata.hr/feeds/sport.xml",
        "https://gol.dnevnik.hr/feeds/category/4.xml",
        "https://sportnet.rtl.hr/rss/sve-vijesti/",
    ],
    "Sport_World": [
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
    "Regija": "mixed",
}

def ocisti_html(html_tekst):
    """Uklanja HTML tagove iz teksta"""
    if not html_tekst:
        return ""
    
    soup = BeautifulSoup(html_tekst, 'html.parser')
    tekst = soup.get_text(separator=' ', strip=True)
    tekst = re.sub(r'\s+', ' ', tekst)
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
        
        vijesti_po_izvoru = {}
        broj_feedova = len(feedovi)
        
        for feed_url in feedovi:
            try:
                feed = feedparser.parse(feed_url)
                feed_izvor = feed.feed.get('title', 'Nepoznat izvor')
                vijesti_po_izvoru[feed_izvor] = []
                
                for entry in feed.entries:
                    naslov = entry.get('title', 'Naslov nije dostupan')
                    
                    tekst = ''
                    if 'description' in entry:
                        tekst = entry.description
                    elif 'summary' in entry:
                        tekst = entry.summary
                    elif 'content' in entry and len(entry.content) > 0:
                        tekst = entry.content[0].value
                    else:
                        tekst = 'Opis nije dostupan'
                    
                    tekst = ocisti_html(tekst)
                    
                    if len(tekst) < 20 and 'nije dostupan' not in tekst:
                        tekst = 'Sadržaj nije dostupan.'
                    
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
        
        # Balanced selection of news from all sources
        balansirane_vijesti = []
        aktivni_izvori = [izvor for izvor, vijesti in vijesti_po_izvoru.items() if vijesti]
        
        if not aktivni_izvori:
            return None
            
        vijesti_po_aktivnom_izvoru = max(1, min(int(broj_vijesti / len(aktivni_izvori)), 2))
        
        for izvor in aktivni_izvori:
            vijesti_izvora = vijesti_po_izvoru[izvor][:vijesti_po_aktivnom_izvoru]
            balansirane_vijesti.extend(vijesti_izvora)
            
        if len(balansirane_vijesti) < broj_vijesti:
            najveci_izvor = max(vijesti_po_izvoru.items(), key=lambda x: len(x[1]))[0]
            vec_dodane = sum(1 for v in balansirane_vijesti if v['izvor'] == najveci_izvor)
            
            dodaj_jos = min(broj_vijesti - len(balansirane_vijesti), 
                            len(vijesti_po_izvoru[najveci_izvor]) - vec_dodane)
                            
            if dodaj_jos > 0:
                dodatne_vijesti = vijesti_po_izvoru[najveci_izvor][vec_dodane:vec_dodane+dodaj_jos]
                balansirane_vijesti.extend(dodatne_vijesti)
        
        return balansirane_vijesti[:broj_vijesti]
    
    except Exception as e:
        print(f"Greška pri dohvaćanju RSS vijesti: {str(e)}")
        return None

def generiraj_ai_sazetak(naslov, kratki_tekst):
    """
    Generates an AI-enhanced summary for Croatian news articles
    """
    if not ANTHROPIC_API_KEY:
        print("⚠️ Cannot generate AI summary: ANTHROPIC_API_KEY not found")
        return kratki_tekst
    
    try:
        print(f"🤖 Generating AI-enhanced summary for: {naslov[:50]}...")
        
        client = ChatAnthropic(
            anthropic_api_key=ANTHROPIC_API_KEY,
            model_name="claude-3-haiku-20240307"
        )
        
        prompt = f"""
        Na temelju sljedećeg naslova i kratkog opisa hrvatskih vijesti, stvori detaljniji i informativan sažetak koji će čitatelju pružiti potpuniju sliku o događaju. 

        Naslov: {naslov}
        Kratki opis: {kratki_tekst}

        Molim te:
        1. Proširi informacije logično i prirodno
        2. Dodaj kontekst koji bi mogao biti važan hrvatskim čitateljima
        3. Zadrži faktičnost - ne izmišljaj nove činjenice
        4. Piši na hrvatskom jeziku
        5. Duljina: 150-300 riječi
        6. Budi informativan i jasan

        Odgovori samo proširenim sažetkom, bez dodatnih objašnjenja:
        """
        
        response = client.invoke(prompt)
        enhanced_summary = response.content.strip()
        
        print(f"✅ AI summary generated ({len(enhanced_summary)} characters)")
        return enhanced_summary
        
    except Exception as e:
        print(f"❌ Failed to generate AI summary: {e}")
        return kratki_tekst  # Return original text if AI enhancement fails

def prevedi_vijesti(vijesti, izvorni_jezik, ciljni_jezik="hr"):
    """
    Prevodi vijesti koristeći Anthropic model ako nisu na hrvatskom jeziku
    """
    print(f"🔄 prevedi_vijesti called with {len(vijesti) if vijesti else 0} articles, source language: {izvorni_jezik}")
    
    if vijesti is None:
        print("⚠️ No news to translate")
        return None
        
    if izvorni_jezik == "hr":
        print(f"✅ News already in Croatian, returning {len(vijesti)} articles")
        return vijesti
    
    if izvorni_jezik == "mixed":
        print(f"✅ Mixed language content, returning {len(vijesti)} articles without translation")
        return vijesti
    
    if not ANTHROPIC_API_KEY:
        print("❌ Cannot translate: ANTHROPIC_API_KEY not found")
        return vijesti
    
    try:
        print(f"🔄 Starting translation of {len(vijesti)} articles from {izvorni_jezik} to {ciljni_jezik}")
        
        client = ChatAnthropic(
            anthropic_api_key=ANTHROPIC_API_KEY,
            model_name="claude-3-haiku-20240307"
        )
        
        prevedene_vijesti = []
        
        for i, vijest in enumerate(vijesti):
            print(f"🔄 Translating article {i+1}/{len(vijesti)}: {vijest['naslov'][:50]}...")
            
            naslov = vijest['naslov']
            tekst = vijest['tekst']
            
            prompt = f"""
            Prevedi sljedeći naslov i tekst vijesti s {izvorni_jezik} jezika na hrvatski jezik. 
            Zadrži sve informacije i stil, samo prevedi sadržaj. Budi precizan i prirodan.
            
            Naslov: {naslov}
            
            Tekst: {tekst}
            
            Molim te odgovori u sljedećem formatu:
            NASLOV: [prevedeni naslov]
            TEKST: [prevedeni tekst]
            """
            
            try:
                odgovor = client.invoke(prompt)
                prijevod = odgovor.content
                print(f"✅ Got translation response for article {i+1}")
                
                prevedeni_naslov = naslov
                prevedeni_tekst = tekst
                
                if "NASLOV:" in prijevod:
                    lines = prijevod.split("\n")
                    for line in lines:
                        if line.strip().startswith("NASLOV:"):
                            prevedeni_naslov = line.replace("NASLOV:", "").strip()
                            break
                
                if "TEKST:" in prijevod:
                    tekst_start = prijevod.find("TEKST:")
                    if tekst_start != -1:
                        prevedeni_tekst = prijevod[tekst_start + 6:].strip()
                
                prevedene_vijesti.append({
                    'naslov': prevedeni_naslov,
                    'tekst': prevedeni_tekst,
                    'izvor': vijest['izvor'] + " (prevedeno)",
                    'link': vijest['link']
                })
                
                print(f"✅ Article {i+1} translated successfully")
                
            except Exception as article_error:
                print(f"❌ Failed to translate article {i+1}: {article_error}")
                prevedene_vijesti.append({
                    'naslov': naslov,
                    'tekst': tekst,
                    'izvor': vijest['izvor'] + " (translation failed)",
                    'link': vijest['link']
                })
        
        print(f"✅ Translation completed: {len(prevedene_vijesti)} articles processed")
        return prevedene_vijesti
        
    except Exception as e:
        print(f"❌ Translation service failed: {str(e)}")
        return vijesti

def generiraj_hrvatska_vijesti():
    """
    Dohvaća najnovije vijesti iz Hrvatske i stvara AI-poboljšane sažetke
    """
    try:
        print("🇭🇷 Fetching Croatian news...")
        vijesti = dohvati_vijesti_iz_rss("Hrvatska")
        
        if not vijesti:
            print("❌ No Croatian news fetched")
            return None
        
        print(f"📰 Fetched {len(vijesti)} Croatian news articles")
        print("🤖 Starting AI enhancement for Croatian articles...")
        
        # Enhance Croatian articles with AI-generated summaries
        poboljsane_vijesti = []
        
        for i, vijest in enumerate(vijesti):
            print(f"🤖 Enhancing article {i+1}/{len(vijesti)}: {vijest['naslov'][:50]}...")
            
            # Generate AI-enhanced summary
            ai_summary = generiraj_ai_sazetak(vijest['naslov'], vijest['tekst'])
            
            # Create short preview (max 140 characters)
            original_text = vijest['tekst']
            if len(original_text) > 140:
                short_preview = original_text[:137] + "..."
            else:
                short_preview = original_text
            
            # Create enhanced article with short preview and AI-enhanced full content
            poboljsana_vijest = {
                'naslov': vijest['naslov'],
                'tekst': short_preview,  # Short preview for initial display
                'ai_enhanced_content': ai_summary,  # Full AI-enhanced content for expansion
                'izvor': vijest['izvor'] + " (AI-poboljšano)",
                'link': None  # Remove external link for Croatian news
            }
            
            poboljsane_vijesti.append(poboljsana_vijest)
            print(f"✅ Article {i+1} enhanced successfully")
        
        print(f"✅ Croatian news enhancement completed: {len(poboljsane_vijesti)} articles")
        return poboljsane_vijesti
        
    except Exception as e:
        print(f"❌ Error generating Croatian news: {str(e)}")
        raise Exception(f"Greška pri generiranju hrvatskih vijesti: {str(e)}")

def generiraj_svijet_vijesti():
    """Dohvaća i prevodi najnovije svjetske vijesti iz RSS feedova"""
    try:
        print("🌍 Fetching world news...")
        vijesti = dohvati_vijesti_iz_rss("Svijet")
        
        if not vijesti:
            print("❌ No world news fetched")
            return None
            
        print(f"📰 Fetched {len(vijesti)} world news articles")
        print("🔄 Starting translation to Croatian...")
        
        translated_news = prevedi_vijesti(vijesti, "en", "hr")
        
        if translated_news:
            print(f"✅ World news translation completed: {len(translated_news)} articles")
        else:
            print("❌ World news translation failed")
            
        return translated_news
        
    except Exception as e:
        print(f"❌ Error generating world news: {str(e)}")
        raise Exception(f"Greška pri generiranju svjetskih vijesti: {str(e)}")

def generiraj_ekonomija_vijesti():
    """Dohvaća i prevodi najnovije ekonomske vijesti iz RSS feedova"""
    try:
        print("💼 Fetching economy news...")
        vijesti = dohvati_vijesti_iz_rss("Ekonomija", broj_vijesti=7)
        
        if not vijesti:
            print("❌ No economy news fetched")
            return None
            
        print(f"📰 Fetched {len(vijesti)} economy news articles")
        print("🔄 Starting translation to Croatian...")
        
        translated_news = prevedi_vijesti(vijesti, "en", "hr")
        
        if translated_news:
            print(f"✅ Economy news translation completed: {len(translated_news)} articles")
        else:
            print("❌ Economy news translation failed")
            
        return translated_news
        
    except Exception as e:
        print(f"❌ Error generating economy news: {str(e)}")
        raise Exception(f"Greška pri generiranju ekonomskih vijesti: {str(e)}")

def generiraj_sport_vijesti():
    """
    Dohvaća kombinaciju hrvatskih i svjetskih sportskih vijesti
    Ukupno 10 vijesti (5 HR + 5 svjetskih, prevedenih)
    """
    try:
        print("⚽ Fetching sports news...")
        
        # Fetch Croatian sports news (5)
        print("🇭🇷 Fetching Croatian sports news...")
        hr_vijesti = dohvati_vijesti_iz_rss("Sport_HR", broj_vijesti=5)
        
        # Fetch world sports news (5) and translate them
        print("🌍 Fetching world sports news...")
        world_vijesti = dohvati_vijesti_iz_rss("Sport_World", broj_vijesti=5)
        
        if world_vijesti:
            print("🔄 Translating world sports news...")
            prevedene_world_vijesti = prevedi_vijesti(world_vijesti, "en", "hr")
        else:
            prevedene_world_vijesti = None
        
        # Combine both lists
        sve_vijesti = []
        
        if hr_vijesti:
            print(f"✅ Added {len(hr_vijesti)} Croatian sports articles")
            sve_vijesti.extend(hr_vijesti)
            
        if prevedene_world_vijesti:
            print(f"✅ Added {len(prevedene_world_vijesti)} translated world sports articles")
            sve_vijesti.extend(prevedene_world_vijesti)
            
        if not sve_vijesti:
            print("❌ No sports news available")
            return None
            
        print(f"✅ Sports news completed: {len(sve_vijesti)} total articles")
        return sve_vijesti
        
    except Exception as e:
        print(f"❌ Error generating sports news: {str(e)}")
        raise Exception(f"Greška pri generiranju sportskih vijesti: {str(e)}")

def generiraj_regija_vijesti():
    """
    Dohvaća najvažnije vijesti iz Slovenije, Mađarske, Italije i Austrije
    Po 2 najvažnije vijesti iz svake zemlje (ukupno 8)
    """
    try:
        print("🏛️ Fetching regional news...")
        sve_vijesti = []
        zemlje = {
            "Slovenija": ("sl", "Slovenija"),
            "Mađarska": ("hu", "Mađarska"), 
            "Italija": ("it", "Italija"),
            "Austrija": ("de", "Austrija")
        }
        
        for zemlja, (jezik, naziv) in zemlje.items():
            print(f"🔄 Fetching news from {naziv}...")
            
            vijesti = dohvati_vijesti_iz_rss(zemlja, broj_vijesti=4)
            
            if vijesti:
                print(f"📰 Fetched {len(vijesti)} articles from {naziv}")
                print(f"🔄 Translating {naziv} news to Croatian...")
                
                prevedene_vijesti = prevedi_vijesti(vijesti, jezik, "hr")
                
                if prevedene_vijesti:
                    najvaznije_vijesti = prevedene_vijesti[:2]
                    
                    for vijest in najvaznije_vijesti:
                        vijest['izvor'] = f"[{naziv}] {vijest['izvor']}"
                    
                    sve_vijesti.extend(najvaznije_vijesti)
                    print(f"✅ Added {len(najvaznije_vijesti)} articles from {naziv}")
                else:
                    print(f"❌ Translation failed for {naziv}")
            else:
                print(f"❌ No articles fetched from {naziv}")
        
        if len(sve_vijesti) > 8:
            sve_vijesti = sve_vijesti[:8]
        
        if not sve_vijesti:
            print("❌ No regional news available")
            return None
            
        print(f"✅ Regional news completed: {len(sve_vijesti)} total articles")
        return sve_vijesti
        
    except Exception as e:
        print(f"❌ Error generating regional news: {str(e)}")
        raise Exception(f"Greška pri generiranju regionalnih vijesti: {str(e)}")

def generiraj_vijesti(kategorija, spinner_callback=None):
    """
    Generira vijesti prema odabranoj kategoriji.
    """
    try:
        danas = datetime.datetime.now().strftime("%d.%m.%Y")
        
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
        
        if kategorija in kategorija_mapping:
            kategorija = kategorija_mapping[kategorija]
        
        # Generate news based on category
        if kategorija == "Hrvatska":
            vijesti = generiraj_hrvatska_vijesti()  # Uses AI-enhanced summaries
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
        
        if vijesti is None:
            return f"Trenutno nije moguće dohvatiti vijesti iz kategorije {kategorija}. Molimo pokušajte kasnije.", None
        
        # Format news for display
        rezultat = ""
        for vijest in vijesti:
            rezultat += f"NASLOV: {vijest['naslov']}\n"
            rezultat += f"{vijest['tekst']}\n"
            
            # Add AI-enhanced content if available (for Croatian news)
            if vijest.get('ai_enhanced_content'):
                rezultat += f"AI_ENHANCED: {vijest['ai_enhanced_content']}\n"
            
            if vijest.get('link'):  # Only add link if it exists
                rezultat += f"Izvor: {vijest['izvor']} - {vijest['link']}\n\n"
            else:
                rezultat += f"Izvor: {vijest['izvor']}\n\n"
        
        # Save to file
        if not os.path.exists("vijesti"):
            os.makedirs("vijesti")
        
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
            if current_article:
                articles.append(current_article)
            
            current_article = {
                'naslov': line.replace('NASLOV:', '').strip(),
                'tekst': '',
                'ai_enhanced_content': '',
                'izvor': '',
                'link': ''
            }
            i += 1
            
            article_text = []
            ai_content = []
            in_ai_section = False
            
            while i < len(lines) and not lines[i].strip().startswith('Izvor:'):
                line_content = lines[i].strip()
                if line_content:
                    if line_content.startswith('AI_ENHANCED:'):
                        in_ai_section = True
                        ai_content.append(line_content.replace('AI_ENHANCED:', '').strip())
                    elif in_ai_section:
                        ai_content.append(line_content)
                    else:
                        article_text.append(line_content)
                i += 1
            
            current_article['tekst'] = ' '.join(article_text)
            current_article['ai_enhanced_content'] = ' '.join(ai_content)
            
            # Get source info
            if i < len(lines) and lines[i].strip().startswith('Izvor:'):
                source_line = lines[i].strip().replace('Izvor:', '').strip()
                if ' - ' in source_line:
                    source_parts = source_line.split(' - ', 1)
                    current_article['izvor'] = source_parts[0].strip()
                    current_article['link'] = source_parts[1].strip()
                else:
                    current_article['izvor'] = source_line
                    current_article['link'] = None  # No link for AI-enhanced articles
            i += 1
        else:
            i += 1
    
    if current_article:
        articles.append(current_article)
    
    return articles