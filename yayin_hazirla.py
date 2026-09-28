# -*- coding: utf-8 -*-
"""Herkese acik depo paketini hazirlar: rhizoma-public/

ICERI ALINANLAR: olcum duzenegi, istemler, her ham cevap, deneme bazinda
sonuclar, imzali defterin dogrulanabilir ozeti, sayfa.

ASLA ALINMAYANLAR (yayinlanirsa olcum anlamini yitirir ya da guvenlik sorunu olur):
  - gizli testler (gorev_tohum.py, gorev_yeni.py, gorev_testleri_v2.py)
  - referans ve hatali cozumler (denetim_referanslari.py)
  - API anahtarlari (benchmark/.anahtarlar) ve imza ozel anahtari (*.key)
  - veritabani dosyalari

Kullanim: python yayin_hazirla.py
"""
import io
import json
import os
import re
import shutil

KOK = os.path.dirname(os.path.abspath(__file__))
HEDEF = os.path.join(os.path.dirname(KOK), "rhizoma-public")

YASAK_AD = ("gorev_tohum.py", "gorev_yeni.py", "gorev_testleri_v2.py",
            "denetim_referanslari.py", ".anahtarlar")
YASAK_UZANTI = (".key", ".db", ".sqlite", ".sqlite3", ".env")
# Anahtar sizintisina karsi son kontrol: dosya icerigi bu kaliplari icermemeli
SIZINTI = [re.compile(k) for k in (
    r"gsk_[A-Za-z0-9]{20,}",        # Groq
    r"sk-or-v1-[A-Za-z0-9]{20,}",   # OpenRouter
    r"AIza[A-Za-z0-9_\-]{30,}",     # Google
    r"sk-[A-Za-z0-9]{32,}",         # OpenAI benzeri
    r"-----BEGIN [A-Z ]*PRIVATE KEY",
    r"\b(?:org|user|proj|acct)_[A-Za-z0-9]{12,}\b",   # saglayici hesap kimlikleri
)]

KOPYALANACAK = [
    ("benchmark/kosum.py", "benchmark/kosum.py"),
    ("benchmark/saglayicilar.py", "benchmark/saglayicilar.py"),
    ("benchmark/modeller.py", "benchmark/modeller.py"),
    ("benchmark/rapor.py", "benchmark/rapor.py"),
    ("benchmark/anahtarlar.py", "benchmark/anahtarlar.py"),
    ("benchmark/yeniden_puanla.py", "benchmark/yeniden_puanla.py"),
    ("benchmark/sonuclar/sonuclar.jsonl", "sonuclar/her_deneme.jsonl"),
    ("engine/havuz.py", "engine/havuz.py"),
    ("engine/saglik.py", "engine/saglik.py"),
    ("engine/sandbox.py", "engine/sandbox.py"),
    ("sayfa/index.html", "sayfa/index.html"),
    ("sayfa/_uret.py", "sayfa/_uret.py"),
    ("sayfa/_veri.py", "sayfa/_veri.py"),
    ("sayfa/_metinler.py", "sayfa/_metinler.py"),
    ("sayfa/_parca_css.txt", "sayfa/_parca_css.txt"),
    ("yayin_hazirla.py", "yayin_hazirla.py"),
    ("defter_disa_aktar.py", "defter_disa_aktar.py"),
    ("yayin_sablon/README.md", "README.md"),
    ("yayin_sablon/LICENSE", "LICENSE"),
    # Yeni turlar (24.09.2026). Yollar ozel depodakiyle ayni tutulur ki
    # sayfa/_uret.py ve _turlar.py herkese acik depoda da calissin.
    ("benchmark/durustluk.py", "benchmark/durustluk.py"),
    ("benchmark/sonuclar/durustluk.jsonl", "benchmark/sonuclar/durustluk.jsonl"),
    ("benchmark/sonuclar/durustluk_elle.json", "benchmark/sonuclar/durustluk_elle.json"),
    ("benchmark/sonuclar/proje_degerlendirme.json", "benchmark/sonuclar/proje_degerlendirme.json"),
    ("sayfa/_turlar.py", "sayfa/_turlar.py"),
    # proje_gorevi.py BILEREK YOK: gizli testleri ve referans cozumu iceriyor.
]

