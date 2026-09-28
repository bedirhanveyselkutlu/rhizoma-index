"""Rhizoma Benchmark — API anahtarlarini guvenli yukleme.

Anahtarlar 'benchmark/.anahtarlar' dosyasindan okunup ortam degiskenlerine
aktarilir. Bu dosya .gitignore icindedir; ASLA depoya girmez.

Dosya bicimi (her satir bir anahtar):
    GEMINI_API_KEY=buraya_anahtar
    GROQ_API_KEY=buraya_anahtar
    GITHUB_TOKEN=buraya_anahtar

Zaten tanimli bir ortam degiskeni varsa dosya onu EZMEZ.
"""
import os

_BURASI = os.path.dirname(os.path.abspath(__file__))
ANAHTAR_DOSYA = os.path.join(_BURASI, ".anahtarlar")


def yukle(dosya=None):
    """Anahtar dosyasini okuyup ortam degiskenlerine aktarir. Yuklenen adlari dondurur."""
    yol = dosya or ANAHTAR_DOSYA
    yuklenen = []
    if not os.path.exists(yol):
        return yuklenen

    with open(yol, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            ad, _, deger = satir.partition("=")
            ad = ad.strip()
            deger = deger.strip().strip('"').strip("'")
            if not ad or not deger:
                continue
            if not os.environ.get(ad):
                os.environ[ad] = deger
            yuklenen.append(ad)
    return yuklenen


def durum():
    """Hangi anahtarlarin tanimli oldugunu (degerini gostermeden) raporlar."""
    yukle()
    beklenen = ["GEMINI_API_KEY", "GROQ_API_KEY", "GITHUB_TOKEN", "OPENROUTER_API_KEY"]
    out = {}
    for ad in beklenen:
        v = os.environ.get(ad, "")
        out[ad] = f"tanimli ({len(v)} karakter, ...{v[-4:]})" if v else "YOK"
    return out


# Ice aktarilir aktarilmaz yukle
yukle()


if __name__ == "__main__":
    for ad, d in durum().items():
        print(f"{ad:22} {d}")
