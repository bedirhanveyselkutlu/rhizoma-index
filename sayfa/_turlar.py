# -*- coding: utf-8 -*-
"""Sayfanin yeni turlarini (proje gorevi, tuzaklar, eski/yeni) veriden uretir.

Kaynaklar (benchmark/sonuclar/):
  durustluk.jsonl + ham_durustluk/ + durustluk_elle.json   tuzak turu (elle etiket otomatigi ezer)
  proje_degerlendirme.json                                 proje gorevi, elle degerlendirme
  proje_testleri.json                                      proje gorevindeki kodun Docker test sonucu
"""
import json
import os
import sys

BURASI = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(BURASI), "benchmark")
SONUC = os.path.join(BENCH, "sonuclar")

# Sayfadaki sira ve gorunen adlar. (ic ad, gorunen ad, erisim etiketi)
MODELLER = [
    ("Claude Opus 5.5 (OpenRouter)", "Claude Opus 5.5", "OpenRouter"),
    ("GPT-6 Astra (OpenRouter)", "GPT-6 Astra", "OpenRouter"),
    ("Claude Fable 5.1 (OpenRouter)", "Claude Fable 5.1", "OpenRouter"),
    ("Gemini 3.8 Flash (OpenRouter)", "Gemini 3.8 Flash", "OpenRouter"),
    ("Gemini 3.1 Flash Lite", "Gemini 3.1 Flash Lite", "Google AI Studio, free tier"),
    ("Qwen3 8B (yerel, dusunme kapali)", "Qwen3 8B", "Ollama, local, think off"),
    ("Qwen2.5 Coder 7B (yerel)", "Qwen2.5 Coder 7B", "Ollama, local"),
]

# Eski -> yeni karsilastirmasi (yalnizca iki turda da olculen aile)
ESKI_YENI = [
    ("Qwen2.5 Coder 7B (yerel)", "Qwen2.5 Coder 7B", "09/2024"),   # iki dilde de okunur
    ("Qwen3 8B (yerel, dusunme kapali)", "Qwen3 8B", "04/2025"),
]


def durustluk():
    """Model -> {'tuzak': Counter, 'kontrol': Counter}"""
    from collections import Counter
    sys.path.insert(0, BENCH)
    import durustluk as d
    sayim = {}
    for (m, _g, _k), (etiket, _kaynak, x) in d.son_etiketler().items():
        s = sayim.setdefault(m, {"tuzak": Counter(), "kontrol": Counter()})
        s[x["tur"]][etiket] += 1
    return sayim


def proje():
    yol = os.path.join(SONUC, "proje_degerlendirme.json")
    return json.load(open(yol, encoding="utf-8"))["modeller"]


def _h(v):
    return str(v)


def tablo_proje(p):
    satir = []
    for ic, ad, erisim in MODELLER:
        if ic not in p:
            continue
        x = p[ic]
        kod = sum(x[g] == "CALISIYOR" for g in ("A", "B"))
        durust = sum(x[g] == "DURUST" for g in ("C", "D", "E", "F", "G"))
        yanlis = len(x["rapor_yanlis"])
        vurgu = ' class="num bad"' if yanlis else ' class="num good"'
        satir.append(f"""          <tr>
            <td class="name">{ad}</td><td class="host">{erisim}</td>
            <td class="num">{kod}/2</td><td class="num">{durust}/5</td><td{vurgu}>{yanlis}</td>
          </tr>""")
    return "<tbody>\n" + "\n".join(satir) + "\n        </tbody>"


def tablo_tuzak(s):
    satir = []
    for ic, ad, erisim in MODELLER:
        if ic not in s:
            continue
        t = s[ic]["tuzak"]
        n = sum(t.values())
        vurgu = ' class="num bad"' if t["YANILTICI"] else ' class="num good"'
        satir.append(f"""          <tr>
            <td class="name">{ad}</td><td class="host">{erisim}</td>
            <td class="num">{n}</td><td class="num">{t['DURUST']}</td><td class="num">{t['KISMEN']}</td><td{vurgu}>{t['YANILTICI']}</td>
          </tr>""")
    return "<tbody>\n" + "\n".join(satir) + "\n        </tbody>"


def tablo_eski_yeni(s, p):
    satir = []
    for ic, ad, yil in ESKI_YENI:
        t = s[ic]["tuzak"]
        n = sum(t.values())
        yanlis = len(p[ic]["rapor_yanlis"]) if ic in p else "&ndash;"
        # Yalin sayilar (toplamlar tablo aciklamasinda): telefonda tablo ekrana sigsin
        satir.append(f"""          <tr>
            <td class="name">{ad}<small class="yil">{yil}</small></td>
            <td class="num">{t['DURUST']}</td><td class="num">{t['KISMEN']}</td><td class="num bad">{t['YANILTICI']}</td><td class="num bad">{yanlis}</td>
          </tr>""")
    return "<tbody>\n" + "\n".join(satir) + "\n        </tbody>"


def kontrol_ozeti(s):
    """Kontrol (ikiz) gorevlerini kosan modellerde toplam cozulen / toplam."""
    cozdu = sum(v["kontrol"]["COZDU"] for v in s.values())
    top = sum(sum(v["kontrol"].values()) for v in s.values())
    return cozdu, top


if __name__ == "__main__":
    s = durustluk()
    p = proje()
    for ic, ad, _ in MODELLER:
        t = s.get(ic, {}).get("tuzak", {})
        print(f"{ad:<22} tuzak {dict(t)} | proje yanlis {len(p[ic]['rapor_yanlis']) if ic in p else '-'}")
    print("kontrol:", kontrol_ozeti(s))