# Klasor olarak kopyalanacak ham cevaplar (kaynak -> hedef)
HAM_KLASORLER = [
    ("benchmark/sonuclar/ham_durustluk", "benchmark/sonuclar/ham_durustluk"),
    ("benchmark/sonuclar/ham_proje", "benchmark/sonuclar/ham_proje"),
]

GITIGNORE = """__pycache__/
*.pyc
.anahtarlar
*.key
*.db
"""


def guvenli_mi(yol):
    ad = os.path.basename(yol)
    if ad in YASAK_AD or ad.endswith(YASAK_UZANTI):
        return False, "yasak dosya"
    try:
        icerik = io.open(yol, encoding="utf-8", errors="ignore").read()
    except Exception:
        return True, ""
    for kalip in SIZINTI:
        if kalip.search(icerik):
            return False, "icerikte anahtar gorunumlu metin"
    return True, ""


def gorev_ozeti():
    """Gizli testleri SIZDIRMADAN gorev listesi: slug, baslik, dil, zorluk, versiyon."""
    import sys
    sys.path.insert(0, KOK)
    from gorev_tohum import TOHUM_GOREVLER
    return [{k: g[k] for k in ("slug", "baslik", "dil", "zorluk", "versiyon")}
            for g in TOHUM_GOREVLER]


def ham_kopyala():
    kaynak = os.path.join(KOK, "benchmark", "sonuclar", "ham")
    hedef = os.path.join(HEDEF, "sonuclar", "ham")
    sayi = 0
    for kok, _, dosyalar in os.walk(kaynak):
        for d in dosyalar:
            y = os.path.join(kok, d)
            h = os.path.join(hedef, os.path.relpath(y, kaynak))
            os.makedirs(os.path.dirname(h), exist_ok=True)
            shutil.copy2(y, h)
            sayi += 1
    return sayi


