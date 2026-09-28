# -*- coding: utf-8 -*-
"""Imzali defteri disariya aktarir: rhizoma-public/defter/

Cikti:
  defter.jsonl       her satir bir kayit: ts, kind, claim, result, prev, hash, sig, pubkey
  acik_anahtar.txt   Ed25519 acik anahtari ve parmak izi
  dogrula.py         bagimsiz dogrulayici (bu depodan hicbir sey import etmez)

Boylece herhangi biri kayitlarin sonradan degistirilmedigini kendi basina
kontrol edebilir. Gizli test iceren bir alan yoktur.
"""
import io
import json
import os
import sqlite3

KOK = os.path.dirname(os.path.abspath(__file__))
HEDEF = os.path.join(os.path.dirname(KOK), "rhizoma-public", "defter")

DOGRULAYICI = '''# -*- coding: utf-8 -*-
"""Rhizoma defterini bagimsiz dogrular.  Kullanim: python dogrula.py

Ne yapar:
  1. Her kaydin hash'ini icerikten yeniden hesaplar (sha256, kanonik JSON).
  2. Zincirin kopmadigini kontrol eder (her kaydin prev'i bir oncekinin hash'i).
  3. Ed25519 imzalarini acik anahtarla dogrular (pynacl ya da cryptography varsa).
"""
import hashlib
import json
import os

GENESIS = "0" * 64
BURASI = os.path.dirname(os.path.abspath(__file__))


def kanonik_hash(rec):
    payload = {k: rec[k] for k in rec if k not in ("hash", "sig", "pubkey")}
    ham = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(ham.encode("utf-8")).hexdigest()


def imza_dogrulayici():
    try:
        from nacl.signing import VerifyKey        # pynacl
        def f(mesaj, imza_hex, acik_hex):
            VerifyKey(bytes.fromhex(acik_hex)).verify(mesaj.encode(), bytes.fromhex(imza_hex))
            return True
        return f
    except Exception:
        pass
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        def f(mesaj, imza_hex, acik_hex):
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(acik_hex)).verify(
                bytes.fromhex(imza_hex), mesaj.encode())
            return True
        return f
    except Exception:
        return None


def main():
    kayitlar = []
    with open(os.path.join(BURASI, "defter.jsonl"), encoding="utf-8") as f:
        for satir in f:
            if satir.strip():
                kayitlar.append(json.loads(satir))
    dogrula = imza_dogrulayici()
    prev = GENESIS
    imzali = 0
    gizli = 0
    for i, r in enumerate(kayitlar):
        if r["prev"] != prev:
            print("KOPUK ZINCIR, kayit", i); return
        if "claim" in r:
            rec = {"ts": r["ts"], "kind": r["kind"], "claim": r["claim"],
                   "result": r["result"], "prev": r["prev"]}
            if kanonik_hash(rec) != r["hash"]:
                print("ICERIK DEGISMIS, kayit", i); return
        else:
            # Olcumle ilgisi olmayan ic kayit: icerigi yayinlanmadi. Zincirdeki
            # yeri ve imzasi yine dogrulanir, yani sessizce eklenip cikarilamaz.
            gizli += 1
        if r.get("sig") and dogrula:
            try:
                dogrula(r["hash"], r["sig"], r["pubkey"])
                imzali += 1
            except Exception:
                print("IMZA GECERSIZ, kayit", i); return
        prev = r["hash"]
    print("TAMAM: %d kayit, zincir saglam, %d imza dogrulandi." % (len(kayitlar), imzali))
    print("  icerigi acik: %d | icerigi gizli ic kayit: %d" % (len(kayitlar) - gizli, gizli))
    if not dogrula:
        print("(Imza dogrulamasi atlandi: pynacl ya da cryptography kurulu degil.)")


if __name__ == "__main__":
    main()
'''


def main():
    os.makedirs(HEDEF, exist_ok=True)
    db = os.path.join(KOK, "rhizoma.db")
    if not os.path.exists(db):
        adaylar = [d for d in os.listdir(KOK) if d.endswith(".db")]
        if not adaylar:
            print("Veritabani bulunamadi")
            return
        db = os.path.join(KOK, adaylar[0])
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT ts,kind,claim,result,prev,hash,sig,pubkey,etiket FROM runs ORDER BY id ASC").fetchall()
    n = 0
    with io.open(os.path.join(HEDEF, "defter.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            if r["etiket"] == "yayin":
                kayit = {
                    "ts": r["ts"], "kind": r["kind"], "claim": r["claim"],
                    "result": json.loads(r["result"]) if isinstance(r["result"], str) else r["result"],
                    "prev": r["prev"], "hash": r["hash"], "sig": r["sig"], "pubkey": r["pubkey"],
                    "etiket": "yayin",
                }
            else:
                # Ic kayit (gelistirme denemeleri, demo agent'lar, hata ayiklama):
                # icerigi yerel dosya yolu ve kisisel bilgi tasiyabilir, yayinlanmaz.
                # hash, prev ve imza kalir; zincir yine bastan sona dogrulanir.
                kayit = {
                    "ts": r["ts"], "kind": r["kind"],
                    "prev": r["prev"], "hash": r["hash"], "sig": r["sig"], "pubkey": r["pubkey"],
                    "etiket": "dahili",
                }
            f.write(json.dumps(kayit, ensure_ascii=False, sort_keys=False) + "\n")
            n += 1
    io.open(os.path.join(HEDEF, "dogrula.py"), "w", encoding="utf-8").write(DOGRULAYICI)

    import sys
    sys.path.insert(0, KOK)
    import crypto
    io.open(os.path.join(HEDEF, "acik_anahtar.txt"), "w", encoding="utf-8").write(
        "Ed25519 public key (raw, hex):" + chr(10) + crypto.get_public_key_raw_hex() + chr(10) + chr(10)
        + "Fingerprint: " + crypto.get_fingerprint() + chr(10))
    print("Defter disa aktarildi: %s (%d kayit)" % (HEDEF, n))


if __name__ == "__main__":
    main()
