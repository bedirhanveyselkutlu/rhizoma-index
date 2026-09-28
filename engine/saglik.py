"""Rhizoma test sagligi denetimi.

Bir gorevin gizli testleri, gorev tanimiyla tutarli mi? Bunu uc soruyla olcer:
  1. Yalnizca tanima gore yazilmis bir REFERANS cozum butun testleri geciyor mu?
     (Gecmiyorsa test, tanimda yazmayan bir sey istiyordur.)
  2. Bilerek HATALI yazilmis cozumler en az bir testte dusuyor mu?
     (Dusmuyorsa test fazla gevsektir: yanlis kodu dogru sayar.)
  3. Bos baslangic kodu dusuyor mu?

Degerlendirme ledger'a YAZILMAZ; bu bir ic denetimdir. Kod yerel makinede
calisir, bu yuzden yalnizca kendi yazdigimiz referans/hatali cozumlerle kullanilir
(model ciktilari icin havuz_degerlendir ve Docker kullanilir).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from .havuz import _PY_RUNNER_SCRIPT, _JS_RUNNER_SCRIPT, _js_export_tamamla
from .sandbox import create_runner


def calistir(gorev: dict, kod: str, zaman_asimi: int = 60, docker: bool = False, gizli_test: str = None) -> dict:
    """Kodu gorevin gizli testlerine karsi calistirir, test bazinda sonuc dondurur.
    docker=True: model kodu icin (internetsiz kapali kutu). gizli_test: baska bir
    test surumuyle yeniden puanlamak icin."""
    test = gizli_test if gizli_test is not None else gorev["gizli_test"]
    d = tempfile.mkdtemp(prefix="rz_saglik_")
    runner = None
    try:
        py = gorev["dil"] == "python"
        if py:
            open(os.path.join(d, "solution.py"), "w", encoding="utf-8").write(kod)
            open(os.path.join(d, "test_secret.py"), "w", encoding="utf-8").write(test)
            open(os.path.join(d, "run_tests.py"), "w", encoding="utf-8").write(_PY_RUNNER_SCRIPT)
            komut, rapor = ["python", "run_tests.py"], "report.xml"
        else:
            open(os.path.join(d, "solution.js"), "w", encoding="utf-8").write(_js_export_tamamla(kod, test))
            open(os.path.join(d, "solution.test.js"), "w", encoding="utf-8").write(test)
            open(os.path.join(d, "run_tests.js"), "w", encoding="utf-8").write(_JS_RUNNER_SCRIPT)
            komut, rapor = ["node", "run_tests.js"], "report.json"
        p = os.path.join(d, rapor)
        if docker:
            runner = create_runner(workdir=d, lang=gorev["dil"], prefer_docker=True)
            if runner.name.lower().startswith("local"):
                raise RuntimeError("Docker yok: model kodu yerelde calistirilmaz")
            runner.run(komut, timeout=zaman_asimi, network=False)
            runner.copy_out(rapor, p)
        else:
            if py:
                komut[0] = sys.executable
            try:
                subprocess.run(komut, cwd=d, timeout=zaman_asimi, capture_output=True)
            except subprocess.TimeoutExpired:
                return {"gecen": 0, "toplam": 1, "hatalar": [("zaman_asimi", "")]}
        if not os.path.exists(p):
            return {"gecen": 0, "toplam": 1, "hatalar": [("rapor_yok", "")]}
        if py:
            hatalar, toplam = [], 0
            for tc in ET.parse(p).iter("testcase"):
                toplam += 1
                f = tc.find("failure")
                if f is not None:
                    hatalar.append((tc.get("name"), (f.get("message") or "")[:200]))
            return {"gecen": toplam - len(hatalar), "toplam": toplam, "hatalar": hatalar}
        r = json.load(open(p, encoding="utf-8"))
        return {"gecen": r["numPassedTests"], "toplam": r["numTotalTests"],
                "hatalar": [(f["name"], f["error"][:200]) for f in r.get("failures", [])]}
    finally:
        if runner:
            runner.cleanup()
        shutil.rmtree(d, ignore_errors=True)


def gorev_denetle(gorev: dict, referans: str, hatalilar: dict) -> dict:
    """Bir gorev icin saglik raporu. hatalilar: {aciklama: kod}"""
    ref = calistir(gorev, referans)
    bos = calistir(gorev, gorev.get("baslangic_kodu", ""))
    gevsek = []
    for ad, kod in hatalilar.items():
        s = calistir(gorev, kod)
        if s["gecen"] == s["toplam"]:
            gevsek.append(ad)          # yanlis kod butun testleri gecti
    sorunlar = []
    if ref["gecen"] != ref["toplam"]:
        sorunlar.append("TANIM-TEST UYUMSUZ: tanima uyan referans cozum dustu")
    if bos["gecen"] == bos["toplam"]:
        sorunlar.append("GEVSEK: bos baslangic kodu butun testleri geciyor")
    if gevsek:
        sorunlar.append("GEVSEK: yanlis cozum gecti -> " + "; ".join(gevsek))
    return {"slug": gorev["slug"], "referans": ref, "bos": bos, "gevsek": gevsek,
            "saglikli": not sorunlar, "sorunlar": sorunlar}
