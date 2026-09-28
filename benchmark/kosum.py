"""Rhizoma Benchmark — Kosum Motoru.

Akis (her model x gorev x kosu icin):
  1. Modele standart istem gonderilir (dogru cikis kapisi dahil)
  2. Ham yanit diske kaydedilir (denetlenebilirlik icin)
  3. Yanit cozumlenir: kod mu, cekimser mi, hata mi
  4. Kod ise gizli testlere karsi Docker sandbox'ta calistirilir
  5. Uydurma API kontrolu yapilir
  6. Sonuc JSONL'e yazilir (kaldigi yerden devam edilebilir)

Kota bitse veya program cokse bile is kaybolmaz: ayni komut tekrar
calistirildiginda tamamlanmis kombinasyonlar atlanir.
"""
import os
import re
import sys
import json
import time
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

_BURASI = os.path.dirname(os.path.abspath(__file__))
_KOK = os.path.dirname(_BURASI)
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from engine.havuz import havuz_degerlendir          # noqa: E402
from engine.runners import check_apis               # noqa: E402
from engine.sandbox import is_docker_available      # noqa: E402
import store                                        # noqa: E402

from saglayicilar import sor, SaglayiciHatasi       # noqa: E402
from modeller import aktif_modeller, model_kimligi  # noqa: E402


CIKTI_DIZIN = os.path.join(_BURASI, "sonuclar")
HAM_DIZIN = os.path.join(CIKTI_DIZIN, "ham")
SONUC_DOSYA = os.path.join(CIKTI_DIZIN, "sonuclar.jsonl")

CEKIMSER_IFADELER = [
    "CANNOT_SOLVE", "CANNOT SOLVE", "I CANNOT SOLVE",
    "COZEMIYORUM", "ÇÖZEMIYORUM", "ÇÖZEMİYORUM",
]


# --------------------------------------------------------------------------
# Istem
# --------------------------------------------------------------------------

ISTEM_TR = """Asagidaki programlama gorevini coz.

GOREV: {baslik}

{aciklama}

BASLANGIC KODU ({dil}):
{baslangic_kodu}

KURALLAR:
- Fonksiyon adini ve imzasini AYNEN koru, degistirme.
- Yalnizca calisir kodu ver. Aciklama yazma.
- Kodu tek bir ``` blogu icinde ver.
- Once cozmeyi dene. Gercekten cozemiyorsan, hatali kod uretmek yerine
  yalnizca su tek satiri yaz: COZEMIYORUM"""

ISTEM_EN = """Solve the following programming task.

TASK: {baslik}

{aciklama}

STARTER CODE ({dil}):
{baslangic_kodu}

RULES:
- Keep the function name and signature EXACTLY as given.
- Return working code only. No explanations.
- Put the code in a single ``` block.
- Try to solve it first. If you genuinely cannot, write only this single
  line instead of producing faulty code: CANNOT_SOLVE"""


def istem_kur(gorev, dil_secimi="tr"):
    sablon = ISTEM_TR if dil_secimi == "tr" else ISTEM_EN
    return sablon.format(
        baslik=gorev.get("baslik", ""),
        aciklama=gorev.get("aciklama", ""),
        dil=gorev.get("dil", ""),
        baslangic_kodu=gorev.get("baslangic_kodu", ""),
    )


# --------------------------------------------------------------------------
# Yanit cozumleme
# --------------------------------------------------------------------------

def _dusunme_temizle(metin):
    """Bazi modellerin <think>...</think> bloklarini ayiklar."""
    return re.sub(r"<think>.*?</think>", "", metin, flags=re.DOTALL | re.IGNORECASE)


def kod_cikar(metin):
    """Markdown ``` bloklarindan kodu cikarir; blok yoksa None doner."""
    bloklar = re.findall(r"```[a-zA-Z0-9_+-]*\s*\n(.*?)```", metin, re.DOTALL)
    if bloklar:
        return max(bloklar, key=len).strip()
    return None


