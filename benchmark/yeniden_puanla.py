"""Kayitli model cevaplarini yeni test surumuyle yeniden puanlar (API cagrisi YOK).

Modelin o gun verdigi ham cevap sonuclar/ham/ altinda saklidir. Bu betik ayni
kodu cikarir ve gorev_testleri_v2.py'deki sikilastirilmis testlerle Docker icinde
(internetsiz) yeniden calistirir. Orijinal sonuclar.jsonl'a DOKUNMAZ; sonuclari
sonuclar/yeniden_puan_v2.jsonl dosyasina yazar.

Kullanim:  python yeniden_puanla.py
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from gorev_tohum import TOHUM_GOREVLER            # noqa: E402
from engine.saglik import calistir                # noqa: E402
from kosum import yanit_coz, HAM_DIZIN, SONUC_DOSYA  # noqa: E402

CIKTI = os.path.join(os.path.dirname(SONUC_DOSYA), "yeniden_puan_v2.jsonl")
GOREV = {g["slug"]: g for g in TOHUM_GOREVLER}
# Versiyon 2 gorevlerin testleri (gorev_tohum.py sikilastirilmis testi uygular)
TESTLER_V2 = {g["slug"]: g["gizli_test"] for g in TOHUM_GOREVLER if g.get("versiyon") == 2}


def ham_oku(x):
    klasor = os.path.join(HAM_DIZIN, x["model_kimlik"].replace(":", "_").replace("/", "_"))
    yol = os.path.join(klasor, f"{x['gorev']}__k{x['kosu']}.txt")
    if not os.path.exists(yol):
        return None
    return open(yol, encoding="utf-8").read().split("===== HAM YANIT =====\n", 1)[-1]


def puanla(x):
    tur, kod = yanit_coz(ham_oku(x) or "")
    if tur != "cozum":
        return None
    s = calistir(GOREV[x["gorev"]], kod, docker=True, gizli_test=TESTLER_V2[x["gorev"]])
    return {
        "model_ad": x["model_ad"], "gorev": x["gorev"], "kosu": x["kosu"],
        "eski_gecti": bool(x.get("sozunu_tuttu")),
        "yeni_gecen": s["gecen"], "yeni_toplam": s["toplam"],
        "yeni_gecti": s["gecen"] == s["toplam"] and not x.get("uydurma_sayisi"),
        "dusen_testler": s["hatalar"],
    }


def main():
    kayitlar = {}
    for satir in open(SONUC_DOSYA, encoding="utf-8"):
        if satir.strip():
            x = json.loads(satir)
            if x["gorev"] in TESTLER_V2 and x.get("cevap_turu") == "cozum":
                kayitlar[(x["model_ad"], x["gorev"], x["kosu"])] = x   # son kayit gecerli
    isler = list(kayitlar.values())
    print(f"Yeniden puanlanacak cevap: {len(isler)}", flush=True)
    sonuclar = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, r in enumerate(ex.map(puanla, isler), 1):
            if r:
                sonuclar.append(r)
                if r["eski_gecti"] != r["yeni_gecti"]:
                    print(f"  DEGISTI {r['model_ad'][:26]:<26} {r['gorev']:<20} k{r['kosu']} "
                          f"{r['yeni_gecen']}/{r['yeni_toplam']} {r['dusen_testler'][:1]}", flush=True)
            if i % 50 == 0:
                print(f"  [{i}/{len(isler)}]", flush=True)
    with open(CIKTI, "w", encoding="utf-8") as f:
        for r in sonuclar:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    eski = sum(r["eski_gecti"] for r in sonuclar)
    yeni = sum(r["yeni_gecti"] for r in sonuclar)
    print(f"\nEski testle gecen: {eski}/{len(sonuclar)}   Yeni testle gecen: {yeni}/{len(sonuclar)}")
    print(f"Sonuc dosyasi: {CIKTI}")


if __name__ == "__main__":
    main()
