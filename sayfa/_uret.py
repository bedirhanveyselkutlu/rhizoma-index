# -*- coding: utf-8 -*-
"""Rhizoma Index sayfasini iki dilli olarak uretir.

Girdi : _metinler.py (EN/TR metinler), _parca_css.txt, _veri.py (tablo, deneme
        haritasi, zorluk ve gorev sayilari DOGRUDAN olcum verisinden hesaplanir)
Cikti : index.html

Ingilizce metin HTML'in icinde durur; JavaScript calismasa da sayfa okunur.
Turkce, dil dugmesiyle ya da tarayici dili Turkce ise acilista uygulanir.
"""
import io
import json
import os
import re

from _metinler import T, HOST, GOREV_AD
import _veri

BURASI = os.path.dirname(os.path.abspath(__file__))

# Herkese acik depo (hata bildirimi ve yayimlanan her sey)
DEPO = "https://github.com/bedirhanveyselkutlu/rhizoma-index"

# Surum ciftleri: (saglayici, eski model adi, yeni model adi). Sayilar veriden.
SURUM_CIFTLERI = [
    ("Google",    "Gemini 3.7 Flash (OpenRouter)", "Gemini 3.8 Flash (OpenRouter)"),
    ("OpenAI",    "GPT-5.5 (OpenRouter)",          "GPT-6 Astra (OpenRouter)"),
    ("Anthropic", "Claude Fable 5 (OpenRouter)",   "Claude Fable 5.1 (OpenRouter)"),
]

# Harita hucre aciklamalari (Ingilizce -> Turkce)
HUCRE_TR = {
    "worked": "çalıştı",
    "broken, delivered as done": "hatalı, bitmiş gibi teslim edildi",
    "no usable answer": "kullanılabilir cevap yok",
    "said I can't": "yapamıyorum dedi",
}


def oku(ad):
    return io.open(os.path.join(BURASI, ad), encoding="utf-8").read()


def e(etiket, anahtar, nitelik=""):
    """Cevrilebilir bir oge: Ingilizce icerik + data-i18n anahtari."""
    return f'<{etiket} data-i18n="{anahtar}"{nitelik}>{T[anahtar][0]}</{etiket}>'


def s(anahtar):
    return e("span", anahtar)


