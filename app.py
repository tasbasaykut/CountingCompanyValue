import streamlit as st
import yfinance as yf
import time

def hesapla_dcf(fcf_baslangic, buyume_orani, iskonto_orani, kalici_buyume_orani, hisse_adedi, yil=5):
    guncel_fcf = fcf_baslangic
    toplam_pv = 0
    for i in range(1, yil + 1):
        guncel_fcf *= (1 + buyume_orani)
        toplam_pv += guncel_fcf / ((1 + iskonto_orani) ** i)
    uc_deger = (guncel_fcf * (1 + kalici_buyume_orani)) / (iskonto_orani - kalici_buyume_orani)
    uc_deger_pv = uc_deger / ((1 + iskonto_orani) ** yil)
    toplam_sirket_degeri = toplam_pv + uc_deger_pv
    return toplam_sirket_degeri / hisse_adedi


def hesapla_carpan_fk(eps, sektor_fk):
    return eps * sektor_fk


def hesapla_carpan_fd_favok(ebitda, sektor_fd_favok, toplam_borc, toplam_nakit, hisse_adedi):
    hedef_fd = ebitda * sektor_fd_favok
    hedef_ozkaynak = hedef_fd - toplam_borc + toplam_nakit
    return hedef_ozkaynak / hisse_adedi


# Fonksiyonun hemen üstüne bu dekoratörü ekliyoruz. 
# ttl=3600 parametresi, veriyi 1 saat (3600 saniye) boyunca hafızada tutar.
@st.cache_data(ttl=3600) 
def rakip_carpanlarini_bul(rakip_kodlari_str):
    rakipler = [x.strip() for x in rakip_kodlari_str.split(",") if x.strip()]
    fk_listesi = []
    fd_favok_listesi = []
    
    for rakip in rakipler:
        try:
            info = yf.Ticker(rakip).info
            fk = info.get("trailingPE") or info.get("forwardPE")
            if fk and fk > 0:
                fk_listesi.append(fk)
                
            fd_favok = info.get("enterpriseToEbitda")
            if fd_favok and fd_favok > 0:
                fd_favok_listesi.append(fd_favok)
            
            # Her API isteğinden sonra sistemi 1 saniye uyutarak spam filtresine takılmayı önleriz
            time.sleep(1) 
        except:
            continue
            
    ortalama_fk = sum(fk_listesi) / len(fk_listesi) if fk_listesi else None
    ortalama_fd_favok = sum(fd_favok_listesi) / len(fd_favok_listesi) if fd_favok_listesi else None
    
    return ortalama_fk, ortalama_fd_favok

    ortalama_fk = sum(fk_listesi) / len(fk_listesi) if fk_listesi else None
    ortalama_fd_favok = sum(fd_favok_listesi) / len(fd_favok_listesi) if fd_favok_listesi else None

    return ortalama_fk, ortalama_fd_favok


st.set_page_config(page_title="Şirket Değerleme Aracı (USD Bazlı)", layout="wide")
st.title("📊 Şirket Değerleme Aracı (Otonom Çarpan Analizli)")
st.write(
    "Bu uygulama hesaplamaları gerçekleştirirken anlık kur verilerini kullanır ve şirketin borsadaki aktif değeri ile tahmini değerini **USD ($)** cinsinden karşılaştırır.")

# --- SOL MENÜ GİRDİLERİ ---
st.sidebar.header("1. Hedef Hisse")
ticker_symbol = st.sidebar.text_input("Borsa Kodu (Örn: AAPL, THYAO.IS):", "THYAO.IS")

st.sidebar.header("2. DCF Varsayımları")
iskonto_orani = st.sidebar.slider("İskonto Oranı (WACC) %", 1.0, 30.0, 15.0, 0.5) / 100
buyume_orani = st.sidebar.slider("Beklenen Yıllık Büyüme (İlk 5 Yıl) %", 1.0, 50.0, 20.0, 1.0) / 100
kalici_buyume = st.sidebar.slider("Kalıcı Büyüme Oranı %", 0.5, 10.0, 2.5, 0.1) / 100

st.sidebar.header("3. Çarpan Analizi (Dinamik)")
st.sidebar.write(
    "Hedef şirketin sektöründeki rakiplerini aralarına virgül koyarak yazın. Oranlar otomatik çekilecektir.")
rakip_hisseler = st.sidebar.text_input("Rakip Kodları (Örn: PGSUS.IS, DOAS.IS):", "PGSUS.IS")

