"""Rhizoma Benchmark — Model Saglayici Adaptorleri.

Her saglayici icin tek tip arayuz: sor(model_kimlik, prompt) -> (metin, ham_yanit, hata)
Hicbir dis bagimlilik yok; yalnizca standart kutuphane (urllib) kullanilir.

Desteklenen saglayicilar:
- ollama         : yerel, anahtar gerekmez (http://localhost:11434)
- openai_uyumlu  : Groq, GitHub Models, OpenRouter, Mistral (hepsi ayni protokol)
- gemini         : Google Generative Language API

API anahtarlari ortam degiskenlerinden okunur; kodun icine anahtar YAZILMAZ.
"""
import os
import json
import time
import urllib.request
import urllib.error

# Anahtarlari .anahtarlar dosyasindan ortama yukler (dosya .gitignore'dadir)
try:
    import anahtarlar  # noqa: F401
except ImportError:
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import anahtarlar  # noqa: F401


VARSAYILAN_ZAMAN_ASIMI = 180


class SaglayiciHatasi(Exception):
    """Model cagrisinda olusan, yeniden denenebilir veya kalici hata."""

    def __init__(self, mesaj, yeniden_denenebilir=False, durum=None):
        super().__init__(mesaj)
        self.yeniden_denenebilir = yeniden_denenebilir
        self.durum = durum


def _post_json(url, govde, basliklar=None, zaman_asimi=VARSAYILAN_ZAMAN_ASIMI):
    """JSON POST atar, JSON sozluk dondurur. Hata durumunda SaglayiciHatasi firlatir."""
    veri = json.dumps(govde).encode("utf-8")
    # User-Agent sart: bazi saglayicilarin Cloudflare korumasi (hata 1010)
    # varsayilan Python-urllib kimligini engelliyor.
    bas = {
        "Content-Type": "application/json",
        "User-Agent": "Rhizoma-Benchmark/1.0 (+https://rhizoma.ai)",
        "Accept": "application/json",
    }
    if basliklar:
        bas.update(basliklar)

    istek = urllib.request.Request(url, data=veri, headers=bas, method="POST")
    try:
        with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
            ham = yanit.read().decode("utf-8", errors="replace")
            return json.loads(ham)
    except urllib.error.HTTPError as e:
        govde_metni = ""
        try:
            govde_metni = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        # 5xx = gecici sunucu hatasi -> yeniden denenebilir.
        #
        # 429 ikiye ayrilir, cunku davranislari zit:
        #  - KOTA dolmasi (gunluk limit): tekrar denemek hem bosuna hem
        #    zararlidir, her deneme kotadan tekrar duser -> KALICI say.
        #  - HIZ SINIRI (dakikada N istek): kisa bir beklemeden sonra
        #    gecer -> YENIDEN DENE.
        alt = govde_metni.lower()
        hiz_siniri = ("rate limit" in alt or "rpm" in alt
                      or "retry shortly" in alt or "too many requests" in alt)
        tekrar = (500 <= e.code < 600) or (e.code == 429 and hiz_siniri)
        raise SaglayiciHatasi(f"HTTP {e.code}: {govde_metni}", yeniden_denenebilir=tekrar, durum=e.code)
    except urllib.error.URLError as e:
        raise SaglayiciHatasi(f"Baglanti hatasi: {e.reason}", yeniden_denenebilir=True)
    except json.JSONDecodeError as e:
        raise SaglayiciHatasi(f"Gecersiz JSON yanit: {e}", yeniden_denenebilir=True)


# --------------------------------------------------------------------------
# Ollama (yerel)
# --------------------------------------------------------------------------

def _ollama_sor(model, prompt, ayarlar):
    taban = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    govde = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    secenekler = {}
    if ayarlar.get("sicaklik") is not None:
        secenekler["temperature"] = ayarlar["sicaklik"]
    if secenekler:
        govde["options"] = secenekler
    # Akil yurutme (thinking) modu: kapatilirsa ayni cevap 2-3 kat hizli gelir.
    # Varsayilandan sapma oldugu icin RAPORDA acikca belirtilir.
    if ayarlar.get("dusunme") is False:
        govde["think"] = False

    yanit = _post_json(f"{taban}/api/chat", govde, zaman_asimi=ayarlar.get("zaman_asimi", 300))
    metin = (yanit.get("message") or {}).get("content", "")
    return metin, yanit