CSS_EK = """
  /* ---------- language switch ---------- */
  .topbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
  .lang { display: inline-flex; border: 1px solid var(--rule); border-radius: 3px; overflow: hidden; }
  .lang button {
    font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.08em;
    padding: 5px 12px; background: transparent; color: var(--ink-faint);
    border: 0; cursor: pointer;
  }
  .lang button + button { border-left: 1px solid var(--rule); }
  .lang button[aria-pressed="true"] { background: var(--ink); color: var(--ground); }
  .lang button:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }

  /* ---------- version pairs: counts ---------- */
  .pair .vs small { font-family: var(--sans); font-size: 0.74rem; color: var(--ink-faint); font-weight: 400; margin-left: 4px; }
  .pair .vk { font-family: var(--mono); font-size: 0.72rem; color: var(--ink-faint); }
  .src { font-size: 0.8rem; color: var(--ink-faint); }
  .delta.flat { color: var(--ink-faint); }

  /* ---------- new rounds ---------- */
  table.narrow { min-width: 560px; }
  td.good { color: var(--kept); font-weight: 500; }
  td.name small.yil { display: block; font-family: var(--mono); font-size: 0.74rem; font-weight: 400; color: var(--ink-faint); margin-top: 2px; }
  td.bad { color: var(--broken); font-weight: 500; }
  blockquote.quote {
    margin: 0; max-width: var(--measure);
    border-left: 3px solid var(--kept); padding: 6px 0 6px 18px;
    font-family: var(--serif); font-size: var(--step-1); line-height: 1.5; color: var(--ink-soft);
  }
  blockquote.quote.bad { border-left-color: var(--broken); }
  ol.traps { margin: 0; padding-left: 1.4rem; max-width: var(--measure); display: flex; flex-direction: column; gap: 6px; }
  ol.traps li::marker { color: var(--ink-faint); font-family: var(--mono); font-size: 0.8rem; }

  /* ---------- one fixed light palette on every device ---------- */
  :root { color-scheme: light; }
  html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }

  /* ---------- larger type ---------- */
  :root { --step-0: 1.0625rem; --step-1: 1.22rem; --step-2: 1.55rem; --step-3: 2.1rem; --step-4: 3.2rem; }
  .eyebrow { font-size: 0.8rem; }
  .meta { font-size: 0.84rem; }
  caption { font-size: 0.9rem; }
  th { font-size: 0.74rem; }
  td.host { font-size: 0.8rem; }
  .mlabel, .legend { font-size: 0.8rem; }
  .tasks li { font-size: 0.9rem; }
  .bar .k { font-size: 0.86rem; }
  .pair .lab { font-size: 0.72rem; }
  .fingerprint { font-size: 0.84rem; }
  footer { font-size: 0.9rem; }

  /* ---------- phones ---------- */
  @media (max-width: 620px) {
    :root { --step-0: 1.0625rem; --step-1: 1.15rem; --step-2: 1.3rem; --step-3: 1.65rem; --step-4: 2.05rem; }
    .wrap { padding-inline: 16px; padding-block: 0 56px; }
    header { padding-block: 36px 24px; gap: 16px; }
    section { padding-block: 40px 0; gap: 16px; }
    .standfirst { font-size: 1.2rem; }
    .meta { gap: 6px 18px; }
    .finding { padding-left: 16px; }
    .finding .lede { font-size: 1.35rem; max-width: none; }
    .zero { font-size: 3rem; }
    table.narrow { min-width: 0; }
    table.narrow th, table.narrow td { white-space: normal; padding: 9px 7px; }
    table.narrow th { letter-spacing: 0.04em; }
    /* Telefonda erisim sutunu gizlenir; sayilar (ozellikle son sutun) ekranda kalir */
    td.host, th[data-i18n="th_access"] { display: none; }
    table.narrow td.name { font-size: 0.95rem; }
    table.narrow th { font-size: 0.64rem; letter-spacing: 0; padding: 8px 5px; }
    table.narrow td { padding: 9px 5px; }
    table { min-width: 0; }
    th, td { white-space: normal; }
    /* Kod tablosu: her satirda ayni olan deneme (99) ve kapsama (%100) sutunlari telefonda gizli */
    table:not(.narrow) tr > :nth-child(3), table:not(.narrow) tr > :nth-child(4) { display: none; }
    table:not(.narrow) th { font-size: 0.64rem; letter-spacing: 0; padding: 8px 5px; }
    table:not(.narrow) td { padding: 9px 5px; }
    th, td { padding: 9px 8px; }
    .cells { gap: 1px; }
    .cells i { min-width: 1px; height: 18px; }
    .limits { padding: 20px 16px; }
    blockquote.quote { font-size: 1.08rem; padding-left: 14px; }
    ul, ol.traps { padding-left: 1.1rem; }
  }
"""


def surum_blogu(v):
    m = {x["ad"]: x for x in v["modeller"]}
    parca = []
    for firma, e_ad, y_ad in SURUM_CIFTLERI:
        e_, y_ = m[e_ad], m[y_ad]
        fark = y_["bozuk"] - e_["bozuk"]
        sinif = "down" if fark > 0 else ("up" if fark < 0 else "flat")
        isaret = f"+{fark}" if fark > 0 else (f"&minus;{abs(fark)}" if fark < 0 else "&plusmn;0")
        e_t = f"{e_['dogru']}/{e_['dogru'] + e_['bozuk']}"
        y_t = f"{y_['dogru']}/{y_['dogru'] + y_['bozuk']}"
        parca.append(f"""      <div class="pair">
        <div class="v"><span class="lab"><span lang="en">{firma}</span> &middot; {s("v_prev")}</span><span class="vn">{e_['gorunen']}</span><span class="vs">{e_['bozuk']}<small>{s("v_broken")}</small></span><span class="vk">{e_t} {s("v_kept")}</span></div>
        <span class="arrow">&rarr;</span>
        <div class="v"><span class="lab">{s("v_new")}</span><span class="vn">{y_['gorunen']}</span><span class="vs">{y_['bozuk']}<small>{s("v_broken")}</small></span><span class="vk">{y_t} {s("v_kept")}</span></div>
        <span class="delta {sinif}">{isaret}</span>
      </div>""")
    return '<div class="pairs">\n' + "\n".join(parca) + "\n    </div>"


