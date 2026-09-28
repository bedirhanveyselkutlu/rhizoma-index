"""Rhizoma Test Havuzu Degerlendiricisi.
Yabanci kod veya agent tarafindan sunulan cozumleri, kontaminasyonsuz gizli
referans testlerine karsi izole Docker Sandbox icinde degerlendirir.

Guvenlik & Bagimsizlik:
- Harici paket bagimliligi olmadan (ag baglantisi gerektirmeden) Python ve Node.js
  container'larinda calisabilen yerel test kosturuculari icerir.
- Gizli test kaynak kodlari istemciye veya loglara asla sizdirilmaz.
"""
import os
import re
import json
import shutil
import tempfile

import store
from .sandbox import create_runner, is_docker_available
from .project import _parse_junit, _temiz


# Python Dahili Test Kosturucu (Ag ve pip gerektirmez, assert ve pytest.raises destekler)
_PY_RUNNER_SCRIPT = """import sys, os, inspect, xml.etree.ElementTree as ET
import builtins

# pytest.raises sahte nesnesi (eger gizli test pytest.raises kullaniyorsa)
class FakePytest:
    class RaisesContext:
        def __init__(self, expected_exc):
            self.expected_exc = expected_exc
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Beklenen hata firlatilmadi: {self.expected_exc.__name__}")
            return issubclass(exc_type, self.expected_exc)
    
    @staticmethod
    def raises(exc):
        return FakePytest.RaisesContext(exc)

sys.modules['pytest'] = FakePytest()
builtins.pytest = FakePytest()

try:
    import test_secret
except Exception as e:
    # Cozum kodunda syntax veya runtime import hatasi
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", tests="1", failures="1", errors="0")
    tc = ET.SubElement(suite, "testcase", name="import_solution")
    f = ET.SubElement(tc, "failure", message=str(e))
    f.text = str(e)
    ET.ElementTree(root).write("report.xml")
    sys.exit(0)

# test_ ile baslayan tum test fonksiyonlarini bul ve kostur
test_funcs = [getattr(test_secret, name) for name in dir(test_secret) if name.startswith("test_") and callable(getattr(test_secret, name))]
total = len(test_funcs) or 1
failures = []
passed = 0

for t in test_funcs:
    try:
        t()
        passed += 1
    except Exception as exc:
        failures.append((t.__name__, str(exc)))

# JUnit XML olustur
root = ET.Element("testsuites")
suite = ET.SubElement(root, "testsuite", tests=str(total), failures=str(len(failures)), errors="0")
for t in test_funcs:
    tc = ET.SubElement(suite, "testcase", name=t.__name__)
    fail_item = next((f for f in failures if f[0] == t.__name__), None)
    if fail_item:
        f_el = ET.SubElement(tc, "failure", message=fail_item[1])
        f_el.text = fail_item[1]

ET.ElementTree(root).write("report.xml")
"""