# --------------------------------------------------------------------------
# OpenAI uyumlu (Groq / GitHub Models / OpenRouter / Mistral)
# --------------------------------------------------------------------------

def _openai_uyumlu_sor(model, prompt, ayarlar):
    taban = ayarlar["taban_url"].rstrip("/")
    anahtar_adi = ayarlar["anahtar_ortam"]
    anahtar = os.environ.get(anahtar_adi, "").strip()
    if not anahtar:
        raise SaglayiciHatasi(
            f"API anahtari yok: {anahtar_adi} ortam degiskeni tanimli degil",
            yeniden_denenebilir=False,
        )

    govde = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if ayarlar.get("sicaklik") is not None:
        govde["temperature"] = ayarlar["sicaklik"]
    if ayarlar.get("azami_token"):
        govde["max_tokens"] = ayarlar["azami_token"]

    basliklar = {"Authorization": f"Bearer {anahtar}"}
    basliklar.update(ayarlar.get("ek_basliklar") or {})

    yanit = _post_json(f"{taban}/chat/completions", govde, basliklar,
                       zaman_asimi=ayarlar.get("zaman_asimi", VARSAYILAN_ZAMAN_ASIMI))
    secenekler = yanit.get("choices") or []
    if not secenekler:
        raise SaglayiciHatasi(f"Bos yanit: {str(yanit)[:300]}", yeniden_denenebilir=True)
    metin = (secenekler[0].get("message") or {}).get("content") or ""
    return metin, yanit


# --------------------------------------------------------------------------
# Google Gemini
# --------------------------------------------------------------------------

def _gemini_sor(model, prompt, ayarlar):
    anahtar = os.environ.get(ayarlar["anahtar_ortam"], "").strip()
    if not anahtar:
        raise SaglayiciHatasi(
            f"API anahtari yok: {ayarlar['anahtar_ortam']} ortam degiskeni tanimli degil",
            yeniden_denenebilir=False,
        )

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={anahtar}")
    govde = {"contents": [{"parts": [{"text": prompt}]}]}
    uretim = {}
    if ayarlar.get("sicaklik") is not None:
        uretim["temperature"] = ayarlar["sicaklik"]
    if uretim:
        govde["generationConfig"] = uretim

    yanit = _post_json(url, govde, zaman_asimi=ayarlar.get("zaman_asimi", VARSAYILAN_ZAMAN_ASIMI))
    adaylar = yanit.get("candidates") or []
    if not adaylar:
        raise SaglayiciHatasi(f"Bos yanit: {str(yanit)[:300]}", yeniden_denenebilir=True)
    parcalar = ((adaylar[0].get("content") or {}).get("parts") or [])
    metin = "".join(p.get("text", "") for p in parcalar)
    return metin, yanit


# --------------------------------------------------------------------------
# Ortak giris noktasi
# --------------------------------------------------------------------------

_SORUCULAR = {
    "ollama": _ollama_sor,
    "openai_uyumlu": _openai_uyumlu_sor,
    "gemini": _gemini_sor,
}


def sor(saglayici, model, prompt, ayarlar=None, deneme=3, bekleme=5):
    """
    Modele soruyu sorar. Gecici hatalarda ustel bekleyerek yeniden dener.

    Donus: (metin, ham_yanit_sozlugu)
    Kalici hatada SaglayiciHatasi firlatir.
    """
    ayarlar = dict(ayarlar or {})
    sorucu = _SORUCULAR.get(saglayici)
    if not sorucu:
        raise SaglayiciHatasi(f"Bilinmeyen saglayici: {saglayici}", yeniden_denenebilir=False)

    son_hata = None
    for i in range(deneme):
        try:
            return sorucu(model, prompt, ayarlar)
        except SaglayiciHatasi as e:
            son_hata = e
            if not e.yeniden_denenebilir or i == deneme - 1:
                raise
            time.sleep(bekleme * (2 ** i))
    raise son_hata