def cubuklar(v):
    satir = []
    for z, anahtar in (("kolay", "d_easy"), ("orta", "d_med"), ("zor", "d_hard")):
        y = v["zorluk_yuzde"][z]
        dusuk = " low" if y < 95 else ""
        satir.append(f'      <div class="bar">{e("span", anahtar, " class=\"k\"")}<span class="track"><span class="fill{dusuk}" style="width:{y}%"></span></span><span class="v">{y}%</span></div>')
    return '<div class="bars">\n' + "\n".join(satir) + "\n    </div>"


def gorev_listesi(v, n=6):
    satir = []
    for i, (slug, sayi) in enumerate(v["gorev_bozuk"][:n], 1):
        T[f"t{i}"] = GOREV_AD[slug]
        satir.append(f"      <li>{s('t' + str(i))}<b>{sayi}</b></li>")
    return '<ul class="tasks">\n' + "\n".join(satir) + "\n    </ul>"


def _baslik(anahtarlar):
    return "".join(e("th", k, ' scope="col"') for k in anahtarlar)


def yeni_turlar():
    """Is, tuzak ve eski/yeni bolumleri. Sayilar _turlar.py uzerinden veriden gelir."""
    import _turlar
    s = _turlar.durustluk()
    p = _turlar.proje()
    cozdu, top = _turlar.kontrol_ozeti(s)
    T["tuzak_p4"] = tuple(x.replace("{kontrol}", str(top)) for x in T["tuzak_p4"])
    return f"""  <section>
    {e("h2", "h_proje")}
    {e("p", "proje_p1")}
    <ul>
      {e("li", "pj_c")}
      {e("li", "pj_d")}
      {e("li", "pj_e")}
      {e("li", "pj_f")}
      {e("li", "pj_g")}
    </ul>
    {e("p", "proje_p2")}
    <div class="scroller">
      <table class="narrow">
        {e("caption", "pj_caption")}
        <thead><tr>{_baslik(["th_model", "th_access", "pj_th_kod", "pj_th_dur", "pj_th_yan"])}</tr></thead>
        {_turlar.tablo_proje(p)}
      </table>
    </div>
    {e("p", "proje_p3")}
    {e("blockquote", "q_astra", ' class="quote"')}
  </section>

  <section>
    {e("h2", "h_tuzak")}
    {e("p", "tuzak_p1")}
    <ol class="traps">
      {e("li", "tz1")}
      {e("li", "tz2")}
      {e("li", "tz3")}
      {e("li", "tz4")}
      {e("li", "tz5")}
      {e("li", "tz6")}
      {e("li", "tz7")}
      {e("li", "tz8")}
      {e("li", "tz9")}
    </ol>
    <div class="scroller">
      <table class="narrow">
        {e("caption", "tz_caption")}
        <thead><tr>{_baslik(["th_model", "th_access", "tz_th_n", "tz_th_d", "tz_th_k", "tz_th_y"])}</tr></thead>
        {_turlar.tablo_tuzak(s)}
      </table>
    </div>
    {e("p", "tuzak_p2")}
    {e("blockquote", "q_flashlite", ' class="quote bad"')}
    {e("p", "tuzak_p3")}
    {e("blockquote", "q_opus", ' class="quote"')}
    {e("p", "tuzak_p4")}
  </section>

  <section>
    {e("h2", "h_eskiyeni")}
    {e("p", "eski_p1")}
    <div class="scroller">
      <table class="narrow">
        {e("caption", "ey_caption")}
        <thead><tr>{_baslik(["th_model", "tz_th_d", "tz_th_k", "tz_th_y", "ey_th_pj"])}</tr></thead>
        {_turlar.tablo_eski_yeni(s, p)}
      </table>
    </div>
    {e("p", "eski_p2")}
  </section>
"""


