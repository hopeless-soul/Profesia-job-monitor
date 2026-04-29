from playwright.sync_api import sync_playwright
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time

# --- NASTAVENIA MAILU (Doplň si svoje údaje zo Seznamu) ---
SENDER_EMAIL = "MAIL"
SENDER_PASSWORD = "HESLO"


def posli_mail_seznam(df_nove):
    if df_nove.empty:
        return

    msg = MIMEMultipart()
    msg['Subject'] = f"🔔 NOVÉ PYTHON POZÍCIE ({datetime.now().strftime('%d.%m. %H:%M')})"
    msg['From'] = SENDER_EMAIL
    msg['To'] = SENDER_EMAIL

    text = "Ahoj, robot prešiel viacero stránok na Profesii a našiel tieto NOVÉ ponuky:\n\n"
    text += df_nove[['pozicia', 'firma', 'plat']].to_string(index=False)
    text += "\n\nDržím palce pri odpisovaní!"

    msg.attach(MIMEText(text, 'plain'))

    try:
        with smtplib.SMTP_SSL("smtp.seznam.cz", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, SENDER_EMAIL, msg.as_string())
        print("📧 Mail s novinkami bol odoslaný na Seznam!")
    except Exception as e:
        print(f"❌ Chyba pri odosielaní mailu: {e}")


def spusti_multipage_system():
    db_name = 'moje_hladanie_prace.db'
    final_data = []
    pocet_stran = 3  # Tu si môžeš nastaviť aj viac, napr. 5

    with sync_playwright() as p:
        print("🚀 Štartujem robota s maskovaním...")
        # NAJPRV spustiť prehliadač
        browser = p.chromium.launch(headless=False)

        # POTOM vytvoriť context s poriadnym User-Agentom
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        context = browser.new_context(user_agent=ua)

        # NAKONIEC otvoriť stránku
        page = context.new_page()

        for cislo_strany in range(1, pocet_stran + 1):
            print(f"📄 Spracovávam stranu č. {cislo_strany}...")
            url = f"https://www.profesia.sk/praca/c-sharp/?page={cislo_strany}&search_anywhere=c%23"

            try:
                # 1. Načítame stránku a počkáme, kým sa sieť upokojí
                page.goto(url, wait_until="networkidle")

                # 2. Emulujeme pohyb človeka (pauza 5 sekúnd)
                page.wait_for_timeout(5000)

                # 3. Skúsime nájsť akýkoľvek inzerát cez širší filter
                # Profesia často mení triedy, tak hľadáme priamo 'article'
                try:
                    page.wait_for_selector("article", timeout=15000)
                    offers = page.query_selector_all("article")
                except:
                    # Ak nenájde article, skúsime starší formát
                    offers = page.query_selector_all("li.list-row")

                if not offers:
                    print(f"⚠️ Na strane {cislo_strany} robot nič nevidí (možná blokácia).")
                    continue

                for offer in offers:
                    try:
                        title_el = offer.query_selector("h2")
                        if title_el:
                            title = title_el.inner_text().strip()
                            print(f"🔍 Našiel som: {title}")

                        # FILTER: Vyhadzujeme seniorné pozície
                        zakazane = []
                        if any(z in title.lower() for z in zakazane):
                            continue

                        employer = offer.query_selector(".employer").inner_text().strip()
                        salary_el = offer.query_selector(".label-info")
                        salary = salary_el.inner_text().strip() if salary_el else "Dohodou"

                        final_data.append({
                            "datum_zberu": datetime.now().strftime("%Y-%m-%d"),
                            "pozicia": title,
                            "firma": employer,
                            "plat": salary
                        })
                    except:
                        continue

                # Malá pauza medzi stránkami, aby sme nevyzerali ako agresívny útok
                time.sleep(1)

            except Exception as e:
                print(f"⚠ Stranu {cislo_strany} sa nepodarilo načítať alebo tam už nie sú ponuky.")
                break

        browser.close()

        # SPRACOVANIE DÁT
        df_aktualne = pd.DataFrame(final_data)
        if df_aktualne.empty:
            print("📭 Nenašli sa žiadne relevantné pozície podľa tvojho filtra.")
            return

        df_aktualne.columns = [c.replace(' ', '_').lower() for c in df_aktualne.columns]

        # DATABÁZOVÁ LOGIKA (Ukladáme len to, čo v DB ešte nie je)
        conn = sqlite3.connect(db_name)

        try:
            stare_data = pd.read_sql_query("SELECT * FROM ponuky", conn)
            # Porovnáme aktuálne nájdené veci s tými, čo už máme v databáze
            nove_ponuky = df_aktualne[~df_aktualne.set_index(['pozicia', 'firma']).index.isin(
                stare_data.set_index(['pozicia', 'firma']).index)]
        except:
            nove_ponuky = df_aktualne

        if not nove_ponuky.empty:
            nove_ponuky.to_sql('ponuky', conn, if_exists='append', index=False)
            print(f"🔥 Celkovo spracovaných {len(df_aktualne)} ponúk. Z toho {len(nove_ponuky)} je ÚPLNE NOVÝCH!")
            posli_mail_seznam(nove_ponuky)
        else:
            print(f"✅ Všetkých {len(df_aktualne)} ponúk z týchto stránok už v databáze máš.")

        # GRAF: Ukážeme celkový prehľad z databázy
        vytvor_graf(conn)
        conn.close()


def vytvor_graf(conn):
    query = "SELECT firma, COUNT(*) as pocet FROM ponuky GROUP BY firma ORDER BY pocet DESC LIMIT 10"
    df_graf = pd.read_sql_query(query, conn)

    if not df_graf.empty:
        plt.figure(figsize=(12, 6))
        plt.bar(df_graf['firma'], df_graf['pocet'], color='skyblue', edgecolor='navy')
        plt.title('Top 10 firiem hľadajúcich Pythonistov (Všetky tvoje dáta)')
        plt.xticks(rotation=45, ha='right')
        plt.ylabel('Počet inzerátov')
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    spusti_multipage_system()