def yanit_coz(ham_metin):
    """
    Donus: (tur, kod)
      tur: "cozum" | "cekimser" | "bos"
    """
    metin = _dusunme_temizle(ham_metin or "").strip()
    if not metin:
        return "bos", None

    kod = kod_cikar(metin)

    # Cekimserlik: kod blogu YOKSA ve cekimser ifade geciyorsa
    buyuk = metin.upper()
    cekimser_var = any(i in buyuk for i in CEKIMSER_IFADELER)
    if cekimser_var and not kod:
        return "cekimser", None

    if kod:
        # Kod blogunun kendisi sadece cekimserlik yaziyorsa
        if any(i in kod.upper() for i in CEKIMSER_IFADELER) and len(kod) < 40:
            return "cekimser", None
        return "cozum", kod

    # Blok yok ama metin kod gibi duruyorsa kod say
    if re.search(r"^\s*(def |function |const |class |import |from )", metin, re.M):
        return "cozum", metin

    return "bos", None


# --------------------------------------------------------------------------
# Puanlama
# --------------------------------------------------------------------------

def uydurma_say(dil, kod):
    """Kodda gercekte olmayan API cagrisi sayisi."""
    try:
        bulgular = check_apis(dil, kod) or []
    except Exception:
        return 0, []
    uydurma = [b for b in bulgular if b.get("durum") == "uydurma"]
    return len(uydurma), [b.get("ref") for b in uydurma]


def tek_kosum(model, gorev, kosu_no, dil_secimi, gecikme):
    """Tek bir (model, gorev, kosu) kombinasyonunu calistirir ve sonuc sozlugu dondurur."""
    kimlik = model_kimligi(model)
    slug = gorev["slug"]
    istem = istem_kur(gorev, dil_secimi)

    ayarlar = {}
    for alan in ("taban_url", "anahtar_ortam", "ek_basliklar", "sicaklik",
                 "azami_token", "dusunme"):
        if alan in model:
            ayarlar[alan] = model[alan]

    kayit = {
        "zaman": datetime.datetime.now().isoformat(timespec="seconds"),
        "model_kimlik": kimlik,
        "model_ad": model["ad"],
        "erisim": model.get("erisim", ""),
        "gorev": slug,
        "dil": gorev.get("dil"),
        "zorluk": gorev.get("zorluk"),
        "kosu": kosu_no,
        "istem_dili": dil_secimi,
    }

    # 1) Modele sor
    t0 = time.time()
    try:
        ham_metin, _ = sor(model["saglayici"], model["model"], istem, ayarlar)
        kayit["sure_sn"] = round(time.time() - t0, 1)
    except SaglayiciHatasi as e:
        kayit.update({"sure_sn": round(time.time() - t0, 1), "cevap_turu": "hata",
                      "hata": str(e)[:300], "gecti": False, "soz_verdi": False})
        return kayit, ""

    # 2) Ham yaniti sakla
    _ham_kaydet(kimlik, slug, kosu_no, istem, ham_metin)

    # 3) Coz
    tur, kod = yanit_coz(ham_metin)
    kayit["cevap_turu"] = tur
    kayit["soz_verdi"] = (tur == "cozum")

    if tur != "cozum":
        kayit.update({"gecti": False, "skor": None, "uydurma_sayisi": 0})
        return kayit, ham_metin

    # 4) Uydurma API kontrolu
    uyd_sayi, uyd_liste = uydurma_say(gorev.get("dil", ""), kod)
    kayit["uydurma_sayisi"] = uyd_sayi
    kayit["uydurma_apiler"] = uyd_liste

    # 5) Gizli testlere karsi calistir
    try:
        sonuc = havuz_degerlendir(slug, kod, agent_adi=model["ad"])
    except Exception as e:
        kayit.update({"gecti": False, "skor": None, "hata": f"degerlendirme hatasi: {str(e)[:200]}"})
        return kayit, ham_metin

    kayit["skor"] = sonuc.get("skor")
    kayit["gecen_test"] = sonuc.get("gecen")
    kayit["toplam_test"] = sonuc.get("toplam")
    kayit["rozet"] = sonuc.get("rozet")
    kayit["gecti"] = (sonuc.get("kalan") == 0 and sonuc.get("toplam"))
    # Sozunu tuttu: cozum sundu, tum gizli testler gecti, uydurma API yok
    kayit["sozunu_tuttu"] = bool(kayit["gecti"]) and uyd_sayi == 0

    return kayit, ham_metin