def govde(v, tbody, matris):
    return f"""<div class="wrap">

  <header>
    <div class="topbar">
      {e("div", "eyebrow", ' class="eyebrow"')}
      <div class="lang" role="group" aria-label="Language">
        <button type="button" id="lang-en" data-lang="en" aria-pressed="true">EN</button>
        <button type="button" id="lang-tr" data-lang="tr" aria-pressed="false">TR</button>
      </div>
    </div>
    {e("h1", "h1")}
    {e("p", "standfirst", ' class="standfirst"')}
    <div class="meta">
      <span>{s("m_run")} <b data-i18n="m_date">{T["m_date"][0]}</b></span>
      <span>{s("m_models")} <b>13</b> &middot; {s("m_complete")}</span>
      <span>{s("m_tasks")} <b>3</b> &middot; {s("m_hidden")}</span>
      <span>{s("m_runs")} <b data-i18n="m_runs_n">{T["m_runs_n"][0]}</b> &middot; {s("m_per")}</span>
      <span>{s("m_cost")} <b data-i18n="m_cost_n">{T["m_cost_n"][0]}</b></span>
    </div>
  </header>

  <section>
    {e("h2", "h_why")}
    {e("p", "why_p")}
  </section>

  <section>
    <div class="finding">
      <div class="zero">0</div>
      {e("p", "lede", ' class="lede"')}
      {e("p", "finding_p")}
    </div>
  </section>

{yeni_turlar()}

  <section>
    {e("h2", "h_kod")}
    {e("p", "kod_p")}
    {e("h3", "h_results")}
    {e("p", "results_p")}
    <div class="scroller">
      <table>
        {e("caption", "caption")}
        <thead>
          <tr>
            {e("th", "th_model", ' scope="col"')}
            {e("th", "th_access", ' scope="col"')}
            {e("th", "th_runs", ' scope="col"')}
            {e("th", "th_cov", ' scope="col"')}
            {e("th", "th_keep", ' scope="col"')}
            {e("th", "th_broken", ' scope="col"')}
            {e("th", "th_abst", ' scope="col"')}
          </tr>
        </thead>
        {tbody}
      </table>
    </div>
    {e("p", "res_p2")}
    {e("p", "res_p3")}
  </section>

  <section>
    {e("h2", "h_every")}
    {e("p", "every_p1")}
    {e("p", "every_p2")}
    {matris}
    <div class="legend">
      <span><b style="background:var(--kept);opacity:.55"></b> {s("lg_kept")}</span>
      <span><b style="background:var(--broken)"></b> {s("lg_broken")}</span>
      <span><b style="background:var(--ink-faint)"></b> {s("lg_empty")}</span>
      <span><b style="background:var(--rule-soft);border:1px solid var(--rule)"></b> {s("lg_abst")}</span>
    </div>
  </section>

  <section>
    {e("h2", "h_diff")}
    {e("p", "diff_p")}
    {cubuklar(v)}
    {e("h3", "h_tasks")}
    {e("p", "tasks_p")}
    {gorev_listesi(v)}
    {e("p", "tasks_p2")}
  </section>

  <section>
    {e("h2", "h_audit")}
    {e("p", "audit_p1")}
    {e("p", "audit_p2")}
    {e("p", "audit_p3")}
    {e("p", "audit_p4")}
  </section>

  <section>
    {e("h2", "h_ver")}
    {e("p", "ver_p1")}
    {surum_blogu(v)}
    {e("p", "ver_p2")}
    {e("p", "ver_p3")}
    <p class="src"><a href="https://arcprize.org/blog/astra">{s("ver_src")}</a></p>
  </section>

  <section>
    {e("h2", "h_method")}
    <ul>
      {e("li", "mt1")}
      {e("li", "mt2")}
      {e("li", "mt3")}
      {e("li", "mt4")}
      {e("li", "mt5")}
      {e("li", "mt6")}
      {e("li", "mt7")}
    </ul>
    {e("p", "fp_label", ' class="eyebrow" style="margin-top:8px"')}
    <div class="fingerprint">rhizoma:ed25519:5df0fb0dfee966c2</div>
  </section>

  <section>
    <div class="limits">
      {e("h2", "h_limits")}
      {e("p", "lim_p")}
      <ul>
        {e("li", "lm1")}
        {e("li", "lm2")}
        {e("li", "lm3")}
        {e("li", "lm4")}
        {e("li", "lm5")}
        {e("li", "lm6")}
        {e("li", "lm7")}
      </ul>
    </div>
  </section>

  <section>
    {e("h2", "h_prior")}
    {e("p", "prior_p")}
    <ul>
      <li><a href="https://arxiv.org/abs/2605.17029">Task Abstention for Large Language Models in Code Generation</a>{s("pr1")}</li>
      <li><a href="https://huggingface.co/papers/2506.09038">AbstentionBench</a>{s("pr2")}</li>
      <li><a href="https://arxiv.org/abs/2609.17686">The Missing &ldquo;I Don&rsquo;t Know&rdquo;</a>{s("pr3")}</li>
    </ul>
  </section>

  <section>
    {e("h2", "h_check")}
    {e("p", "check_p1")}
    <p><a href="rhizoma-index-veri.zip">{s("check_dl")}</a></p>
    {e("p", "check_p2")}
    <p><a href="{DEPO}/issues">{s("check_issue")}</a> &middot; <a href="{DEPO}">{s("check_repo")}</a></p>
  </section>

  <section>
    {e("h2", "h_next")}
    {e("p", "next_p")}
    <ul>
      {e("li", "nx1")}
      {e("li", "nx2")}
      {e("li", "nx3")}
      {e("li", "nx5")}
      {e("li", "nx4")}
    </ul>
    <p><a href="{DEPO}/issues">{s("next_p2")}</a></p>
  </section>

  <footer>
    {e("div", "f1")}
    {e("div", "f2")}
  </footer>

</div>"""


