"""Rhizoma Benchmark — Test edilecek modellerin kaydi.

Her kayit yayinda birebir bu haliyle raporlanir: hangi model, hangi kapidan,
hangi ayarla calistirildi. Seffaflik icin 'erisim' alani zorunludur.

Kota alanlari (istek_araligi_sn) ucretsiz katmanlarin hiz sinirlarina gore
ayarlanir; harness her cagri arasinda bu kadar bekler.
"""

# Model kimlikleri saglayicilarin canli model listelerinden dogrulandi;
# dogrulama tarihleri ilgili kayitlarin yaninda yazili.

MODELLER = [
    # ---- Yerel (anahtar gerekmez, sifir maliyet) ----
    {
        "ad": "Qwen2.5 Coder 7B (yerel)",
        "saglayici": "ollama",
        "model": "qwen2.5-coder:7b",
        "erisim": "Ollama, yerel makinede (RTX 3060)",
        "istek_araligi_sn": 0,
        "yerel": True,
        "aktif": True,
    },
    {
        # Akil yurutme KAPALI calistirilir: varsayilan modda cagri basina
        # ~90-133 sn suruyor (tek basina ~3 saat), kapaliyken ~19 sn ve
        # cevap uzunlugu ayni. Bu bir varsayilan sapmasidir, raporda yazilir.
        "ad": "Qwen3 8B (yerel, dusunme kapali)",
        "saglayici": "ollama",
        "model": "qwen3:8b",
        "dusunme": False,
        "erisim": "Ollama, yerel makinede (RTX 3060), think=False",
        "istek_araligi_sn": 0,
        "yerel": True,
        "aktif": True,
    },

    # ---- Ucretsiz API katmanlari (anahtar gerektirir) ----
    # Anahtar yoksa harness bu modelleri otomatik atlar.
    {
        # Takma ad (gemini-flash-latest) KULLANILMAZ: zamanla degisir,
        # yayinlanan sonuc tekrar uretilemez olur. Sabit surum secilir.
        # 3.8 Flash'in ucretsiz gunluk kotasi cok dar: iki gunde toplam 18 kosum
        # yapilabildi, 99'a ulasmasi ~12 gun surerdi. Kota MODEL BASINA ayri
        # oldugu icin kotasi olan diger Gemini modelleriyle devam ediliyor.
        # 18 kosumluk kismi veri saklandi, raporda "tamamlanmadi" diye gecer.
        "ad": "Gemini 3.8 Flash",
        "saglayici": "gemini",
        "model": "gemini-3.8-flash",          # 14.09.2026'da API listesinden dogrulandi
        "erisim": "Google AI Studio ucretsiz katman",
        "anahtar_ortam": "GEMINI_API_KEY",
        "istek_araligi_sn": 4,
        "aktif": False,
    },
    {
        # Ucretsiz kotasi 6 kosumda doldu. Ayni model OpenRouter uzerinden
        # olculuyor; bu kayit kapali birakilir (6 kosumluk kismi veri durur).
        "ad": "Gemini 3.7 Flash",
        "saglayici": "gemini",
        "model": "gemini-3.7-flash",          # 19.09.2026'da kotasi dogrulandi
        "erisim": "Google AI Studio ucretsiz katman",
        "anahtar_ortam": "GEMINI_API_KEY",
        "istek_araligi_sn": 4,
        "aktif": False,
    },
    {
        "ad": "Gemini 3.1 Flash Lite",
        "saglayici": "gemini",
        "model": "gemini-3.1-flash-lite",     # 19.09.2026'da kotasi dogrulandi
        "erisim": "Google AI Studio ucretsiz katman",
        "anahtar_ortam": "GEMINI_API_KEY",
        "istek_araligi_sn": 3,
        "aktif": True,
    },
    # NOT: GitHub Models 30 Temmuz 2026'da KAPATILDI (GitHub kendi dokumani).
    # GPT ve DeepSeek'e o yoldan ucretsiz erisim artik yok.
    # Asagidaki Groq modelleri 14.09.2026'da canli API listesinden dogrulandi.
    {
        "ad": "GPT-OSS 120B (Groq)",
        "saglayici": "openai_uyumlu",
        "model": "openai/gpt-oss-120b",
        "taban_url": "https://api.groq.com/openai/v1",
        "anahtar_ortam": "GROQ_API_KEY",
        "erisim": "Groq ucretsiz katman",
        # Groq varsayilani 2048 cikti token; akil yuruten modeller bunu
        # dusunmeye harcayip bos/kesik cevap veriyordu (21.09.2026 teshisi).
        "azami_token": 8000,
        "istek_araligi_sn": 45,               # bedava katman: dakikada 8000 token (TPM)
        "aktif": True,
    },
    {
        "ad": "GPT-OSS 20B (Groq)",
        "saglayici": "openai_uyumlu",
        "model": "openai/gpt-oss-20b",
        "taban_url": "https://api.groq.com/openai/v1",
        "anahtar_ortam": "GROQ_API_KEY",
        "erisim": "Groq ucretsiz katman",
        # Groq varsayilani 2048 cikti token; akil yuruten modeller bunu
        # dusunmeye harcayip bos/kesik cevap veriyordu (21.09.2026 teshisi).
        "azami_token": 8000,
        "istek_araligi_sn": 45,
        "aktif": True,
    },
    {
        # Yerel Qwen 7B/8B ile birlikte boyut karsilastirmasi saglar:
        # "daha buyuk model daha mi durust?" sorusu.
        "ad": "Qwen3.8 27B (Groq)",
        "saglayici": "openai_uyumlu",
        "model": "qwen/qwen3.8-27b",
        "taban_url": "https://api.groq.com/openai/v1",
        "anahtar_ortam": "GROQ_API_KEY",
        "erisim": "Groq ucretsiz katman",
        # Groq varsayilani 2048 cikti token; akil yuruten modeller bunu
        # dusunmeye harcayip bos/kesik cevap veriyordu (21.09.2026 teshisi).
        "azami_token": 1000,                 # bedava katman: dakikada 1000 cikti token (OTPM)
        "istek_araligi_sn": 65,
        "aktif": True,
    },
]


