# -*- coding: utf-8 -*-
"""Sayfanin sayilarini dogrudan olcum verisinden hesaplar.

Kaynaklar:
  benchmark/sonuclar/sonuclar.jsonl         her denemenin kaydi
  benchmark/sonuclar/yeniden_puan_v2.jsonl  sikilastirilmis testlerle yeniden puan
Kurallar:
  - Yalnizca havuzdaki 33 gorev (emekli gorevler haric), Ingilizce istem.
  - Yalnizca tam olculmus 12 model (99 deneme).
  - Versiyon 2 gorevlerde yeniden puan gecerlidir.
  - OLCULEMEZ: saglayicinin cikti siniri yuzunden kesilen cevaplar.
"""
import json
import os
import sys
from collections import Counter, defaultdict

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)
sys.path.insert(0, KOK)

try:
    # Ozel depo: gorev havuzu (gizli testlerle birlikte) burada.
    from gorev_tohum import TOHUM_GOREVLER  # noqa: E402
    SONUC = os.path.join(KOK, "benchmark", "sonuclar", "sonuclar.jsonl")
    V2 = os.path.join(KOK, "benchmark", "sonuclar", "yeniden_puan_v2.jsonl")
except ImportError:
    # Herkese acik depo: gizli testler yok; gorev listesi ve sonuclar sonuclar/ altinda.
    TOHUM_GOREVLER = json.load(open(os.path.join(KOK, "sonuclar", "gorevler.json"), encoding="utf-8"))
    SONUC = os.path.join(KOK, "sonuclar", "her_deneme.jsonl")
    V2 = os.path.join(KOK, "sonuclar", "yeniden_puan_v2.jsonl")

# Groq ucretsiz katmani Qwen3.8 27B'ye dakikada 1000 cikti token veriyor;
# bu cevap o sinirda yarida kesildi (kod blogu kapanmamis). Modelin hatasi sayilmaz.
OLCULEMEZ = {("Qwen3.8 27B (Groq)", "js-tik-makinesi", 1)}

ERISIM = [  # (ad icinde gecen, tablo etiketi)
    ("(OpenRouter)", "OpenRouter"),
    ("(Groq)", "Groq, free tier"),
    ("Gemini 3.1 Flash Lite", "Google AI Studio, free tier"),
    ("dusunme kapali", "Ollama, local, think off"),
    ("(yerel", "Ollama, local"),
]


def gorunen_ad(ad):
    return ad.split(" (")[0]


def erisim(ad):
    for parca, etiket in ERISIM:
        if parca in ad:
            return etiket
    return ""