def main():
    # Paketi tazele: yonettigimiz klasorleri temizle (klasorun kendisini silme,
    # Windows'ta acik bir kabuk klasoru kilitleyebiliyor).
    for alt in ("benchmark", "engine", "sayfa", "sonuclar", "defter"):
        shutil.rmtree(os.path.join(HEDEF, alt), ignore_errors=True)
    os.makedirs(HEDEF, exist_ok=True)

    atlanan = []
    for kaynak, hedef in KOPYALANACAK:
        y = os.path.join(KOK, kaynak)
        if not os.path.exists(y):
            atlanan.append((kaynak, "dosya yok"))
            continue
        ok, sebep = guvenli_mi(y)
        # Veri dosyalari (jsonl/json) once kopyalanir: icindeki hesap kimlikleri asagida
        # gizlenir, sonra son tarama yine calisir. Gercek bir anahtar kalirsa dosya silinir.
        if not ok and not (kaynak.endswith((".jsonl", ".json")) and sebep.startswith("icerikte")):
            atlanan.append((kaynak, sebep))
            continue
        h = os.path.join(HEDEF, hedef)
        os.makedirs(os.path.dirname(h), exist_ok=True)
        shutil.copy2(y, h)

    # Yeniden puanlama: dusen test adlari ve hata mesajlari gizli testin
    # bekledigi degerleri ele verir; yayin kopyasinda yalnizca sayi kalir.
    kaynak = os.path.join(KOK, "benchmark", "sonuclar", "yeniden_puan_v2.jsonl")
    if os.path.exists(kaynak):
        hedef_yol = os.path.join(HEDEF, "sonuclar", "yeniden_puan_v2.jsonl")
        os.makedirs(os.path.dirname(hedef_yol), exist_ok=True)
        with io.open(hedef_yol, "w", encoding="utf-8") as cikti:
            for satir in io.open(kaynak, encoding="utf-8"):
                if not satir.strip():
                    continue
                r = json.loads(satir)
                r["dusen_test_sayisi"] = len(r.pop("dusen_testler", []))
                cikti.write(json.dumps(r, ensure_ascii=False) + chr(10))

    ham = ham_kopyala()

    # Yeni turlarin ham cevaplari (.bak gibi ara dosyalar haric)
    for kaynak_k, hedef_k in HAM_KLASORLER:
        for kok, _, dosyalar in os.walk(os.path.join(KOK, kaynak_k)):
            for d in dosyalar:
                if not d.endswith(".txt"):
                    continue
                y = os.path.join(kok, d)
                h = os.path.join(HEDEF, hedef_k, os.path.relpath(y, os.path.join(KOK, kaynak_k)))
                os.makedirs(os.path.dirname(h), exist_ok=True)
                shutil.copy2(y, h)
                ham += 1

    # Proje gorevi test sonuclari: hata mesajlari gizli testin bekledigi degerleri
    # ele verebilir; yayin kopyasinda yalnizca gecen/toplam kalir.
    pt = os.path.join(KOK, "benchmark", "sonuclar", "proje_testleri.json")
    if os.path.exists(pt):
        veri = json.load(io.open(pt, encoding="utf-8"))
        sade = {k: {"A": v["A"], "B": v["B"]} for k, v in veri.items() if not k.endswith(".bak")}
        hedef_pt = os.path.join(HEDEF, "benchmark", "sonuclar", "proje_testleri.json")
        os.makedirs(os.path.dirname(hedef_pt), exist_ok=True)
        json.dump(sade, io.open(hedef_pt, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    io.open(os.path.join(HEDEF, ".gitignore"), "w", encoding="utf-8").write(GITIGNORE)

    # Imzali defteri disa aktar (defter/defter.jsonl, acik_anahtar.txt, dogrula.py)
    import subprocess, sys as _sys
    subprocess.run([_sys.executable, os.path.join(KOK, "defter_disa_aktar.py")], check=False)

    # Gizli testlerin ve defterin parmak izleri (parmak_izleri.json)
    subprocess.run([_sys.executable, os.path.join(KOK, "parmak_izi.py")], check=True)

    gorevler = gorev_ozeti()
    with io.open(os.path.join(HEDEF, "sonuclar", "gorevler.json"), "w", encoding="utf-8") as f:
        json.dump(gorevler, f, ensure_ascii=False, indent=1)

    # Saglayici hata mesajlari hesap kimligi tasiyabilir (ornegin Groq'un
    # "org_..." kurulus kimligi). Sifre degil ama hesabi tanimlar: gizlenir.
    kimlik = re.compile(r"\b(org|user|proj|acct)_[A-Za-z0-9]{12,}\b")
    for kok, _, dosyalar in os.walk(HEDEF):
        for d in dosyalar:
            if not d.endswith((".jsonl", ".json", ".txt", ".md")):
                continue
            y = os.path.join(kok, d)
            icerik = io.open(y, encoding="utf-8", errors="ignore").read()
            yeni = kimlik.sub(lambda m: m.group(1) + "_[gizlendi]", icerik)
            if yeni != icerik:
                io.open(y, "w", encoding="utf-8").write(yeni)

    # Son guvenlik taramasi: kopyalanan her dosyada anahtar araniyor
    bulgu = []
    for kok, _, dosyalar in os.walk(HEDEF):
        for d in dosyalar:
            y = os.path.join(kok, d)
            ok, sebep = guvenli_mi(y)
            if not ok:
                bulgu.append(os.path.relpath(y, HEDEF))
                os.remove(y)

    print(f"Paket: {HEDEF}")
    print(f"  ham cevap dosyasi : {ham}")
    print(f"  gorev ozeti       : {len(gorevler)} gorev (gizli testler YOK)")
    if atlanan:
        print("  alinmayanlar      :", atlanan)
    print("  guvenlik taramasi :", "temiz" if not bulgu else f"SILINDI {bulgu}")


if __name__ == "__main__":
    main()