# --- ANALİZ BLOĞU ---
if st.button("Analiz Et"):
    with st.spinner('Piyasa verileri, rakiplerin çarpanları ve döviz kurları çekiliyor...'):
        try:
            # Rakiplerin Oranlarını Çekme
            sektor_fk, sektor_fd_favok = rakip_carpanlarini_bul(rakip_hisseler)

            # Anlık Dolar Kurunu Çekme
            kur_verisi = yf.Ticker("TRY=X").history(period="1d")
            usd_try_kuru = kur_verisi['Close'].iloc[-1] if not kur_verisi.empty else 1.0

            sirket = yf.Ticker(ticker_symbol)
            info = sirket.info
            kur_boleni = usd_try_kuru if ".IS" in ticker_symbol.upper() else 1.0

            # Şirket Verilerini Çekme
            guncel_fiyat = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            hisse_adedi = info.get("sharesOutstanding")
            eps = info.get("trailingEps") or info.get("forwardEps")
            ebitda = info.get("ebitda")
            toplam_borc = info.get("totalDebt", 0)
            toplam_nakit = info.get("totalCash", 0)

            nakit_akislari = sirket.cashflow
            fcf_baslangic = None
            if not nakit_akislari.empty:
                try:
                    fcf_baslangic = nakit_akislari.loc["Free Cash Flow"].iloc[0]
                except KeyError:
                    try:
                        faliyet_nakdi = nakit_akislari.loc["Operating Cash Flow"].iloc[0]
                        capex = nakit_akislari.loc["Capital Expenditure"].iloc[0]
                        fcf_baslangic = faliyet_nakdi + capex
                    except KeyError:
                        pass

            if not guncel_fiyat:
                st.error("Güncel fiyat verisi bulunamadı. Kodu doğru girdiğinizden emin olun.")
            else:
                guncel_fiyat_usd = guncel_fiyat / kur_boleni

                st.header(f"📌 {info.get('shortName', ticker_symbol)} - Analiz Raporu")

                # --- HATANIN DÜZELTİLDİĞİ KISIM ---
                fk_metin = f"{sektor_fk:.2f}" if sektor_fk else "Veri Yok"
                fd_metin = f"{sektor_fd_favok:.2f}" if sektor_fd_favok else "Veri Yok"

                st.info(f"**Rakiplerden Çekilen Otonom Sektör Ortalamaları:** F/K: {fk_metin} | FD/FAVÖK: {fd_metin}")

                if ".IS" in ticker_symbol.upper():
                    st.info(f"Kullanılan anlık USD/TRY çeviri kuru: **{usd_try_kuru:.2f} ₺**")
                st.markdown("---")

                # 1. DCF Arayüzü
                st.subheader("1. İndirgenmiş Nakit Akımları (DCF) Analizi")
                if fcf_baslangic and hisse_adedi:
                    dcf_degeri = hesapla_dcf(fcf_baslangic, buyume_orani, iskonto_orani, kalici_buyume, hisse_adedi)
                    dcf_usd = dcf_degeri / kur_boleni

                    col1, col2 = st.columns(2)
                    col1.metric("Borsadaki Aktif Değer", f"${guncel_fiyat_usd:,.2f}")
                    col2.metric("Tahmini Değer (DCF)", f"${dcf_usd:,.2f}",
                                f"%{((dcf_usd - guncel_fiyat_usd) / guncel_fiyat_usd) * 100:.1f} Potansiyel")
                else:
                    st.warning("DCF hesabı için gereken veriler eksik.")
                st.markdown("---")

                # 2. F/K Arayüzü
                st.subheader("2. F/K (Fiyat/Kazanç) Çarpanı Analizi")
                if eps and sektor_fk:
                    fk_degeri = hesapla_carpan_fk(eps, sektor_fk)
                    fk_usd = fk_degeri / kur_boleni

                    col1, col2 = st.columns(2)
                    col1.metric("Borsadaki Aktif Değer", f"${guncel_fiyat_usd:,.2f}")
                    col2.metric("Tahmini Değer (F/K)", f"${fk_usd:,.2f}",
                                f"%{((fk_usd - guncel_fiyat_usd) / guncel_fiyat_usd) * 100:.1f} Potansiyel")
                else:
                    st.warning("F/K hesabı için EPS verisi veya geçerli rakip F/K ortalaması eksik.")
                st.markdown("---")

                # 3. FD/FAVÖK Arayüzü
                st.subheader("3. FD/FAVÖK Çarpanı Analizi")
                if ebitda and hisse_adedi and sektor_fd_favok:
                    fd_favok_degeri = hesapla_carpan_fd_favok(ebitda, sektor_fd_favok, toplam_borc, toplam_nakit,
                                                              hisse_adedi)
                    fd_favok_usd = fd_favok_degeri / kur_boleni

                    col1, col2 = st.columns(2)
                    col1.metric("Borsadaki Aktif Değer", f"${guncel_fiyat_usd:,.2f}")
                    col2.metric("Tahmini Değer (FD/FAVÖK)", f"${fd_favok_usd:,.2f}",
                                f"%{((fd_favok_usd - guncel_fiyat_usd) / guncel_fiyat_usd) * 100:.1f} Potansiyel")
                else:
                    st.warning("FD/FAVÖK hesabı için veriler veya geçerli rakip ortalaması eksik.")

        except Exception as e:
            st.error(f"Hata oluştu: {e}")
