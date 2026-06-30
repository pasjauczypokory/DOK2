import streamlit as st
import requests
import datetime
import re
import io
import fitz  # Potężna biblioteka PyMuPDF

# --- POBIERANIE OFICJALNEJ CZCIONKI Z POLSKIMI ZNAKAMI ---
@st.cache_data
def get_font_bytes():
    try:
        url = "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Me5Q.ttf"
        return requests.get(url).content
    except:
        return None

# --- INICJALIZACJA PAMIĘCI PODRĘCZNEJ (SESSION STATE) ---
if 'wygenerowano' not in st.session_state:
    st.session_state.wygenerowano = False
    st.session_state.bufor_umowa = None
    st.session_state.bezpieczna_nazwa_firmy = ""
    st.session_state.plik_umowy = ""

# --- INTELIGENTNE POBIERANIE DANYCH + AUTOMATYCZNA MIEJSCOWOŚĆ ---
def pobierz_dane_z_api(nip):
    dzisiaj = datetime.date.today().strftime("%Y-%m-%d")
    url = f"https://wl-api.mf.gov.pl/api/search/nip/{nip}?date={dzisiaj}"
    try:
        odpowiedz = requests.get(url)
        if odpowiedz.status_code == 200:
            dane = hotel = odpowiedz.json()['result']['subject']
            if dane:
                adres = dane.get('workingAddress') or dane.get('residenceAddress') or ""
                krs = dane.get('krs', '')
                
                # WYCIĄGANIE MIEJSCOWOŚCI Z ADRESU (szukamy miasta zaraz po kodzie pocztowym XX-XXX)
                miejscowosc = "Warszawa" # domyślny zapas
                if adres:
                    # Szuka wzoru typu 00-000 i łapie tekst po nim, ignorując ewentualne przecinki czy kropki
                    match = re.search(r'\d{2}-\d{3}\s+([A-ZĄĆĘŁŃÓŚŹŻa-ęćłńóśźż\s-]+)', adres)
                    if match:
                        miejscowosc = match.group(1).strip().title() # Zamienia wersaliki np. KRAKÓW na Kraków
                
                # Próba automatycznego wyciągnięcia Imienia i Nazwiska z nazwy JDG
                pelna_nazwa = dane.get('name', '')
                wykryte_reprezentant = ""
                if not krs and pelna_nazwa:
                    slowa = pelna_nazwa.split()
                    if len(slowa) >= 2:
                        wykryte_reprezentant = f"{slowa[0].capitalize()} {slowa[1].capitalize()}"

                return {
                    "nazwa": pelna_nazwa,
                    "regon": dane.get('regon', ''),
                    "krs": krs or "Brak",
                    "adres": adres,
                    "miejscowosc": miejscowosc,
                    "czy_krs": bool(krs),
                    "wykryte_reprezentant": wykryte_reprezentant
                }
        return None
    except Exception as e:
        return None

# --- WYGLĄD STRONY ---
st.set_page_config(page_title="Generator Oświadczeń", page_icon="📝")
st.title("🗂️ Generator Oświadczeń")
st.divider() 

# --- RESZTA APLIKACJI ---
st.header("1. Wpisz NIP i wybierz datę")
col_nip, col_data = st.columns(2)
with col_nip:
    nip_input = st.text_input("Wpisz NIP (10 cyfr)")
with col_data:
    wybrana_data = st.date_input("Data na dokumencie:", datetime.date.today())

nazwa_do_edycji = ""
reprezentant_auto = ""
dane_z_api = None
czy_krs = False

# AUTOMATYCZNE ROZPOZNAWANIE KLIENTA
if nip_input and len(nip_input.strip().replace("-", "")) == 10:
    dane_z_api = pobierz_dane_z_api(nip_input.strip().replace("-", ""))
    if dane_z_api:
        nazwa_do_edycji = dane_z_api['nazwa']
        czy_krs = dane_z_api['czy_krs']
        reprezentant_auto = dane_z_api['wykryte_reprezentant']
        
        if czy_krs:
            st.success(f"🏢 Wykryto Spółkę (KRS: {dane_z_api['krs']}). System automatycznie użyje wzoru KRS.")
        else:
            st.info("👤 Wykryto działalność (CEIDG). System automatycznie użyje wzoru JDG.")

st.header("2. Dane firmy")
finalna_nazwa_firmy = st.text_input("Pełna nazwa firmy (edytuj, jeśli zachodzi potrzeba):", value=nazwa_do_edycji)

# BLOK DANYCH UZUPEŁNIAJĄCYCH (Pokazuje się TYLKO dla działalności gospodarczej - CEIDG)
imie_input = ""
pesel_input = ""
nr_dowodu_input = ""

if not czy_krs and dane_z_api:
    st.header("3. Dane uzupełniające właściciela")
    col1, col2 = st.columns(2)
    with col1:
        imie_input = st.text_input("Imię i nazwisko reprezentanta:", value=reprezentant_auto)
        nr_dowodu_input = st.text_input("Seria i nr Dowodu Osobistego:")
    with col2:
        pesel_input = st.text_input("PESEL:")

# --- LOGIKA GENEROWANIA ---
if st.button("Generuj Oświadczenie", type="primary"):
    nip = nip_input.strip().replace("-", "")
    
    if len(nip) != 10:
        st.warning("Podaj poprawny, 10-cyfrowy NIP!")
    elif not finalna_nazwa_firmy:
        st.error("Uzupełnij nazwę firmy!")
    elif not czy_krs and not imie_input:
        st.error("Uzupełnij imię i nazwisko właściciela!")
    else:
        if not dane_z_api:
            st.error("Nie znaleziono firmy o takim NIP w bazie MF.")
        else:
            surowa_nazwa = finalna_nazwa_firmy
            formy_prawne = r"\b(SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ|SPÓŁKA Z O\.O\.|SP\. Z O\.O\.|SP Z O O|SPÓŁKA Z O O|SPÓŁKA JAWNA|SP\. J\.|SP J|SPÓŁKA AKCYJNA|S\.A\.|SA|SPÓŁKA KOMANDYTOWA|SP\. K\.|SP K|SPÓŁKA KOMANDYTOWO-AKCYJNA|