def hesapla():
    gorevler = [g for g in TOHUM_GOREVLER]
    sira = [g["slug"] for g in gorevler]
    zorluk = {g["slug"]: g["zorluk"] for g in gorevler}

    son = {}
    for satir in open(SONUC, encoding="utf-8"):
        if satir.strip():
            x = json.loads(satir)
            if x["gorev"] in zorluk and x.get("istem_dili", "en") == "en":
                son[(x["model_ad"], x["gorev"], x["kosu"])] = x
    v2 = {}
    for satir in open(V2, encoding="utf-8"):
        if satir.strip():
            r = json.loads(satir)
            v2[(r["model_ad"], r["gorev"], r["kosu"])] = r

    hucre = defaultdict(dict)   # model -> (slug, kosu) -> durum
    for k, x in son.items():
        tur = x.get("cevap_turu")
        if tur == "hata":
            continue
        if k in OLCULEMEZ:
            d = "yok"
        elif tur == "cekimser":
            d = "cekimser"
        elif tur == "bos":
            d = "yok"
        else:
            ok = v2[k]["yeni_gecti"] if k in v2 else bool(x.get("sozunu_tuttu"))
            d = "dogru" if ok else "bozuk"
        hucre[k[0]][(k[1], k[2])] = d

    modeller = []
    for ad, h in hucre.items():
        if len(h) < 99:            # tam olculmemis (kotasi biten) modeller
            continue
        c = Counter(h.values())
        cevap = c["dogru"] + c["bozuk"]
        modeller.append({
            "ad": ad, "gorunen": gorunen_ad(ad), "erisim": erisim(ad),
            "deneme": len(h), "dogru": c["dogru"], "bozuk": c["bozuk"],
            "yok": c["yok"], "cekimser": c["cekimser"],
            "kapsama": (cevap + c["yok"]) / len(h),   # kod sunulan / deneme (bos cevap kapsama disi degil)
            "tutma": c["dogru"] / cevap if cevap else 0,
            "hucre": [h.get((s, k), "yok") for s in sira for k in (1, 2, 3)],
        })
    # kapsama: modelin bir cevap uretmeye giristigi denemeler. Bos/kesik cevap
    # "denedi ama sonuc yok" sayilir, cekimserlik kapsama disidir.
    for m in modeller:
        m["kapsama"] = (m["deneme"] - m["cekimser"]) / m["deneme"]
    modeller.sort(key=lambda m: (-m["tutma"], m["bozuk"], m["gorunen"]))

    zor = Counter()
    zor_top = Counter()
    gorev_bozuk = Counter()
    for m in modeller:
        for (s, k), d in ((sk, hucre[m["ad"]][sk]) for sk in hucre[m["ad"]]):
            if d in ("dogru", "bozuk"):
                zor_top[zorluk[s]] += 1
                if d == "dogru":
                    zor[zorluk[s]] += 1
                else:
                    gorev_bozuk[s] += 1
    return {
        "modeller": modeller,
        "sira": sira,
        "baslik": {g["slug"]: g["baslik"] for g in gorevler},
        "dil": {g["slug"]: g["dil"] for g in gorevler},
        "zorluk_yuzde": {z: round(100 * zor[z] / zor_top[z]) for z in zor_top},
        "gorev_bozuk": gorev_bozuk.most_common(),
        "toplam": {
            "deneme": sum(m["deneme"] for m in modeller),
            "bozuk": sum(m["bozuk"] for m in modeller),
            "yok": sum(m["yok"] for m in modeller),
            "cekimser": sum(m["cekimser"] for m in modeller),
        },
    }


def yuzde(x):
    return f"{round(100 * x)}%"


def tbody(v):
    satirlar = []
    for i, m in enumerate(v["modeller"]):
        lead = " lead" if i == 0 else ""
        satirlar.append(f"""          <tr>
            <td class="name">{m['gorunen']}</td><td class="host">{m['erisim']}</td>
            <td class="num">{m['deneme']}</td><td class="num">{yuzde(m['kapsama'])}</td><td class="num{lead}">{yuzde(m['tutma'])}</td><td class="num">{m['bozuk']}</td><td class="num">{m['cekimser']}</td>
          </tr>""")
    return "<tbody>\n" + "\n".join(satirlar) + "\n        </tbody>"


BASLIK = {"dogru": "worked", "bozuk": "broken, delivered as done",
          "yok": "no usable answer", "cekimser": "said I can't"}
SINIF = {"dogru": "", "bozuk": ' class="x"', "yok": ' class="e"', "cekimser": ' class="a"'}


def matris(v):
    satirlar = []
    for m in v["modeller"]:
        hucreler = "".join(f'<i{SINIF[d]} title="{BASLIK[d]}"></i>' for d in m["hucre"])
        satirlar.append(f"""      <div class="mrow">
        <div class="mlabel"><span>{m['gorunen']}</span><span>{m['bozuk']} broken of {m['deneme']}</span></div>
        <div class="cells">{hucreler}</div>
      </div>""")
    return '<div class="matrix">\n' + "\n".join(satirlar) + "\n    </div>"


if __name__ == "__main__":
    v = hesapla()
    for m in v["modeller"]:
        print(f"{m['gorunen']:<24}{m['erisim']:<30}{m['deneme']:>4}{yuzde(m['kapsama']):>6}{yuzde(m['tutma']):>6}{m['bozuk']:>4}{m['yok']:>3}{m['cekimser']:>3}")
    print(v["toplam"], v["zorluk_yuzde"])
    print(v["gorev_bozuk"][:8])