# JavaScript Dahili Test Kosturucu (Ag ve npm gerektirmez, jest/expect destekler)
_JS_RUNNER_SCRIPT = """const fs = require('fs');

let total = 0;
let passed = 0;
let failed = 0;
const failures = [];

function expect(actual) {
  return {
    toBe: (expected) => {
      if (actual !== expected) throw new Error(`Beklenen: ${expected}, Alinan: ${actual}`);
    },
    toEqual: (expected) => {
      const a = JSON.stringify(actual);
      const b = JSON.stringify(expected);
      if (a !== b) throw new Error(`Beklenen: ${b}, Alinan: ${a}`);
    },
    toBeNull: () => {
      if (actual !== null) throw new Error(`Beklenen null, Alinan: ${actual}`);
    },
    toBeUndefined: () => {
      if (actual !== undefined) throw new Error(`Beklenen undefined, Alinan: ${actual}`);
    },
    toBeDefined: () => {
      if (actual === undefined) throw new Error(`Tanimsiz deger (undefined)`);
    },
    toBeGreaterThan: (n) => {
      if (!(actual > n)) throw new Error(`Beklenen ${actual} > ${n}`);
    },
    toBeLessThan: (n) => {
      if (!(actual < n)) throw new Error(`Beklenen ${actual} < ${n}`);
    },
    not: {
      toBe: (expected) => {
        if (actual === expected) throw new Error(`Beklenmeyen degerle eslesme: ${actual}`);
      },
      toEqual: (expected) => {
        if (JSON.stringify(actual) === JSON.stringify(expected)) throw new Error(`Beklenmeyen eslesme`);
      }
    }
  };
}

global.expect = expect;
// Testler once toplanir, sonra SIRAYLA ve BEKLENEREK kosulur. (22.09.2026 duzeltmesi:
// eskiden promise donduren testler beklenmeden "gecti" sayiliyordu.)
const kayitli = [];
global.test = function(name, fn) { kayitli.push({ name, fn }); };
global.it = global.test;
const TEST_ZAMAN_ASIMI_MS = 5000;

global.jest = {
  fn: (impl) => {
    const f = function(...args) {
      f.mock.calls.push(args);
      return impl ? impl(...args) : undefined;
    };
    f.mock = { calls: [] };
    return f;
  },
  useFakeTimers: () => {},
  advanceTimersByTime: () => {}
};

function raporYaz() {
  const report = {
    numTotalTests: total,
    numPassedTests: passed,
    numFailedTests: failed,
    failures: failures
  };
  fs.writeFileSync('report.json', JSON.stringify(report, null, 2));
}

(async () => {
  try {
    require('./solution.test.js');
  } catch (err) {
    total = 1;
    failed = 1;
    failures.push({ name: 'load_test', error: err.message });
    raporYaz();
    process.exit(0);
  }
  // Test disinda yakalanmamis promise hatalari sureci dusurmesin
  process.on('unhandledRejection', () => {});
  for (const t of kayitli) {
    total++;
    try {
      let zamanlayici;
      const sure = new Promise((_, rej) => { zamanlayici = setTimeout(() => rej(new Error('test zaman asimi')), TEST_ZAMAN_ASIMI_MS); });
      await Promise.race([Promise.resolve().then(() => t.fn()), sure]);
      clearTimeout(zamanlayici);
      passed++;
    } catch (err) {
      failed++;
      failures.push({ name: t.name, error: (err && err.message) || String(err) });
    }
  }
  raporYaz();
  process.exit(0);
})();
"""


def _js_export_tamamla(cozum_kodu: str, gizli_test: str) -> str:
    """
    JS cozumlerinde eksik 'module.exports' satirini tamamlar.

    Neden gerekli: Modeller cogu zaman dogru algoritmayi yazip baslangic
    kodundaki export satirini dusuruyor. O zaman gizli test require() ile
    bos nesne alir ve DOGRU kod sifir puan alir. Bu, olcmek istedigimiz
    seyi (kod calisiyor mu) degil, boilerplate hafizasini olcer.

    Bu normalizasyon yalnizca PAKETLEMEYI tamamlar; algoritmaya dokunmaz.
    Cozumde zaten export varsa hicbir sey yapilmaz.
    """
    kod = cozum_kodu or ""
    if re.search(r"\bmodule\.exports\b|\bexports\.", kod):
        return kod

    # Gizli testin require ile istedigi adlari bul
    istenen = []
    for grup in re.findall(r"(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\(", gizli_test):
        for parca in grup.split(","):
            ad = parca.split(":")[0].strip()
            if ad:
                istenen.append(ad)

    if not istenen:
        return kod

    # Yalnizca cozumde GERCEKTEN tanimli olanlari disa aktar
    tanimli = []
    for ad in istenen:
        desen = rf"(?:function\s+{re.escape(ad)}\s*\(|class\s+{re.escape(ad)}\b|(?:const|let|var)\s+{re.escape(ad)}\s*=)"
        if re.search(desen, kod) and ad not in tanimli:
            tanimli.append(ad)

    if not tanimli:
        return kod

    return kod.rstrip() + "\n\nmodule.exports = { " + ", ".join(tanimli) + " };\n"