# ---- OpenRouter (tek bakiye, tum saglayicilar) ----
# Model kimlikleri 21.09.2026'da OpenRouter canli katalogundan dogrulandi.
# AMAC: her aileden IKI SURUM olcup "yeni surum daha mi durust?" sorusunu
# cevaplamak. Gemini burada AI Studio ucretsiz katmanindan FARKLI bir kapidan
# geliyor; bu yuzden ayri kayit olarak tutulur, eski kismi veriyle karistirilmaz.
_OR = "https://openrouter.ai/api/v1"

MODELLER += [
    {"ad": "GPT-6 Astra (OpenRouter)", "saglayici": "openai_uyumlu",
     "model": "openai/gpt-6-astra", "taban_url": _OR,
     "anahtar_ortam": "OPENROUTER_API_KEY",
     "erisim": "OpenRouter, ucretli", "azami_token": 3000, "istek_araligi_sn": 3.5, "aktif": True},

    {"ad": "GPT-5.5 (OpenRouter)", "saglayici": "openai_uyumlu",
     "model": "openai/gpt-5.5", "taban_url": _OR,
     "anahtar_ortam": "OPENROUTER_API_KEY",
     "erisim": "OpenRouter, ucretli", "azami_token": 3000, "istek_araligi_sn": 3.5, "aktif": True},

    {"ad": "Claude Fable 5.1 (OpenRouter)", "saglayici": "openai_uyumlu",
     "model": "anthropic/claude-fable-5.1", "taban_url": _OR,
     "anahtar_ortam": "OPENROUTER_API_KEY",
     "erisim": "OpenRouter, ucretli", "azami_token": 3000, "istek_araligi_sn": 3.5, "aktif": True},
    # 24.09.2026: yalnizca durustluk turu icin eklendi (kod turunda olculmedi).
    # aktif=False: kod turu (kosum.py) bu modeli calistirmasin.
    {"ad": "Claude Opus 5.5 (OpenRouter)", "saglayici": "openai_uyumlu",
     "model": "anthropic/claude-opus-5.5", "taban_url": _OR,
     "anahtar_ortam": "OPENROUTER_API_KEY",
     "erisim": "OpenRouter, ucretli", "azami_token": 3000, "istek_araligi_sn": 3.5, "aktif": False},

    {"ad": "Claude Fable 5 (OpenRouter)", "saglayici": "openai_uyumlu",
     "model": "anthropic/claude-fable-5", "taban_url": _OR,
     "anahtar_ortam": "OPENROUTER_API_KEY",
     "erisim": "OpenRouter, ucretli", "azami_token": 3000, "istek_araligi_sn": 3.5, "aktif": True},

    {"ad": "Gemini 3.8 Flash (OpenRouter)", "saglayici": "openai_uyumlu",
     "model": "google/gemini-3.8-flash", "taban_url": _OR,
     "anahtar_ortam": "OPENROUTER_API_KEY",
     "erisim": "OpenRouter, ucretli", "azami_token": 3000, "istek_araligi_sn": 3.5, "aktif": True},

    {"ad": "Gemini 3.7 Flash (OpenRouter)", "saglayici": "openai_uyumlu",
     "model": "google/gemini-3.7-flash", "taban_url": _OR,
     "anahtar_ortam": "OPENROUTER_API_KEY",
     "erisim": "OpenRouter, ucretli", "azami_token": 3000, "istek_araligi_sn": 3.5, "aktif": True},
]


def aktif_modeller():
    """Yalnizca 'aktif' isaretli modelleri dondurur."""
    return [m for m in MODELLER if m.get("aktif")]


def model_kimligi(m):
    """Sonuc dosyalarinda ve ledger'da kullanilacak sabit kimlik."""
    return f"{m['saglayici']}:{m['model']}"