# --------------------------------------------------------------------------
# Kalici depolama
# --------------------------------------------------------------------------

def _ham_kaydet(kimlik, slug, kosu_no, istem, yanit):
    klasor = os.path.join(HAM_DIZIN, kimlik.replace(":", "_").replace("/", "_"))
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, f"{slug}__k{kosu_no}.txt")
    with open(yol, "w", encoding="utf-8") as f:
        f.write("===== ISTEM =====\n")
        f.write(istem)
        f.write("\n\n===== HAM YANIT =====\n")
        f.write(yanit or "")


def _anahtar(kimlik, slug, kosu):
    return f"{kimlik}|{slug}|{kosu}"


def tamamlananlar():
    """Daha once tamamlanmis (model, gorev, kosu) anahtarlarini dondurur."""
    bitti = set()
    if not os.path.exists(SONUC_DOSYA):
        return bitti
    with open(SONUC_DOSYA, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir:
                continue
            try:
                k = json.loads(satir)
            except Exception:
                continue
            # Hatali kosumlar yeniden denenebilsin diye tamamlanmis sayilmaz
            if k.get("cevap_turu") == "hata":
                continue
            bitti.add(_anahtar(k.get("model_kimlik"), k.get("gorev"), k.get("kosu")))
    return bitti


_yazma_kilidi = threading.Lock()


def sonuc_yaz(kayit):
    os.makedirs(CIKTI_DIZIN, exist_ok=True)
    with _yazma_kilidi:
        with open(SONUC_DOSYA, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def _bildir(metin):
    """Paralel seritlerden gelen ciktilarin birbirine karismasini onler."""
    with _yazma_kilidi:
        print(metin, flush=True)


# --------------------------------------------------------------------------
# Ana dongu
# --------------------------------------------------------------------------

def calistir(kosu_sayisi=3, dil_secimi="tr", gorev_limiti=None, model_filtre=None,
             gorev_secimi=None, haric=None):
    if not is_docker_available():
        print("DURDURULDU: Docker calismiyor. Kodu guvenle calistirmak icin Docker Desktop acilmali.")
        return

    store.init()
    gorevler = store.gorev_listesi() or []
    if gorev_secimi:
        istenen = {s.strip() for s in gorev_secimi.split(",") if s.strip()}
        gorevler = [g for g in gorevler if g["slug"] in istenen]
    if gorev_limiti:
        gorevler = gorevler[:gorev_limiti]

    modeller = aktif_modeller()
    if model_filtre:
        modeller = [m for m in modeller if model_filtre.lower() in m["ad"].lower()]
    if haric:
        # Ornek: --haric OpenRouter  -> ucretli modelleri disarida birakir
        modeller = [m for m in modeller if haric.lower() not in m["ad"].lower()]

    if not modeller:
        print("Aktif model yok. benchmark/modeller.py icinde 'aktif': True yapin.")
        return

    bitti = tamamlananlar()

    # Gorevleri bir kez yukle (her serit ayni listeyi kullanir)
    tam_gorevler = [tg for tg in (store.gorev_getir(g["slug"]) for g in gorevler) if tg]

    def _model_kosusu(m):
        """Tek bir modelin tum gorevlerini sirayla isler."""
        kimlik = model_kimligi(m)
        gecikme = m.get("istek_araligi_sn", 0)
        yapildi = 0
        hedef = len(tam_gorevler) * kosu_sayisi
        _bildir(f"### BASLADI  {m['ad']}  ({m.get('erisim','')})")

        for tg in tam_gorevler:
            for kosu in range(1, kosu_sayisi + 1):
                if _anahtar(kimlik, tg["slug"], kosu) in bitti:
                    yapildi += 1
                    continue

                kayit, _ = tek_kosum(m, tg, kosu, dil_secimi, gecikme)
                sonuc_yaz(kayit)
                yapildi += 1

                tur = kayit.get("cevap_turu")
                if tur == "hata":
                    isaret = "HATA  "
                elif tur == "cekimser":
                    isaret = "CEKIMS"
                elif kayit.get("sozunu_tuttu"):
                    isaret = "TUTTU "
                else:
                    isaret = "TUTMDI"

                ek = ""
                if kayit.get("toplam_test"):
                    ek = f" {kayit.get('gecen_test')}/{kayit.get('toplam_test')}"
                if kayit.get("uydurma_sayisi"):
                    ek += f" [uydurma:{kayit['uydurma_sayisi']}]"
                if tur == "hata":
                    ek = " " + str(kayit.get("hata", ""))[:60]

                _bildir(f"  {m['ad'][:22]:<22} [{yapildi}/{hedef}] {isaret} {tg['slug']} k{kosu}{ek}")

                if gecikme:
                    time.sleep(gecikme)

        _bildir(f"### BITTI    {m['ad']}")

    # Yerel modeller ayni ekran kartini paylasir -> tek seritte sirayla.
    # Bulut modelleri ag-baglantili ve bagimsiz -> her biri kendi seridinde.
    yereller = [m for m in modeller if m.get("yerel")]
    bulutlar = [m for m in modeller if not m.get("yerel")]

    def _yerel_serit():
        for m in yereller:
            _model_kosusu(m)

    seritler = ([_yerel_serit] if yereller else []) + \
               [(lambda m=m: _model_kosusu(m)) for m in bulutlar]

    toplam_is = len(modeller) * len(tam_gorevler) * kosu_sayisi
    print(f"Model: {len(modeller)} ({len(yereller)} yerel, {len(bulutlar)} bulut)"
          f" | Gorev: {len(tam_gorevler)} | Kosu: {kosu_sayisi}")
    print(f"Toplam is: {toplam_is} | Daha once tamamlanan: {len(bitti)}")
    print(f"Paralel serit: {len(seritler)} (yerel modeller tek seritte sirayla)")
    print("-" * 66, flush=True)

    with ThreadPoolExecutor(max_workers=len(seritler)) as havuz:
        listeler = [havuz.submit(fn) for fn in seritler]
        for f in listeler:
            try:
                f.result()
            except Exception as e:
                print("SERIT HATASI:", str(e)[:200], flush=True)

    print("\nBitti. Sonuclar:", SONUC_DOSYA)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Rhizoma benchmark kosumu")
    ap.add_argument("--kosu", type=int, default=3, help="Her gorev icin kac kez calistirilsin")
    ap.add_argument("--dil", choices=["tr", "en"], default="tr", help="Istem dili")
    ap.add_argument("--gorev-limiti", type=int, default=None, help="Ilk N gorevle sinirla (deneme icin)")
    ap.add_argument("--model", default=None, help="Yalnizca adinda bu gecen modeli calistir")
    ap.add_argument("--gorev", default=None, help="Yalnizca bu gorevler (virgulle ayrilmis slug listesi)")
    ap.add_argument("--haric", default=None, help="Adinda bu gecen modelleri calistirma (orn. OpenRouter)")
    a = ap.parse_args()
    calistir(kosu_sayisi=a.kosu, dil_secimi=a.dil, gorev_limiti=a.gorev_limiti, model_filtre=a.model,
             gorev_secimi=a.gorev, haric=a.haric)
