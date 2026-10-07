/* ekip.js — Ekip alani: ajanlar, projeler, ekip gorevi (canli), pano, gecmis.
   Ana arayuzun (index.html) yardimcilarini kullanir: el, t, ikon, toast,
   bosalt, kisalt, onayKarti. DOM dogrudan kurulur, innerHTML yok (ARAYUZ.md 9).

   Veri kaynaklari (pencere.Api): ekip_projeler / ekip_proje_yaz / ekip_proje_sil,
   ajanlar / ajan_yaz / ajan_sil, anahtar_yuvalari / anahtar_yaz(yuva),
   ekip_gorev_baslat, ekip_pano_yaz, ekip_kosular / ekip_kosu, klasor_sec.
   Canli durum: ana olay akisindan (olayIsle -> Ekip.olay). */
"use strict";
window.Ekip = (() => {
  const T = (s, p) => (typeof t === "function" ? t(s, p) : s);
  const D = {
    acik: false, sekme: "gorev",
    projeler: [], ajanlar: [], yuvalar: {}, secili: new Set(), proje: "",
    kosu: null,            // aktif kosu: {kimlik, durum, uyeler:{ad:{ajan,durum,son,ozet}}, pano:[], sonuc:""}
    kosular: [], detay: null,
  };
  const SAGLAYICI_ADI = {gemini: "Gemini", openai: "OpenAI-uyumlu", anthropic: "Anthropic"};
  const RENKLER = ["#dcaa65", "#79b9a0", "#91a9e8", "#c4a0d9", "#e08f8f", "#8fd0e0"];

  function kap() { return document.getElementById("ekip-gorunum"); }
  function api() { return window.pywebview && window.pywebview.api; }
  /* Ikonlu yapi taslari: etiket, dugme, meta satiri, silme dugmesi. */
  function ikonlu(dugum, im, metin, boyut) { dugum.appendChild(ikon(im, boyut || 15)); dugum.appendChild(el("span", "", metin)); return dugum; }
  function dugme(sinif, metin, im) { return ikonlu(el("button", sinif + " ek-dugme"), im, T(metin)); }
  function etiket(metin, im) { return ikonlu(el("label"), im, T(metin), 14); }
  function meta(im, metin) { return ikonlu(el("div", "ek-meta"), im, metin, 13); }
  function silDugmesi(baslik, tikla) { const b = el("button", "ek-sil"); b.title = T(baslik); b.appendChild(ikon("ret", 14)); b.addEventListener("click", tikla); return b; }
  const DURUM_IKONU = {planlaniyor: "yukleniyor", onay_bekliyor: "bayrak", calisiyor: "etkinlik", birlestiriliyor: "birlestir",
                       bitti: "tamam", hata: "uyari", reddedildi: "ret", plan_hatasi: "uyari"};
  function durumIkonu(durum, boyut) { const s = ikon(DURUM_IKONU[durum] || "saat", boyut || 16);
    if (durum === "planlaniyor" || durum === "birlestiriliyor") s.classList.add("donen"); return s; }
  function renk(ad) { let h = 0; for (const c of String(ad)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return RENKLER[h % RENKLER.length]; }

  async function yukle() {
    const a = api(); if (!a) return;
    const [p, aj, y, k] = await Promise.all([a.ekip_projeler(), a.ajanlar(), a.anahtar_yuvalari(), a.ekip_kosular()]);
    D.projeler = (p && p.projeler) || [];
    D.ajanlar = (aj && aj.ajanlar) || [];
    D.yuvalar = (y && y.yuvalar) || {};
    D.kosular = (k && k.kosular) || [];
    if (!D.proje && D.projeler.length) D.proje = D.projeler[0].kimlik;
    if (!D.secili.size) D.ajanlar.forEach((x) => D.secili.add(x.ad));
  }

  /* 3B ofis (ofis/ofis.js) varsa Ekip alani onu gosterir; bu dosyanin
     sekmeleri ofisin cekmecesinde cizilir. WebGL yoksa bugunku kart gorunumu. */
  function ofis() { return window.Ofis || null; }
  function ac() {
    D.acik = true;
    const o = ofis();
    Promise.all([yukle(), o ? o.hazirla() : null]).then(() => { if (D.acik) ciz(); if (o && D.acik) o.ac(); });
  }
  function kapat() { D.acik = false; if (ofis()) ofis().kapat(); }

  /* ---------------- iskelet ---------------- */
  function ciz() {
    const k = kap(); if (!k) return;
    const o = ofis();
    if (o && o.etkin()) { o.ciz(); if (o.etkin()) return; }
    k.classList.remove("ofis");
    bosalt(k);
    if (o && o.D.kip === "kart") {
      /* WebGL yok: ofis yerine kart gorunumu; bos ekran hicbir durumda yok. */
      k.appendChild(ikonlu(el("div", "ek-bilgi"), "bilgi", T("3B ofis bu cihazda açılamadı (WebGL yok); kart görünümü gösteriliyor."), 14));
    }
    const dis = el("div", "ek-dis");
    const yan = el("nav", "ek-yan");
    [["gorev", "hedef", "Görev"], ["ajanlar", "bot", "Ajanlar"], ["projeler", "klasor", "Projeler"], ["gecmis", "degisiklik", "Geçmiş"]]
      .forEach(([kod, im, ad]) => {
        const b = el("button", "ek-sekme" + (D.sekme === kod ? " aktif" : ""));
        b.appendChild(ikon(im, 16)); b.appendChild(el("span", "", T(ad)));
        b.addEventListener("click", () => { D.sekme = kod; ciz(); });
        yan.appendChild(b);
      });
    dis.appendChild(yan);
    const ic = el("div", "ek-ic");
    ic.appendChild(el("p","ek-sonuk",T("Ekip, bir görevi farklı ajanlara paylaştırır. Örneğin biri araştırır, diğeri raporu hazırlar; sonuçları birlikte izlersin.")));
    sekmeCiz(ic, D.sekme);
    dis.appendChild(ic);
    k.appendChild(dis);
  }
  function sekmeCiz(ic, kod) {
    ({gorev: gorevSekmesi, ajanlar: ajanlarSekmesi, projeler: projelerSekmesi, gecmis: gecmisSekmesi}[kod] || gorevSekmesi)(ic);
  }

  function baslik(ic, ad, aciklama, im) {
    ic.appendChild(ikonlu(el("h2"), im || "ekip", T(ad), 20));
    if (aciklama) ic.appendChild(ikonlu(el("div", "ek-alt"), "bilgi", T(aciklama), 14));
  }

  /* ---------------- Gorev ---------------- */
  function gorevSekmesi(ic) {
    baslik(ic, "Ekip görevi",
      "Proje ve ekibi seç, görevi yaz. Planlayıcı işi böler; onayından sonra üyeler paralel çalışır ve sonuçlar "
      + "birleştirilir.", "hedef");
    if (!D.ajanlar.length) {
      const u = el("div", "ek-uyari");
      u.appendChild(ikon("uyari", 18)); u.appendChild(el("span", "", T("Önce en az bir ajan tanımla.")));
      const b = dugme("birincil", "Ajanlar", "bot"); b.addEventListener("click", () => { D.sekme = "ajanlar"; ciz(); });
      u.appendChild(b); ic.appendChild(u);
    }
    const form = el("div", "ek-form");
    /* proje */
    const ps = el("div", "ek-satir");
    ps.appendChild(etiket("Proje", "klasor"));
    const sec = el("select");
    if (!D.projeler.length) { const o = el("option", "", T("(proje yok — varsayılan klasör)")); o.value = ""; sec.appendChild(o); }
    D.projeler.forEach((p) => { const o = el("option", "", p.ad + " — " + p.klasor); o.value = p.kimlik; if (p.kimlik === D.proje) o.selected = true; sec.appendChild(o); });
    sec.addEventListener("change", () => { D.proje = sec.value; });
    ps.appendChild(sec);
    const yeniP = dugme("ikincil", "Yeni proje…", "yeni"); yeniP.addEventListener("click", () => { D.sekme = "projeler"; ciz(); });
    ps.appendChild(yeniP);
    form.appendChild(ps);
    /* ajanlar */
    const as = el("div", "ek-satir");
    as.appendChild(etiket("Ekip", "ekip"));
    const cips = el("div", "ek-cipler");
    D.ajanlar.forEach((a) => {
      const c = el("button", "ek-cip" + (D.secili.has(a.ad) ? " secili" : ""));
      const nokta = el("span", "ek-nokta"); nokta.style.background = renk(a.ad); c.appendChild(nokta);
      c.appendChild(ikon(D.secili.has(a.ad) ? "onay" : "bot", 14));
      c.appendChild(el("span", "", a.ad + " · " + (a.etkin_model || a.saglayici)));
      if (!a.anahtar_var) c.appendChild(ikonlu(el("span", "ek-eksik"), "anahtar", T("anahtar yok"), 12));
      c.addEventListener("click", () => { D.secili.has(a.ad) ? D.secili.delete(a.ad) : D.secili.add(a.ad); ciz(); });
      cips.appendChild(c);
    });
    as.appendChild(cips); form.appendChild(as);
    /* gorev */
    const gs = el("div", "ek-satir dikey");
    gs.appendChild(etiket("Görev", "kalem"));
    const alan = el("textarea", "ek-gorev"); alan.placeholder = T("Görevi tanımla. Planlayıcı iş bölümünü önerir, sen"
                                                                  + " onaylarsın.");
    alan.rows = 4; gs.appendChild(alan); form.appendChild(gs);
    const dugmeler = el("div", "ek-dugmeler");
    const baslat = dugme("birincil", "Ekibi başlat", "oynat");
    baslat.disabled = !D.ajanlar.length || kosuSurer();
    baslat.addEventListener("click", () => gorevBaslat(alan.value).then((ok) => { if (ok) { alan.value = ""; canliCiz(); } }));
    dugmeler.appendChild(baslat);
    const dur = dugme("ikincil", "Durdur", "dur");
    dur.addEventListener("click", () => api().durdur());
    dugmeler.appendChild(dur);
    form.appendChild(dugmeler);
    ic.appendChild(form);
    /* canli alan */
    const canli = el("div", "ek-canli"); canli.id = "ekip-canli"; ic.appendChild(canli);
    canliCiz();
  }

  const DURUM_METNI = {planlaniyor: "Planlanıyor…", onay_bekliyor: "Bölüşüm onayını bekliyor", calisiyor: "Üyeler çalışıyor",
                       birlestiriliyor: "Birleştiriliyor…", bitti: "Bitti", hata: "Hata", reddedildi: "Plan reddedildi", plan_hatasi: "Plan kurulamadı"};

  function canliCiz() {
    const c = document.getElementById("ekip-canli"); if (!c || !D.kosu) { if (c) bosalt(c); return; }
    /* Onay karti disaridan (index.onayKarti) buraya eklenir; korunmali. */
    const onay = c.querySelector(".onay");
    bosalt(c);
    const ust = el("div", "ek-durum " + D.kosu.durum);
    const nokta = el("span", "ek-nokta " + D.kosu.durum); ust.appendChild(nokta);
    const di = el("span", "ek-durum-ikon"); di.appendChild(durumIkonu(D.kosu.durum, 17)); ust.appendChild(di);
    ust.appendChild(el("span", "", T(DURUM_METNI[D.kosu.durum] || D.kosu.durum)));
    c.appendChild(ust);
    if (onay) c.appendChild(onay);
    const uyeler = Object.keys(D.kosu.uyeler);
    if (uyeler.length) {
      const grid = el("div", "ek-uyeler");
      uyeler.forEach((ad) => {
        const u = D.kosu.uyeler[ad];
        const kart = el("div", "ek-uye" + (u.durum === "bitti" ? " bitti" : ""));
        const bas = el("div", "ek-uye-bas");
        const n = el("span", "ek-nokta"); n.style.background = renk(ad); bas.appendChild(n);
        bas.appendChild(ikon("bot", 15));
        bas.appendChild(el("strong", "", ad)); bas.appendChild(el("span", "ek-sonuk", u.ajan || ""));
        const ud = el("span", "ek-uye-durum"); ud.title = T(u.durum === "bitti" ? "Bitti" : "Çalışıyor");
        ud.appendChild(u.durum === "bitti" ? ikon("tamam", 15) : (() => { const s = ikon("yukleniyor", 15); s.classList.add("donen"); return s; })());
        bas.appendChild(ud); kart.appendChild(bas);
        kart.appendChild(ikonlu(el("div", "ek-uye-son"), u.son ? "gorev" : "saat", u.son ? u.son : T("bekliyor…"), 13));
        if (u.ozet) kart.appendChild(ikonlu(el("div", "ek-uye-ozet ek-meta"), "dosya", kisalt(u.ozet, 400), 13));
        grid.appendChild(kart);
      });
      c.appendChild(grid);
    }
    /* pano */
    const pano = el("div", "ek-pano");
    pano.appendChild(ikonlu(el("h4"), "pano", T("Pano"), 14));
    const liste = el("div", "ek-pano-liste");
    if (!D.kosu.pano.length) liste.appendChild(el("div", "ek-sonuk", T("Henüz mesaj yok.")));
    D.kosu.pano.forEach((m) => {
      const s = el("div", "ek-mesaj");
      const kim = el("span", "ek-kim"); kim.style.color = renk(m.kimden);
      kim.appendChild(el("span", "", m.kimden)); kim.appendChild(ikon("sagok", 12)); kim.appendChild(el("span", "", m.kime || "herkes"));
      s.appendChild(kim); s.appendChild(el("span", "secilebilir", m.metin)); liste.appendChild(s);
    });
    pano.appendChild(liste);
    if (!["bitti", "hata", "reddedildi", "plan_hatasi"].includes(D.kosu.durum)) {
      const gir = el("div", "ek-pano-gir");
      const g = el("input"); g.placeholder = T("Ekibe not yaz (hepsi görür)…");
      const gonder = dugme("ikincil", "Gönder", "yolla");
      const yolla = () => { const m = g.value.trim(); if (!m) return; api().ekip_pano_yaz(m, "herkes").then((r) => {
        if (r && !r.ok) { toast(r.hata, "kotu"); return; } g.value = ""; }); };
      gonder.addEventListener("click", yolla); g.addEventListener("keydown", (e) => { if (e.key === "Enter") yolla(); });
      gir.appendChild(g); gir.appendChild(gonder); pano.appendChild(gir);
    }
    c.appendChild(pano);
    if (D.kosu.sonuc) {
      const s = el("div", "ek-sonuc"); s.appendChild(ikonlu(el("h4"), "birlestir", T("Birleştirici"), 14));
      const md = el("div", "secilebilir"); md.appendChild(typeof markdown === "function" ? markdown(D.kosu.sonuc) : document.createTextNode(D.kosu.sonuc)); s.appendChild(md);
      c.appendChild(s);
    }
  }

  /* Ana olay akisindan (index.olayIsle). Ekip kosusu yoksa da izlenir: /ekip ile
     sohbetten baslatilan kosu da burada gorunsun. */
  function olay(o) {
    try { olayIsleIc(o); } finally { if (ofis()) ofis().olay(o); }
  }
  function olayIsleIc(o) {
    const v = o.veri || {};
    /* {rol: planlayici|birlestirici, durum}: ofis icin; kosunun durumu degil. */
    if (o.tip === "ekip_mesaj" && v.rol) return;
    if (o.tip === "ekip_mesaj" && v.durum) {
      if (!D.kosu || v.durum === "planlaniyor") D.kosu = {kimlik: v.kimlik || null, durum: v.durum, uyeler: {}, pano: [], sonuc: "", plan: null};
      D.kosu.durum = v.durum; if (v.kimlik) D.kosu.kimlik = v.kimlik;
      (v.uyeler || []).forEach((ad) => { D.kosu.uyeler[ad] = D.kosu.uyeler[ad] || {ajan: "", durum: "calisiyor", son: "", ozet: ""}; });
      canliCiz(); return;
    }
    if (!D.kosu) return;
    if (o.tip === "ekip_mesaj" && v.kimden) { D.kosu.pano.push({kimden: v.kimden, kime: v.kime, metin: v.metin}); canliCiz(); return; }
    if (o.tip === "onay_gerekli" && v.istek && v.istek.arac === "ekip_plan") { D.kosu.durum = "onay_bekliyor"; canliCiz(); return; }
    if (o.tip === "arac_cagrildi" && v.ajan) {
      const u = D.kosu.uyeler[v.ajan] = D.kosu.uyeler[v.ajan] || {ajan: "", durum: "calisiyor", son: "", ozet: ""};
      if (v.arac === "ekip_isci") u.ajan = (v.args && v.args.ajan) || "";
      else u.son = (typeof aracBasligi === "function" ? aracBasligi(v.arac) : v.arac) + (v.args && v.args.path ? " — " + String(v.args.path).split(/[\\/]/).pop() : "");
      canliCiz(); return;
    }
    if (o.tip === "arac_sonucu" && v.ajan && v.arac === "ekip_isci") {
      const u = D.kosu.uyeler[v.ajan] = D.kosu.uyeler[v.ajan] || {ajan: "", durum: "calisiyor", son: "", ozet: ""};
      u.durum = "bitti"; u.ozet = v.sonuc || ""; u.son = T("bitti"); canliCiz(); return;
    }
    if (o.tip === "gorev_bitti") {
      if (!["bitti", "reddedildi", "plan_hatasi"].includes(D.kosu.durum)) D.kosu.durum = v.durduruldu ? "hata" : "bitti";
      D.kosu.sonuc = v.metin || D.kosu.sonuc; canliCiz();
      api() && api().ekip_kosular().then((k) => { D.kosular = (k && k.kosular) || []; });
    }
  }
  /* index.onayKarti: ekip plani, alan acikken buraya */
  function hedef(kart) {
    if (!D.acik) return null;
    const c = ofis() && ofis().etkin() ? ofis().onayHedefi() : document.getElementById("ekip-canli");
    if (!c) return null;
    c.appendChild(kart); return kart;
  }

  /* ---------------- Ajanlar ---------------- */
  function ajanlarSekmesi(ic) {
    baslik(ic, "Ajanlar", "Ekip üyeleri. Her ajanın kendi sağlayıcısı, modeli ve isteğe bağlı anahtar yuvası vardır.", "bot");
    const liste = el("div", "ek-kartlar");
    if (!D.ajanlar.length) liste.appendChild(el("div", "ek-sonuk", T("Tanımlı ajan yok. Ekip görevi için en az iki ajan tanımla.")));
    D.ajanlar.forEach((a) => {
      const k = el("div", "ek-kart");
      const bas = el("div", "ek-uye-bas");
      const n = el("span", "ek-nokta"); n.style.background = renk(a.ad); bas.appendChild(n);
      bas.appendChild(ikon("bot", 16)); bas.appendChild(el("strong", "", a.ad));
      const duzenle = dugme("ikincil", "Düzenle", "kalem");
      duzenle.addEventListener("click", () => {
        const onceki = k.querySelector(".of-form");
        if (onceki) { onceki.remove(); return; }
        if (window.Ofis && Ofis.ajanFormu) Ofis.ajanFormu(k, a, () => yukle().then(ciz));
      });
      bas.appendChild(duzenle);
      bas.appendChild(silDugmesi("Ajanı sil", () => api().ajan_sil(a.ad).then((r) => { if (r && !r.ok) { toast(r.hata, "kotu"); return; } D.secili.delete(a.ad); yukle().then(ciz); })));
      k.appendChild(bas);
      k.appendChild(meta("islemci", (SAGLAYICI_ADI[a.saglayici] || a.saglayici) + " · " + (a.etkin_model || "?")));
      k.appendChild(meta("anahtar", a.anahtar_yuvasi ? "#" + a.anahtar_yuvasi : T("varsayılan anahtar")));
      if (a.taban_url) k.appendChild(meta("sunucu", a.taban_url));
      if (a.rol) k.appendChild(ikonlu(el("div", "ek-meta"), "kullanici", a.rol, 13));
      if (!a.anahtar_var) k.appendChild(ikonlu(el("div", "ek-eksik"), "uyari", T("Bu sağlayıcı/yuva için anahtar yok — aşağıdan ekle."), 13));
      liste.appendChild(k);
    });
    ic.appendChild(liste);
    /* ekleme */
    ic.appendChild(ikonlu(el("h4"), "yeni", T("YENİ AJAN"), 13));
    const form = el("div", "ek-form");
    const ad = girdi(form, "Ad", "yazar", "bot"), rol = girdi(form, "Rol (isteğe bağlı)", "Metinleri yazar", "kullanici");
    const sag = secim(form, "Sağlayıcı", [["gemini", "Gemini"], ["openai", "OpenAI-uyumlu"], ["anthropic", "Anthropic"]], "web");
    const model = girdi(form, "Model (boş = Hızlı mod modeli)", "gemini-2.5-flash", "islemci");
    const taban = girdi(form, "Sunucu adresi (yalnızca OpenAI-uyumlu, boş = api.openai.com)", "http://localhost:11434/v1", "sunucu");
    const yuva = secim(form, "Anahtar", [["", T("varsayılan anahtar")]], "anahtar");
    function yuvalariDoldur() { bosalt(yuva); const o0 = el("option", "", T("varsayılan anahtar")); o0.value = ""; yuva.appendChild(o0);
      (D.yuvalar[sag.value] || []).forEach((y) => { const o = el("option", "", "#" + y.yuva); o.value = y.yuva; yuva.appendChild(o); }); }
    sag.addEventListener("change", yuvalariDoldur); yuvalariDoldur();
    const ekle = dugme("birincil", "Ajan ekle", "bot");
    ekle.addEventListener("click", () => {
      if (!ad.value.trim()) { toast(T("Ajan adı gerekli"), "kotu"); return; }
      api().ajan_yaz(ad.value.trim(), sag.value, model.value.trim(), yuva.value, rol.value.trim(), taban.value.trim()).then((r) => {
        if (r && !r.ok) { toast(r.hata, "kotu"); return; }
        toast(T("Ajan kaydedildi"), "iyi"); D.secili.add(ad.value.trim()); yukle().then(ciz);
      });
    });
    form.appendChild(ekle); ic.appendChild(form);
    /* anahtar yuvalari */
    ic.appendChild(ikonlu(el("h4"), "anahtar", T("EK ANAHTARLAR (YUVALAR)"), 13));
    ic.appendChild(ikonlu(el("div", "ek-alt"), "kalkan", T("Aynı sağlayıcıda ek hesap veya kota için. Anahtar sistem "
                                                           + "anahtar deposunda saklanır."), 14));
    const yl = el("div", "ek-kartlar");
    Object.keys(D.yuvalar).forEach((s) => (D.yuvalar[s] || []).forEach((y) => {
      const k = el("div", "ek-kart satir");
      k.appendChild(ikonlu(el("span", "ek-dugme"), "anahtar", (SAGLAYICI_ADI[s] || s) + " #" + y.yuva + "  " + (y.kaynak === "yok" ? T("(boş)") : y.maske), 14));
      k.appendChild(silDugmesi("Yuvayı sil", () => api().anahtar_yaz(s, "", y.yuva).then((r) => { if (r && !r.ok) { toast(r.hata, "kotu"); return; } yukle().then(ciz); })));
      yl.appendChild(k);
    }));
    ic.appendChild(yl);
    const yf = el("div", "ek-form satir");
    const ysag = secim(yf, "Sağlayıcı", [["gemini", "Gemini"], ["openai", "OpenAI-uyumlu"], ["anthropic", "Anthropic"]], "web");
    const yad = girdi(yf, "Yuva adı", "ikinci", "anahtar"); const yk = girdi(yf, "API anahtarı", "", "kalkan"); yk.type = "password"; yk.autocomplete = "off";
    const yekle = dugme("ikincil", "Anahtar ekle", "anahtar");
    yekle.addEventListener("click", () => {
      if (!yad.value.trim() || !yk.value.trim()) { toast(T("Yuva adı ve anahtar gerekli"), "kotu"); return; }
      api().anahtar_yaz(ysag.value, yk.value.trim(), yad.value.trim()).then((r) => { if (r && !r.ok) { toast(r.hata, "kotu"); return; }
        toast(T("Anahtar kaydedildi"), "iyi"); yukle().then(ciz); });
    });
    yf.appendChild(yekle); ic.appendChild(yf);
  }

  /* Gorev baslatma TEK yol: kart gorunumu de ofisin gorev cubugu da bunu
     cagirir (mevcut ekip_gorev_baslat; plan onayi ve dar isci politikasi aynen). */
  function kosuSurer() { return !!D.kosu && !["bitti", "hata", "reddedildi", "plan_hatasi"].includes(D.kosu.durum); }
  function gorevBaslat(metin) {
    const g = String(metin || "").trim();
    if (!g) { toast(T("Görev boş"), "kotu"); return Promise.resolve(false); }
    if (!D.secili.size) { toast(T("En az bir ajan seç"), "kotu"); return Promise.resolve(false); }
    return api().ekip_gorev_baslat(g, D.proje || null, Array.from(D.secili), null).then((c) => {
      if (c && !c.ok) { toast(c.hata, "kotu"); return false; }
      D.kosu = {kimlik: null, durum: "planlaniyor", uyeler: {}, pano: [], sonuc: "", plan: null};
      return true;
    });
  }

  function girdi(form, ad, ornek, im) {
    const s = el("div", "ek-satir"); s.appendChild(im ? etiket(ad, im) : el("label", "", T(ad)));
    const g = el("input"); g.placeholder = ornek || ""; g.spellcheck = false; s.appendChild(g); form.appendChild(s); return g;
  }
  function secim(form, ad, secenekler, im) {
    const s = el("div", "ek-satir"); s.appendChild(im ? etiket(ad, im) : el("label", "", T(ad)));
    const g = el("select"); secenekler.forEach(([v, e]) => { const o = el("option", "", e); o.value = v; g.appendChild(o); });
    s.appendChild(g); form.appendChild(s); return g;
  }

  /* ---------------- Projeler ---------------- */
  function projelerSekmesi(ic) {
    baslik(ic, "Projeler", "Proje bir klasördür; ekip yalnızca bu klasörde çalışır. Klasör yazılabilir bir klasörün "
                           + "içinde olmalıdır (Ayarlar > Dosyalar).", "klasor");
    const liste = el("div", "ek-kartlar");
    if (!D.projeler.length) liste.appendChild(el("div", "ek-sonuk", T("Proje yok. Aşağıdan bir klasör seçerek ekle.")));
    D.projeler.forEach((p) => {
      const k = el("div", "ek-kart");
      const bas = el("div", "ek-uye-bas"); bas.appendChild(ikon("klasorac", 16)); bas.appendChild(el("strong", "", p.ad));
      bas.appendChild(silDugmesi("Projeyi sil (klasör silinmez)", () => api().ekip_proje_sil(p.kimlik).then((r) => { if (r && !r.ok) { toast(r.hata, "kotu"); return; } if (D.proje === p.kimlik) D.proje = ""; yukle().then(ciz); })));
      k.appendChild(bas);
      k.appendChild(meta("klasor", p.klasor));
      if(p.workspace_id){const open=dugme("ikincil","Workspace'te aç","klasor");open.addEventListener("click",()=>window.LocalPlugins?.navigate("workspace","tasks",p.workspace_id));k.appendChild(open);}
      if (p.aciklama) k.appendChild(ikonlu(el("div", "ek-meta"), "bilgi", p.aciklama, 13));
      const n = D.kosular.filter((x) => x.proje === p.kimlik).length;
      k.appendChild(meta("degisiklik", T("{n} ekip koşusu", {n})));
      liste.appendChild(k);
    });
    ic.appendChild(liste);
    ic.appendChild(ikonlu(el("h4"), "yeni", T("YENİ PROJE"), 13));
    const form = el("div", "ek-form");
    const ad = girdi(form, "Ad", "Web sitesi yenileme", "kalem");
    const ks = el("div", "ek-satir"); ks.appendChild(etiket("Klasör", "klasor"));
    const klasor = el("input"); klasor.readOnly = true; klasor.placeholder = T("Seçilmedi"); ks.appendChild(klasor);
    const secB = dugme("ikincil", "Klasör seç…", "klasorac");
    secB.addEventListener("click", () => api().klasor_sec().then((c) => { if (c && c.ok && c.yol) klasor.value = c.yol; }));
    ks.appendChild(secB); form.appendChild(ks);
    const acik = girdi(form, "Açıklama (isteğe bağlı)", "", "bilgi");
    const ekle = dugme("birincil", "Proje ekle", "yeni");
    ekle.addEventListener("click", () => {
      api().ekip_proje_yaz(ad.value.trim(), klasor.value.trim(), acik.value.trim(), null).then((r) => {
        if (r && !r.ok) { toast(r.hata, "kotu"); return; }
        toast(T("Proje eklendi"), "iyi"); D.proje = r.proje.kimlik; yukle().then(ciz);
      });
    });
    form.appendChild(ekle); ic.appendChild(form);
  }

  /* ---------------- Gecmis ---------------- */
  function gecmisSekmesi(ic) {
    baslik(ic, "Geçmiş", "Önceki ekip koşuları: plan, üye raporları, pano ve birleştirici çıktısı.", "degisiklik");
    if (D.detay) {
      const geri = dugme("ikincil", "Listeye dön", "solok"); geri.addEventListener("click", () => { D.detay = null; ciz(); });
      ic.appendChild(geri);
      /* 3B ofiste: kayitli olaylarla oynat (canli degil; kopruye yazmaz) */
      if (ofis() && ofis().etkin()) {
        const oyna = dugme("ikincil", "Ofiste oynat", "oynat"); oyna.addEventListener("click", () => ofis().oynat(D.detay.kimlik));
        ic.appendChild(oyna);
      }
      const k = D.detay;
      const kb = el("h4", "ek-durum " + k.durum); const kdi = el("span", "ek-durum-ikon"); kdi.appendChild(durumIkonu(k.durum, 14)); kb.appendChild(kdi);
      kb.appendChild(el("span", "", (k.baslangic || "").replace("T", " ") + " · " + T(DURUM_METNI[k.durum] || k.durum))); ic.appendChild(kb);
      ic.appendChild(ikonlu(el("div", "ek-dugme"), "hedef", k.gorev || "", 14));
      ic.appendChild(meta("klasor", k.alan || ""));
      if ((k.plan || []).length) ic.appendChild(ikonlu(el("h4"), "plan", T("Plan"), 13));
      (k.plan || []).forEach((ag) => { const c = el("div", "ek-kart ek-mesaj"); const kim = el("span", "ek-kim"); kim.style.color = renk(ag.ad);
        kim.appendChild(ikon("bot", 13)); kim.appendChild(el("span", "", ag.ad + " [" + ag.ajan + "]")); kim.appendChild(ikon("sagok", 12));
        kim.appendChild(el("span", "", (ag.yollar || []).join(", "))); c.appendChild(kim); c.appendChild(el("span", "", ag.gorev)); ic.appendChild(c); });
      if ((k.sonuclar || []).length) ic.appendChild(ikonlu(el("h4"), "ekip", T("Üye raporları"), 13));
      (k.sonuclar || []).forEach((s) => { const c = el("div", "ek-kart"); const bas = el("div", "ek-uye-bas");
        const n = el("span", "ek-nokta"); n.style.background = renk(s.ad); bas.appendChild(n); bas.appendChild(ikon(s.hata ? "uyari" : "tamam", 14));
        bas.appendChild(el("strong", "", s.ad + " / " + s.ajan)); c.appendChild(bas);
        c.appendChild(el("div", "", s.hata ? T("HATA: {hata}", {hata: s.hata}) : (s.metin || "")));
        c.appendChild(meta("dosya", (s.yazmalar || []).length ? (s.yazmalar || []).join(", ") : T("hiçbir dosya yazmadı"))); ic.appendChild(c); });
      if ((k.pano || []).length) { ic.appendChild(ikonlu(el("h4"), "pano", T("Pano"), 13));
        k.pano.forEach((m) => { const s = el("div", "ek-mesaj"); const kim = el("span", "ek-kim"); kim.style.color = renk(m.kimden);
          kim.appendChild(el("span", "", m.kimden)); kim.appendChild(ikon("sagok", 12)); kim.appendChild(el("span", "", m.kime || "herkes"));
          s.appendChild(kim); s.appendChild(el("span", "secilebilir", m.metin)); ic.appendChild(s); }); }
      if (k.birlestirici) { ic.appendChild(ikonlu(el("h4"), "birlestir", T("Birleştirici"), 13));
        const md = el("div", "secilebilir"); md.appendChild(typeof markdown === "function" ? markdown(k.birlestirici) : document.createTextNode(k.birlestirici)); ic.appendChild(md); }
      return;
    }
    const liste = el("div", "ek-kartlar");
    if (!D.kosular.length) liste.appendChild(el("div", "ek-sonuk", T("Henüz ekip koşusu yok.")));
    D.kosular.forEach((k) => {
      const c = el("button", "ek-kart tikla");
      const p = D.projeler.find((x) => x.kimlik === k.proje);
      const bas = el("div", "ek-uye-bas ek-durum " + k.durum); const di = el("span", "ek-durum-ikon"); di.appendChild(durumIkonu(k.durum, 15)); bas.appendChild(di);
      bas.appendChild(el("span", "", (k.baslangic || "").replace("T", " ") + " · " + T(DURUM_METNI[k.durum] || k.durum)));
      bas.appendChild(ikonlu(el("span", "ek-meta"), "klasor", p ? p.ad : T("(varsayılan klasör)"), 13)); c.appendChild(bas);
      c.appendChild(ikonlu(el("div", "ek-dugme"), "hedef", kisalt(k.gorev || "", 140), 14));
      c.addEventListener("click", () => api().ekip_kosu(k.kimlik).then((r) => { if (r && r.ok) { D.detay = r.kosu; ciz(); } }));
      liste.appendChild(c);
    });
    ic.appendChild(liste);
  }

  return {ac, kapat, ciz, olay, hedef, sekmeCiz, renk, DURUM_METNI, D, yenile: yukle, gorevBaslat, kosuSurer};
})();
