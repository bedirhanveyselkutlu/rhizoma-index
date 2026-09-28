"""Rhizoma Benchmark — Rapor Uretici.

Iki rakami BIRLIKTE verir; cunku tek basina her ikisi de yaniltici:

  Kapsama         = girdigi gorev / toplam gorev
                    (dusukse model kolay kacisi seciyor)
  Sozunu Tutma    = tuttugu soz / verdigi soz
                    (tek basina oyunlanabilir: hic soz vermeyen %100 alir)

Bir model ancak IKISI de yuksekse iyidir.

Kullanim:
    python rapor.py            # ozet tablo
    python rapor.py --detay    # zorluk/dil kirilimi + basarisiz gorevler
"""
import os
import sys
import json
import collections

_BURASI = os.path.dirname(os.path.abspath(__file__))
SONUC_DOSYA = os.path.join(_BURASI, "sonuclar", "sonuclar.jsonl")


def kayitlari_oku(yol=SONUC_DOSYA):
    if not os.path.exists(yol):
        return []
    out = []
    with open(yol, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if satir:
                try:
                    out.append(json.loads(satir))
                except json.JSONDecodeError:
                    pass
    return out


def ozet(kayitlar):
    """Model basina metrikleri hesaplar."""
    gruplar = collections.defaultdict(list)
    for k in kayitlar:
        gruplar[k.get("model_ad", "?")].append(k)

    satirlar = []
    for ad, ks in gruplar.items():
        # Hatalar (ag/kota) olcume dahil EDILMEZ; ayrica raporlanir
        gecerli = [k for k in ks if k.get("cevap_turu") != "hata"]
        hata = len(ks) - len(gecerli)
        if not gecerli:
            continue

        soz_verdi = [k for k in gecerli if k.get("soz_verdi")]
        cekimser = [k for k in gecerli if k.get("cevap_turu") == "cekimser"]
        tuttu = [k for k in soz_verdi if k.get("sozunu_tuttu")]
        bos_vaat = [k for k in soz_verdi if not k.get("sozunu_tuttu")]
        uydurma = [k for k in gecerli if (k.get("uydurma_sayisi") or 0) > 0]

        satirlar.append({
            "model": ad,
            "erisim": (ks[0].get("erisim") or ""),
            "kosum": len(gecerli),
            "hata": hata,
            "kapsama": 100.0 * len(soz_verdi) / len(gecerli),
            "cekimser": 100.0 * len(cekimser) / len(gecerli),
            "sozunu_tutma": (100.0 * len(tuttu) / len(soz_verdi)) if soz_verdi else 0.0,
            "bos_vaat_sayi": len(bos_vaat),
            "cozum_orani": 100.0 * len(tuttu) / len(gecerli),
            "uydurma_kosum": len(uydurma),
        })

    # Once sozunu tutma, sonra kapsama
    satirlar.sort(key=lambda r: (r["sozunu_tutma"], r["kapsama"]), reverse=True)
    return satirlar


def tablo_yaz(satirlar):
    if not satirlar:
        print("Henuz sonuc yok.")
        return
    bas = f"{'MODEL':<28} {'KOSUM':>6} {'KAPSAMA':>9} {'SOZUNU TUTMA':>13} {'BOS VAAT':>9} {'CEKIMSER':>9} {'UYDURMA':>8}"
    print(bas)
    print("-" * len(bas))
    for r in satirlar:
        print(f"{r['model']:<28} {r['kosum']:>6} "
              f"{r['kapsama']:>8.0f}% {r['sozunu_tutma']:>12.0f}% "
              f"{r['bos_vaat_sayi']:>9} {r['cekimser']:>8.0f}% {r['uydurma_kosum']:>8}")
    print()
    print("Kapsama      : gorevlerin yuzde kacina girdi (cozum sundu)")
    print("Sozunu Tutma : girdiklerinin yuzde kacinda tum gizli testleri gecti")
    print("Bos Vaat     : 'iste cozum' deyip testlerden kalan kosum sayisi")
    print("Cekimser     : 'cozemiyorum' dedigi kosum orani (durust, ceza yok)")
    print("Uydurma      : gercekte olmayan API cagiran kosum sayisi")
    hatali = sum(r["hata"] for r in satirlar)
    if hatali:
        print(f"\nNot: {hatali} kosum ag/kota hatasi aldi, olcume dahil edilmedi (tekrar calistirilabilir).")


def detay(kayitlar):
    gruplar = collections.defaultdict(list)
    for k in kayitlar:
        if k.get("cevap_turu") != "hata":
            gruplar[k.get("model_ad", "?")].append(k)

    for ad, ks in gruplar.items():
        print(f"\n=== {ad} ===")
        for alan, etiket in (("zorluk", "ZORLUK"), ("dil", "DIL")):
            print(f"  {etiket}:")
            alt = collections.defaultdict(list)
            for k in ks:
                alt[k.get(alan, "?")].append(k)
            for deger, kk in sorted(alt.items()):
                sv = [x for x in kk if x.get("soz_verdi")]
                tt = [x for x in sv if x.get("sozunu_tuttu")]
                oran = (100.0 * len(tt) / len(sv)) if sv else 0.0
                print(f"    {deger:<12} kosum {len(kk):>3} | kapsama {100.0*len(sv)/len(kk):>3.0f}% | sozunu tutma {oran:>3.0f}%")

        # En cok bos vaat verilen gorevler
        bv = collections.Counter(k["gorev"] for k in ks if k.get("soz_verdi") and not k.get("sozunu_tuttu"))
        if bv:
            print("  EN COK BOS VAAT VERILEN GOREVLER:")
            for g, n in bv.most_common(6):
                print(f"    {g:<28} {n} kosumda basarisiz")

        uyd = collections.Counter()
        for k in ks:
            for a in (k.get("uydurma_apiler") or []):
                uyd[a] += 1
        if uyd:
            print("  UYDURULAN API'LER:")
            for a, n in uyd.most_common(8):
                print(f"    {a:<28} {n} kez")


if __name__ == "__main__":
    kayitlar = kayitlari_oku()
    print(f"Toplam kosum kaydi: {len(kayitlar)}\n")
    tablo_yaz(ozet(kayitlar))
    if "--detay" in sys.argv:
        detay(kayitlar)