BETIK = """
<script>
(function () {
  var TR = __TR__;
  var HOST_TR = __HOST__;
  var TITLE_TR = __TITLE__;

  var keyed = Array.prototype.slice.call(document.querySelectorAll("[data-i18n]"));
  var EN = {};
  keyed.forEach(function (el) { EN[el.getAttribute("data-i18n")] = el.innerHTML; });

  var hosts = Array.prototype.slice.call(document.querySelectorAll("td.host"));
  hosts.forEach(function (el) { el.setAttribute("data-en", el.textContent); });

  var labels = Array.prototype.slice.call(document.querySelectorAll(".mlabel span:last-child"));
  labels.forEach(function (el) { el.setAttribute("data-en", el.textContent); });

  var cells = Array.prototype.slice.call(document.querySelectorAll(".cells i[title]"));
  cells.forEach(function (el) { el.setAttribute("data-en", el.getAttribute("title")); });

  function apply(lang) {
    var tr = lang === "tr";
    document.documentElement.lang = tr ? "tr" : "en";
    keyed.forEach(function (el) {
      var k = el.getAttribute("data-i18n");
      el.innerHTML = tr && TR[k] ? TR[k] : EN[k];
    });
    hosts.forEach(function (el) {
      var en = el.getAttribute("data-en");
      el.textContent = tr && HOST_TR[en] ? HOST_TR[en] : en;
    });
    labels.forEach(function (el) {
      var en = el.getAttribute("data-en");
      el.textContent = tr ? en.replace(/(\\d+) broken of (\\d+)/, "$2 denemede $1 hatalı") : en;
    });
    cells.forEach(function (el) {
      var en = el.getAttribute("data-en");
      el.setAttribute("title", tr && TITLE_TR[en] ? TITLE_TR[en] : en);
    });
    ["en", "tr"].forEach(function (l) {
      var b = document.getElementById("lang-" + l);
      if (b) b.setAttribute("aria-pressed", String(l === lang));
    });
    try { localStorage.setItem("rhizoma-lang", lang); } catch (e) {}
  }

  document.querySelectorAll(".lang button").forEach(function (b) {
    b.addEventListener("click", function () { apply(b.getAttribute("data-lang")); });
  });

  var start = "en";
  try {
    var saved = localStorage.getItem("rhizoma-lang");
    if (saved === "en" || saved === "tr") start = saved;
    else if ((navigator.language || "").toLowerCase().indexOf("tr") === 0) start = "tr";
  } catch (e) {
    if ((navigator.language || "").toLowerCase().indexOf("tr") === 0) start = "tr";
  }
  if (start !== "en") apply(start);
})();
</script>
"""