def havuz_degerlendir(gorev_slug: str, cozum_kodu: str, agent_adi: str = "Anonim") -> dict:
    """
    Belirli bir benchmark gorevini gizli testlerine karsi Sandbox'ta degerlendirir.
    Sonuc Ed25519 imzali ledger'a kaydedilir.
    """
    gorev = store.gorev_getir_gizli(gorev_slug)
    if not gorev:
        return {
            "kind": "havuz",
            "gorev": gorev_slug,
            "skor": None,
            "rozet": "bulunamadi",
            "not": f"Gorev havuzda bulunamadi: '{gorev_slug}'"
        }

    # Guvenlik Kontrolu: Sandbox zorunludur
    if not is_docker_available():
        return {
            "kind": "havuz",
            "gorev": gorev_slug,
            "baslik": gorev.get("baslik"),
            "dil": gorev.get("dil"),
            "zorluk": gorev.get("zorluk"),
            "agent": agent_adi,
            "skor": None,
            "rozet": "degerlendirilemedi",
            "not": "Guvenlik Engeli: Cozum kodunu calistirmak icin izole Docker Sandbox gereklidir (Docker daemon bulunamadi)."
        }

    dil = gorev["dil"].lower()
    gizli_test = gorev["gizli_test"]
    temp_dir = tempfile.mkdtemp(prefix="rz_havuz_")
    runner = None

    try:
        if dil == "python":
            sol_path = os.path.join(temp_dir, "solution.py")
            test_path = os.path.join(temp_dir, "test_secret.py")
            run_script_path = os.path.join(temp_dir, "run_tests.py")

            with open(sol_path, "w", encoding="utf-8") as f:
                f.write(cozum_kodu or "")
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(gizli_test)
            with open(run_script_path, "w", encoding="utf-8") as f:
                f.write(_PY_RUNNER_SCRIPT)

            runner = create_runner(workdir=temp_dir, lang="python", prefer_docker=True)
            rel_xml = "report.xml"
            host_xml = os.path.join(temp_dir, rel_xml)

            # Internetsiz, izole container test kosumu
            r = runner.run(["python", "run_tests.py"], timeout=60, network=False)
            runner.copy_out(rel_xml, host_xml)
            parsed = _parse_junit(host_xml)

        elif dil == "javascript":
            sol_path = os.path.join(temp_dir, "solution.js")
            test_path = os.path.join(temp_dir, "solution.test.js")
            run_script_path = os.path.join(temp_dir, "run_tests.js")

            with open(sol_path, "w", encoding="utf-8") as f:
                f.write(_js_export_tamamla(cozum_kodu or "", gizli_test))
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(gizli_test)
            with open(run_script_path, "w", encoding="utf-8") as f:
                f.write(_JS_RUNNER_SCRIPT)

            runner = create_runner(workdir=temp_dir, lang="javascript", prefer_docker=True)
            rel_json = "report.json"
            host_json = os.path.join(temp_dir, rel_json)

            # Internetsiz, izole container test kosumu
            r = runner.run(["node", "run_tests.js"], timeout=60, network=False)
            runner.copy_out(rel_json, host_json)
            
            data = None
            if os.path.exists(host_json):
                try:
                    with open(host_json, encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = None
            if data:
                parsed = {
                    "gecen": data.get("numPassedTests", 0),
                    "kalan": data.get("numFailedTests", 0),
                    "toplam": data.get("numTotalTests", 0)
                }
            else:
                parsed = None

        else:
            return {
                "kind": "havuz",
                "gorev": gorev_slug,
                "skor": None,
                "rozet": "desteklenmiyor",
                "not": f"Desteklenmeyen dil: {dil}"
            }

        # Sonuclari hesapla
        if not parsed or not parsed.get("toplam"):
            gecen = 0
            kalan = 1
            toplam = 1
            skor = 0
            rozet = "sorun"
            not_metin = "Test calistirilamadi veya syntax/runtime hatasi: " + _temiz(r.get("err") or r.get("out") or "")[:200]
        else:
            gecen = parsed["gecen"]
            kalan = parsed["kalan"]
            toplam = parsed["toplam"]
            skor = round(100 * gecen / toplam)
            rozet = "dogru" if kalan == 0 else "sorun"
            not_metin = f"{gecen}/{toplam} gizli referans testi basariyla gecti."

        sonuc = {
            "kind": "havuz",
            "gorev": gorev_slug,
            "baslik": gorev.get("baslik"),
            "dil": gorev.get("dil"),
            "zorluk": gorev.get("zorluk"),
            "agent": agent_adi,
            "gecen": gecen,
            "kalan": kalan,
            "toplam": toplam,
            "skor": skor,
            "rozet": rozet,
            "runner": runner.name if runner else "Unknown",
            "not": not_metin
        }

        # Ledger'a imzali ekle
        store.add("havuz", gorev_slug, sonuc)
        return sonuc

    finally:
        if runner:
            runner.cleanup()
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