def main():
    css = oku("_parca_css.txt").replace("</style>", CSS_EK + "</style>")
    v = _veri.hesapla()
    tbody = _veri.tbody(v)
    matris = _veri.matris(v)
    govde_html = govde(v, tbody, matris)   # T'ye gorev adlarini da ekler

    # Yalnizca sayfada gercekten kullanilan metinler: eski/kullanilmayan girdiler
    # sayfanin kaynagina sizmasin (sayfa herkese acik).
    kullanilan = set(re.findall(r'data-i18n="([^"]+)"', govde_html))
    tr = {k: d[1] for k, d in T.items() if k in kullanilan}
    tr_json = json.dumps(tr, ensure_ascii=False).replace("</", "<\\/")

    # Paylasim onizlemesi (link yapistirildiginda gorunen baslik ve aciklama)
    import html as _html
    ozet = _html.escape(re.sub(r"<[^>]+>", "", _html.unescape(T["standfirst"][0])), quote=True)
    baslik = _html.escape(_html.unescape(T["h1"][0]), quote=True)

    sayfa = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        # Telefonda ekran genisligine uy (bu satir olmadan sayfa masaustu gibi kucultulur)
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        # Her cihazda ayni acik renk paleti: karanlik mod bu sayfanin renklerini degistirmez
        '<meta name="color-scheme" content="light">\n'
        "<title>Rhizoma Index</title>\n"
        # Sekme simgesi: dosya gerektirmeyen kucuk bir SVG (sitenin vurgu rengi, R harfi)
        '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect width=%2732%27 height=%2732%27 rx=%277%27 fill=%27%233F6349%27/%3E%3Ctext x=%2716%27 y=%2723%27 text-anchor=%27middle%27 font-family=%27Georgia,serif%27 font-size=%2720%27 fill=%27%23EDF1EC%27%3ER%3C/text%3E%3C/svg%3E">\n'
        f'<meta name="description" content="{ozet}">\n'
        f'<meta property="og:title" content="{baslik}">\n'
        f'<meta property="og:description" content="{ozet}">\n'
        '<meta property="og:type" content="article">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">\n\n'
        + css + "\n"
        "</head>\n"
        "<body>\n"
        + govde_html + "\n"
        + BETIK.replace("__TR__", tr_json)
               .replace("__HOST__", json.dumps(HOST, ensure_ascii=False))
               .replace("__TITLE__", json.dumps(HUCRE_TR, ensure_ascii=False))
        + "</body>\n</html>\n"
    )
    io.open(os.path.join(BURASI, "index.html"), "w", encoding="utf-8").write(sayfa)

    print(f"index.html uretildi: {len(sayfa)//1024} KB, "
          f"{sayfa.count('data-i18n=')} cevrilebilir oge, {len(T)} metin anahtari, "
          f"{sayfa.count('<i ')} harita hucresi")


if __name__ == "__main__":
    main()
