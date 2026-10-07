/* ofis/ofis.js — Ekip alaninin 3B ofis gorunumu: window.Ofis.

   Katmanlar (docs/OFIS_TASARIM.md 4):
     ofis/durum.js  saf durum makinesi (olay -> her ajanin masasi ve durumu)
     ofis/sahne.js  three.js sahnesi: cizer, karar vermez
     ofis/ofis.js   bu dosya: iskelet, paneller, cekmece, kopru cagrilari

   Ofis HICBIR izin vermez ve hicbir kontrolu atlatmaz: gorev baslatma, plan
   onayi, pano ve durdurma ekip.js'in mevcut kopru cagrilaridir. Ekrandaki her
   hareket gercek bir olaydan gelir (uydurma animasyon yok).

   three.js (vendor/three.min.js) TEMBEL yuklenir: Ekip alani hic acilmazsa
   uygulamanin acilisi 650 KB betik ayristirmaz. WebGL yoksa ya da betik
   yuklenemezse Ekip alani bugunku kart gorunumune duser; bos ekran yok.

   Ana arayuzden (index.html): el, t, ikon, toast, bosalt, kisalt. */
"use strict";
window.Ofis = (() => {
  const T = (s, p) => (typeof t === "function" ? t(s, p) : s);
  const D = {
    kip: null,              // null: denenmedi | "3b" | "kart" (WebGL yok)
    acik: false, cekmece: false, iskelet: null,
    panel: null,            // sag kart: {tur: "ajan"|"masa"|"ise_al"|"sonuc", kod}
    girenler: new Set(),    // yeni ise alinan: kapidan girer
    silOnay: null,          // iki adimli silme: onay bekleyen ajan adi
    masalar: [], ajanlar: [],
    yukleniyor: null,
    durum: null,            // canli ofis durumu (ofis/durum.js)
    oynatma: null,          // gecmis oynatma: {kimlik, olaylar, i, hiz, duraklat, durum}
    cikanlar: new Set(),    // kapidan cikmis gecici kopyalar
    balonlar: new Map(),    // balon imzasi -> ilk gosterim zamani
    saat: null,
  };
  /* Sistem karakterleri: kullanici silemez, duzenleyemez. Ad cakismasin diye
     '@' onekli (ajan adlari harf/rakam/_/- ile sinirli). */
  const SISTEM = [{ad: "@planlayici", gorunenAd: "Planlayıcı", sistem: true, renk: "#9c9a94", gorunum: 0},
                  {ad: "@birlestirici", gorunenAd: "Birleştirici", sistem: true, renk: "#7d7266", gorunum: 0}];

  function api() { return window.pywebview && window.pywebview.api; }
  function kap() { return document.getElementById("ekip-gorunum"); }
  function ikonlu(dugum, im, metin, boyut) { dugum.appendChild(ikon(im, boyut || 15)); dugum.appendChild(el("span", "", metin)); return dugum; }

  /* ---------------- hazirlik: WebGL + three.js ---------------- */
  function betikYukle(yol) {
    return new Promise((coz) => {
      const s = document.createElement("script");
      s.src = yol; s.onload = () => coz(true); s.onerror = () => coz(false);
      document.head.appendChild(s);
    });
  }
  function hazirla() {
    if(typeof arayuzAyar!=="undefined" && arayuzAyar.gorunum.ekip_gorunumu==="kart")return Promise.resolve("kart");
    if (D.kip) return Promise.resolve(D.kip);
    if (D.yukleniyor) return D.yukleniyor;
    if (!window.OfisSahne || !OfisSahne.webglVar()) { D.kip = "kart"; return Promise.resolve(D.kip); }
    D.yukleniyor = (window.THREE ? Promise.resolve(true) : betikYukle("vendor/three.min.js")).then((ok) => {
      D.kip = ok && window.THREE ? "3b" : "kart";
      D.yukleniyor = null;
      return D.kip;
    });
    return D.yukleniyor;
  }
  function etkin() { return D.kip === "3b" && (typeof arayuzAyar==="undefined" || arayuzAyar.gorunum.ekip_gorunumu!=="kart"); }

  /* ---------------- ac / kapat ---------------- */
  function ac() {
    D.acik = true;
    const a = api();
    const duzen = a && a.ofis_duzeni ? a.ofis_duzeni() : Promise.resolve(null);
    return Promise.all([hazirla(), duzen]).then(([, d]) => {
      if (d && d.ok !== false) { D.masalar = d.masalar || []; D.ajanlar = d.ajanlar || []; }
      if (window.OfisDurum) D.durum = OfisDurum.ajanlariEsitle(durumAl(), ajanAdlari());
      if (D.acik && etkin() && D.iskelet) { sahneyiTazele(); OfisSahne.baslat(); }
    });
  }
  function kapat() {
    D.acik = false;
    if (window.OfisSahne) OfisSahne.durdur();
  }
  /* Pencere gizliyken ya da Ayarlar acikken kare cizilmez. */
  function gorunurMu() {
    const perde = document.getElementById("ayar-perde");
    return D.acik && !document.hidden && !(perde && perde.classList.contains("acik"));
  }
  function gorunurlukTazele() {
    if (!etkin() || !D.iskelet) return;
    if (gorunurMu()) OfisSahne.baslat(); else OfisSahne.durdur();
  }
  document.addEventListener("visibilitychange", gorunurlukTazele);
  (() => {
    const perde = document.getElementById("ayar-perde");
    if (perde && window.MutationObserver) new MutationObserver(gorunurlukTazele).observe(perde, {attributes: true, attributeFilter: ["class"]});
  })();

  /* ---------------- iskelet (BIR KEZ) ----------------
     Tuval ve olaylari sabit kalir; ciz() yalnizca panelleri tazeler. Tuvali
     her cizimde yeniden kurmak suruklemeyi koparirdi (ag.js dersi). */
  function iskelet() {
    const k = kap(); if (!k) return null;
    if (D.iskelet && D.iskelet.kok.parentNode === k) return D.iskelet;
    bosalt(k);
    k.classList.add("ofis");
    const kok = el("div", "of-kok");
    const sahne = el("div", "of-sahne");
    const ust = el("div", "of-ust");
    const bilgi = el("div", "of-ipucu");
    const cekmece = el("aside", "of-cekmece");
    kok.appendChild(sahne); kok.appendChild(cekmece);
    k.appendChild(kok);
    if (!OfisSahne.kur(sahne)) {              /* WebGL baglami acilamadi: kart gorunumu */
      D.kip = "kart"; k.classList.remove("ofis"); bosalt(k); D.iskelet = null;
      return null;
    }
    const onay = el("div", "of-onay");        /* plan onayi: cekmeceden bagimsiz, yeniden cizimde kaybolmaz */
    const panel = el("aside", "of-panel");    /* ajan / masa karti */
    const gorev = el("div", "of-gorev");      /* gorev cubugu */
    sahne.appendChild(ust); sahne.appendChild(onay); sahne.appendChild(panel); sahne.appendChild(gorev); sahne.appendChild(bilgi);
    OfisSahne.D.onSec = secildi;
    D.iskelet = {kok, sahne, ust, bilgi, cekmece, onay, panel, gorev};
    return D.iskelet;
  }

  function ciz() {
    const i = iskelet();
    if (!i) { if (window.Ekip) Ekip.ciz(); return; }
    ustCiz(i.ust);
    ipucuCiz(i.bilgi);
    cekmeceCiz(i.cekmece);
    gorevCubugu(i.gorev);
    panelCiz();
    sahneyiTazele();
    if (gorunurMu()) OfisSahne.baslat();
  }

  /* ---------------- ust cubuk ---------------- */
  /* Gorev formu cekmecede degil: ofisin altindaki gorev cubugunda. */
  const CEKMECE_SEKMELERI = [["ajanlar", "bot", "Ajanlar"], ["projeler", "klasor", "Projeler"], ["gecmis", "degisiklik", "Geçmiş"]];
  function ustCiz(u) {
    bosalt(u);
    const bas = el("div", "of-baslik");
    bas.appendChild(ikon("ekip", 17)); bas.appendChild(el("span", "", T("Ofis")));
    bas.title=T("Ajanları ve yürüttükleri işleri izle. Sade görünüm için Ayarlar > Genel > Gelişmiş > Ekip görünümü.");
    u.appendChild(bas);
    const kosu = window.Ekip && Ekip.D.kosu;
    if (kosu) {
      const d = el("div", "of-durum ek-durum " + kosu.durum);
      d.appendChild(el("span", "ek-nokta " + kosu.durum));
      d.appendChild(el("span", "", T(Ekip.DURUM_METNI[kosu.durum] || kosu.durum)));
      u.appendChild(d);
    }
    if (kosu && kosu.sonuc) {
      const sn = ikonlu(el("button", "of-dugme" + (D.panel && D.panel.tur === "sonuc" ? " acik" : "")), "birlestir", T("Sonuç"), 14);
      sn.addEventListener("click", () => panelAc({tur: "sonuc"}));
      u.appendChild(sn);
    }
    u.appendChild(el("div", "of-bosluk"));
    const al = ikonlu(el("button", "of-dugme" + (D.panel && D.panel.tur === "ise_al" ? " acik" : "")), "yeni", T("İşe al"), 14);
    al.title = T("Yeni ajan ekle");
    al.addEventListener("click", () => panelAc({tur: "ise_al"}));
    u.appendChild(al);
    const don = ikonlu(el("button", "of-dugme"), "hedef", T("Ofise dön"), 14);
    don.title = T("Kamerayı başlangıç görünümüne getir");
    don.addEventListener("click", () => OfisSahne.ofiseDon());
    u.appendChild(don);
    CEKMECE_SEKMELERI.forEach(([kod, im, ad]) => {
      const acik = D.cekmece && Ekip.D.sekme === kod;
      const b = ikonlu(el("button", "of-dugme" + (acik ? " acik" : "")), im, T(ad), 14);
      b.addEventListener("click", () => {
        if (acik) D.cekmece = false; else { D.cekmece = true; Ekip.D.sekme = kod; }
        ciz();
      });
      u.appendChild(b);
    });
  }

  function ipucuCiz(b) {
    bosalt(b);
    b.appendChild(el("span", "", T("Sürükle: döndür · Tekerlek: yakınlaş · Sağ tık: kaydır · Çift tık: odaklan")));
  }

  /* ---------------- cekmece: ekip.js sekmeleri ----------------
     Ajanlar, Projeler, Gecmis ve Gorev formlari ekip.js'in AYNI
     fonksiyonlariyla cizilir; ofis yalnizca kabi saglar. */
  function cekmeceCiz(c) {
    c.classList.toggle("acik", D.cekmece);
    bosalt(c);
    if (!D.cekmece) return;
    const bas = el("div", "of-cekmece-bas");
    const kod = Ekip.D.sekme;
    const s = CEKMECE_SEKMELERI.find((x) => x[0] === kod) || CEKMECE_SEKMELERI[0];
    Ekip.D.sekme = s[0];
    bas.appendChild(ikonlu(el("strong", ""), s[1], T(s[2]), 16));
    const kapa = el("button", "ek-sil"); kapa.title = T("Paneli kapat"); kapa.appendChild(ikon("ret", 15));
    kapa.addEventListener("click", () => { D.cekmece = false; ciz(); });
    bas.appendChild(kapa);
    c.appendChild(bas);
    const ic = el("div", "ek-ic of-cekmece-ic");
    Ekip.sekmeCiz(ic, s[0]);
    c.appendChild(ic);
  }
  /* Plan onay karti ofisin ustunde, kendi panelinde (cekmece kapali da olsa
     gorunur; cekmece yeniden cizilince kaybolmaz). Karar mevcut akis:
     index.onayKarti -> cevapla -> onay_cevapla. */
  function onayHedefi() {
    if (!etkin() || !D.iskelet) return null;
    bosalt(D.iskelet.onay);
    return D.iskelet.onay;
  }

  /* ---------------- durum (ofis/durum.js) ----------------
     Olaylar ofis KAPALIYKEN de durum makinesinden gecer: alan acildiginda
     karakterler zaten dogru yerde durur. Cizim yalnizca gorunurken. */
  const DURUM_METNI = {bosta: "boşta", planda_bekliyor: "sırada", calisiyor: "çalışıyor", dusunuyor: "düşünüyor",
                       onay_bekliyor: "onay bekliyor", bitti: "bitti", hata: "hata", bilinmiyor: "durum bilinmiyor"};
  const BALON_SURESI = 8000;
  function ajanAdlari() {
    const kaynak = D.ajanlar.length ? D.ajanlar : ((window.Ekip && Ekip.D.ajanlar) || []);
    return kaynak.map((a) => a.ad);
  }
  function durumAl() {
    if (!D.durum) D.durum = OfisDurum.bos(ajanAdlari(), OfisSahne.noktaSayilari());
    return D.durum;
  }
  function gosterilen() { return D.oynatma ? D.oynatma.durum : durumAl(); }

  /* Karakterin gorunusu: tanimli ajan kopruden (renk/gorunum), gecici kopya
     bagli oldugu ajanin gorunusuyle; ajani yoksa (varsayilan) notr. */
  function gorunus(k) {
    const sistem = SISTEM.find((x) => x.ad === k.anahtar);
    if (sistem) return Object.assign({}, sistem, {gorunenAd: T(sistem.gorunenAd)});
    const kaynak = D.ajanlar.length ? D.ajanlar : ((window.Ekip && Ekip.D.ajanlar) || []);
    const tanim = kaynak.find((a) => a.ad === k.ajan);
    const renk = tanim ? (tanim.renk || Ekip.renk(tanim.ad)) : (k.gecici ? "#b9b2a6" : Ekip.renk(k.anahtar));
    const g = tanim && Number.isInteger(tanim.gorunum) ? tanim.gorunum : (String(k.isci || k.anahtar).length % 8);
    return {ad: k.anahtar, renk, gorunum: g, gorunenAd: k.gecici ? (k.isci || k.anahtar.slice(1)) : k.anahtar};
  }

  function sahneyiTazele() {
    if (!etkin() || !D.iskelet) return;
    OfisSahne.masaAdlari(D.masalar);
    uygula(gosterilen());
  }
  function uygula(durum) {
    const karakterler = Object.values(durum.karakterler).filter((k) => !(k.gecici && k.ayrildi && D.cikanlar.has(k.anahtar)));
    OfisSahne.ajanlariAyarla(karakterler.map(gorunus));
    D.girenler.forEach((a) => { if (OfisSahne.D.ajanlar[a]) { OfisSahne.kapidanGir(a); D.girenler.delete(a); } });
    OfisSahne.ekipVurgula(new Set(window.Ekip ? Array.from(Ekip.D.secili) : []));
    /* dolu masanin etiketi soluklasir: ajan etiketi onun ustune biniyordu */
    const dolu = new Set(karakterler.filter((k) => k.masa !== "bekleme").map((k) => k.masa));
    Object.keys(OfisSahne.D.masalar).forEach((m) => {
      const e = OfisSahne.D.masalar[m].etiket; if (e) e.classList.toggle("dolu", dolu.has(m));
    });
    karakterler.forEach((k) => {
      OfisSahne.hedefle(k.anahtar, k.masa, k.nokta);
      OfisSahne.durumGoster(k.anahtar, k.durum);
      const s = OfisSahne.D.ajanlar[k.anahtar]; if (!s) return;
      s.rozet.textContent = (k.isci && !k.gecici && k.isci !== k.anahtar ? k.isci + " · " : "") + T(DURUM_METNI[k.durum] || k.durum);
      s.rozet.className = "of-rozet " + k.durum;
      s.etiket.classList.toggle("gecici", k.gecici);
      balonCiz(s, k);
      zarfCiz(s, k);
      if (k.gecici && k.ayrildi && !D.cikanlar.has(k.anahtar)) {
        /* kosu bitti: kopya kapiya yurur, sonra ofisten cikar */
        setTimeout(() => { D.cikanlar.add(k.anahtar); if (D.acik && etkin()) uygula(gosterilen()); }, 3000);
      }
    });
  }
  /* Pano balonu: ilk ~60 karakter, duz metin (textContent); tiklayinca tamami.
     Model ciktisi VERIDIR: baglanti tiklanmaz, HTML yorumlanmaz. */
  function balonCiz(s, k) {
    let b = s.etiket.querySelector(".of-balon");
    /* gosterim zamani sunumun isi: durum nesnesine yazilmaz (saf kalir) */
    const imza = k.balon ? k.anahtar + "#" + k.balon.sira : "";
    if (imza && !D.balonlar.has(imza)) D.balonlar.set(imza, Date.now());
    const goster = imza && Date.now() - D.balonlar.get(imza) < BALON_SURESI;
    if (!goster) { if (b) b.remove(); return; }
    if (!b) {
      b = el("div", "of-balon");
      b.addEventListener("click", (e) => { e.stopPropagation(); b.classList.toggle("acik"); b.textContent = b.classList.contains("acik") ? b.dataset.tam : b.dataset.kisa; });
      s.etiket.insertBefore(b, s.etiket.firstChild);
      setTimeout(() => { if (D.acik && etkin()) uygula(gosterilen()); }, BALON_SURESI + 50);
    }
    b.dataset.kisa = k.balon.metin; b.dataset.tam = k.balon.tam;
    if (!b.classList.contains("acik")) b.textContent = k.balon.metin;
    b.title = k.balon.kime && k.balon.kime !== "herkes" ? "→ " + k.balon.kime : T("herkese");
  }
  function zarfCiz(s, k) {
    let z = s.etiket.querySelector(".of-zarf");
    if (!k.zarf) { if (z) z.remove(); return; }
    if (!z) { z = el("span", "of-zarf"); z.appendChild(ikon("pano", 12)); z.appendChild(el("span", "")); s.etiket.appendChild(z); }
    z.lastChild.textContent = String(k.zarf); z.title = T("Okunmamış pano mesajı");
  }

  /* Sessizlik denetimi: calisan karakterden uzun sure olay gelmezse durum
     makinesi onu 'bilinmiyor' yapar (_zaman olayi). Yalnizca kosu surerken. */
  function saatKur() {
    const d = durumAl();
    const surer = d.kosu && !["bitti", "hata", "reddedildi", "plan_hatasi"].includes(d.kosu.durum);
    if (surer && !D.saat) D.saat = setInterval(() => olay({tip: "_zaman", veri: {simdi: Date.now()}}), 30000);
    if (!surer && D.saat) { clearInterval(D.saat); D.saat = null; }
  }

  /* Tik: ajan -> ajan karti; Ctrl/Shift+tik -> ekibe ekle/cikar (gorev
     cubugundaki secim). Masa -> masa karti (istisare: pano). Bos -> kapat. */
  function secildi(v, mod) {
    if (v && v.tur === "ajan" && mod && mod.ekle && tanimli(v.kod)) { ekipDegistir(v.kod); return; }
    if (!v) { panelAc(null); return; }
    if (v.tur === "nesne") { nesneyeGit(v.kod); return; }
    panelAc({tur: v.tur, kod: v.kod});
  }
  function tanimli(ad) { return !!window.Ekip && Ekip.D.ajanlar.some((a) => a.ad === ad); }
  function ekipDegistir(ad) {
    if (Ekip.D.secili.has(ad)) Ekip.D.secili.delete(ad); else Ekip.D.secili.add(ad);
    OfisSahne.ekipVurgula(new Set(Ekip.D.secili));
    if (D.iskelet) { gorevCubugu(D.iskelet.gorev); panelCiz(); }
  }

  /* Masadaki esyaya dokunma: ilgili yere gider. Hicbiri yetki vermez;
     dosyalar yalnizca Explorer'da GOSTERILIR (dosya_goster: yurutmez). */
  function nesneyeGit(kod) {
    if (kod === "dosyalar") panelAc({tur: "dosyalar", kod: "dosya"});
    else if (kod === "kodlar") panelAc({tur: "dosyalar", kod: "kod"});
    else if (kod === "ag") { if (typeof gorunum === "function") gorunum("ag"); }
    else if (kod === "gecmis") { Ekip.D.sekme = "gecmis"; Ekip.D.detay = null; D.cekmece = true; ciz(); }
  }
  /* Bu kosuda o masada YAZILAN dosyalar (olaylardan; en yenisi ustte). */
  function yazilanlar(d, masa) {
    const yollar = [];
    (d.masaGecmisi[masa] || []).slice().reverse().forEach((a) => {
      if (["write_file", "edit_file"].includes(a.arac) && a.yol && !yollar.some((y) => y.yol === a.yol)) yollar.push(a);
    });
    return yollar;
  }
  function dosyalarKarti(c, masa) {
    const d = gosterilen();
    baslikSatiri(c, "", T(masa === "kod" ? "Yazılan kod dosyaları" : "Yazılan dosyalar"), masaAdi(masa));
    c.appendChild(el("div", "ek-alt", T("Dosyaya tıkla: Explorer'da seçili açılır.")));
    const liste = yazilanlar(d, masa);
    if (!liste.length) c.appendChild(el("div", "ek-sonuk", T("Bu koşuda bu masada dosya yazılmadı.")));
    liste.forEach((a) => {
      const s = el("button", "of-kart-satir tikla");
      s.appendChild(el("span", "", dosyaAdi(a.yol))); s.title = a.yol;
      const k = d.karakterler[a.anahtar];
      s.appendChild(el("span", "of-kart-sonuk", k ? gorunus(k).gorunenAd : a.anahtar));
      s.addEventListener("click", () => api().dosya_goster(a.yol).then((r) => { if (r && !r.ok) toast(r.hata, "kotu"); }));
      c.appendChild(s);
    });
  }

  /* ---------------- sag kart ---------------- */
  function panelAc(p) {
    D.panel = p; D.silOnay = null;
    OfisSahne.sec(p && p.tur === "ajan" ? p.kod : null);
    if (D.iskelet) { ustCiz(D.iskelet.ust); panelCiz(); }
  }
  function panelCiz() {
    if (!D.iskelet) return;
    const c = D.iskelet.panel;
    bosalt(c);
    c.classList.toggle("acik", !!D.panel);
    if (!D.panel) return;
    const kapa = el("button", "ek-sil of-panel-kapat"); kapa.title = T("Paneli kapat"); kapa.appendChild(ikon("ret", 15));
    kapa.addEventListener("click", () => panelAc(null));
    c.appendChild(kapa);
    ({ajan: ajanKarti, masa: masaKarti, ise_al: iseAlKarti, duzenle: ajanDuzenleKarti, sonuc: sonucKarti, dosyalar: dosyalarKarti}[D.panel.tur] || (() => {}))(c, D.panel.kod);
  }
  function baslikSatiri(c, renk, ad, etiket) {
    const b = el("div", "of-kart-bas");
    const n = el("span", "ek-nokta"); if (renk) n.style.background = renk; b.appendChild(n);
    b.appendChild(el("strong", "", ad));
    if (etiket) b.appendChild(el("span", "of-kart-etiket", etiket));
    c.appendChild(b);
  }
  function bolum(c, im, baslik) { c.appendChild(ikonlu(el("h4", "of-kart-h"), im, T(baslik), 13)); }
  function masaAdi(kod) { const m = D.masalar.find((x) => x.kod === kod); return m ? m.ad : kod; }
  function dosyaAdi(yol) { return String(yol || "").split(/[\\/]/).pop(); }
  function aracSatiri(a) {
    const s = el("div", "of-kart-satir");
    s.appendChild(el("span", "", (typeof aracBasligi === "function" ? aracBasligi(a.arac) : a.arac) + (a.yol ? " — " + dosyaAdi(a.yol) : "")));
    s.appendChild(el("span", "of-kart-sonuk", masaAdi(a.masa)));
    return s;
  }

  function ajanKarti(c, anahtar) {
    const d = gosterilen(), k = d.karakterler[anahtar];
    if (!k) { c.appendChild(el("div", "ek-sonuk", T("Bu ajan artık ofiste değil."))); return; }
    const g = gorunus(k);
    const sistem = OfisDurum.SISTEM.includes(anahtar);
    baslikSatiri(c, g.renk, g.gorunenAd, sistem ? T("sistem") : k.gecici ? T("geçici kopya") : "");
    const tanim = ((window.Ekip && Ekip.D.ajanlar) || []).find((a) => a.ad === (k.ajan || anahtar));
    if (sistem) c.appendChild(el("div", "ek-alt", T(anahtar === "@planlayici" ? "Görevi alt görevlere böler; planı sen onaylarsın."
                                                                               : "Üyelerin sonuçlarını toplar ve düzeltir.")));
    if (tanim && tanim.rol) c.appendChild(el("div", "ek-alt", tanim.rol));
    /* durum ve yer */
    const dr = el("div", "of-kart-durum");
    dr.appendChild(el("span", "of-rozet " + k.durum, T(DURUM_METNI[k.durum] || k.durum)));
    dr.appendChild(el("span", "of-kart-sonuk", masaAdi(k.masa) + (k.isci ? " · " + k.isci : "")));
    c.appendChild(dr);
    /* baglanti · model ve limit durumu: kopruden (anahtar gelmez) */
    const model = el("div", "of-kart-model");
    if (tanim) {
      model.appendChild(el("div", "of-kart-sonuk", (tanim.baglanti_ad || tanim.saglayici || "") + " · " + (tanim.etkin_model || tanim.model || "")));
      c.appendChild(model);
      const a = api();
      if (a && a.ofis_ajan_karti) {
        a.ofis_ajan_karti(tanim.ad, k.isci || "", (d.kosu && d.kosu.kimlik) || "").then((r) => {
          if (!r || !r.ok || !model.isConnected) return;
          bosalt(model);
          (r.zincir || []).forEach((h, i) => {
            const s = el("div", "of-kart-satir" + (h.dolu_bitis ? " dolu" : ""));
            s.appendChild(el("span", "", (i ? "↳ " : "") + h.etiket));
            s.appendChild(el("span", "of-kart-sonuk", h.dolu_bitis ? T("limit doldu, {saat}'e kadar", {saat: h.dolu_bitis.slice(11)}) : (i ? "" : T("kullanılıyor"))));
            model.appendChild(s);
          });
          if (r.yazdiklari && r.yazdiklari.length) yazdiklariCiz(yz, r.yazdiklari, true);
        });
      }
    }
    if (k.modelGecis) c.appendChild(ikonlu(el("div", "ek-meta"), "uyari", T("Limit doldu, geçti: {yeni}", {yeni: k.modelGecis.yeni || "?"}), 13));
    /* son arac cagrilari ve yazdigi dosyalar */
    bolum(c, "gorev", "Son işler");
    if (!k.sonAraclar.length) c.appendChild(el("div", "ek-sonuk", T("Bu koşuda henüz iş yok.")));
    k.sonAraclar.slice().reverse().forEach((a) => c.appendChild(aracSatiri(a)));
    const yz = el("div", "");
    c.appendChild(yz);
    yazdiklariCiz(yz, k.yazdiklari, false);
    /* panoya ona ozel mesaj: yalnizca calisan bir isciye (pano isci adiyla adresler) */
    if (!D.oynatma && !sistem) {
      bolum(c, "pano", "Ona yaz");
      const surer = d.kosu && !["bitti", "hata", "reddedildi", "plan_hatasi"].includes(d.kosu.durum);
      if (k.isci && surer) c.appendChild(panoGirdisi(() => k.isci, T("{ad} için not…", {ad: k.isci})));
      else c.appendChild(el("div", "ek-sonuk", T("Ajan bir görevde çalışırken ona panodan yazabilirsin.")));
    }
    /* Tek ajana dogrudan gorev: planlayici yok. Yazma yolu (proje icinde)
       plan onay kartinda gorunur; plan_dogrula ve dar isci politikasi ayni. */
    if (tanim && !D.oynatma && !Ekip.kosuSurer()) {
      bolum(c, "hedef", "Bu ajana görev ver");
      const f = el("div", "of-form");
      const g = el("textarea", "of-tek-gorev"); g.rows = 3; g.placeholder = T("Yalnızca bu ajanın yapacağı iş…");
      const y = el("input", "of-tek-yol"); y.placeholder = tanim.ad + "/"; y.spellcheck = false;
      y.title = T("Ajanın yazabileceği tek yol: proje klasörüne göre göreli dosya ya da klasör");
      const ys = el("label", "of-form-satir"); ys.appendChild(el("span", "", T("Yazacağı yol"))); ys.appendChild(y);
      const b = ikonlu(el("button", "birincil ek-dugme"), "oynat", T("Görevi ver"), 15);
      b.addEventListener("click", () => {
        const metin = g.value.trim(); if (!metin) { toast(T("Görev boş"), "kotu"); return; }
        api().ekip_tek_gorev_baslat(metin, Ekip.D.proje || null, tanim.ad, y.value.trim(), null).then((r) => {
          if (r && !r.ok) { toast(r.hata, "kotu"); return; }
          Ekip.D.kosu = {kimlik: null, durum: "planlaniyor", uyeler: {}, pano: [], sonuc: "", plan: null};
          panelAc(null); ciz();
        });
      });
      f.appendChild(g); f.appendChild(ys); f.appendChild(b); c.appendChild(f);
    }
    /* tanimli ajan: ekip secimi ve silme */
    if (tanim && !D.oynatma) {
      const dug = el("div", "of-kart-dugmeler");
      const ekipte = Ekip.D.secili.has(tanim.ad);
      const b1 = ikonlu(el("button", "of-dugme" + (ekipte ? " acik" : "")), ekipte ? "onay" : "yeni", T(ekipte ? "Ekipte" : "Ekibe ekle"), 14);
      b1.addEventListener("click", () => ekipDegistir(tanim.ad));
      dug.appendChild(b1);
      const duzenle = ikonlu(el("button", "of-dugme"), "kalem", T("Düzenle"), 14);
      duzenle.addEventListener("click", () => panelAc({tur: "duzenle", kod: tanim.ad}));
      dug.appendChild(duzenle);
      const onayda = D.silOnay === tanim.ad;
      const b2 = ikonlu(el("button", "of-dugme tehlike"), "cop", onayda ? T("Emin misin?") : T("Ajanı sil"), 14);
      b2.addEventListener("click", () => ajanSil(tanim.ad));
      dug.appendChild(b2);
      c.appendChild(dug);
    }
  }
  function yazdiklariCiz(kap_, yollar, gunluk) {
    bosalt(kap_);
    if (!yollar || !yollar.length) return;
    bolum(kap_, "dosya", gunluk ? "Yazdığı dosyalar (günlük)" : "Yazdığı dosyalar");
    yollar.forEach((y) => { const s = el("div", "of-kart-satir secilebilir"); s.appendChild(el("span", "", y)); s.title = y; kap_.appendChild(s); });
  }
  function panoGirdisi(kime, yer) {
    const g = el("div", "of-kart-gir");
    const i = el("input"); i.placeholder = yer;
    const b = ikonlu(el("button", "of-dugme"), "yolla", T("Gönder"), 14);
    const yolla = () => {
      const m = i.value.trim(); if (!m) return;
      api().ekip_pano_yaz(m, kime()).then((r) => { if (r && !r.ok) { toast(r.hata, "kotu"); return; } i.value = ""; toast(T("Panoya yazıldı"), "iyi"); });
    };
    b.addEventListener("click", yolla); i.addEventListener("keydown", (e) => { if (e.key === "Enter") yolla(); });
    g.appendChild(i); g.appendChild(b);
    return g;
  }
  function ajanSil(ad) {
    if (D.silOnay !== ad) {
      D.silOnay = ad; panelCiz();
      setTimeout(() => { if (D.silOnay === ad) { D.silOnay = null; panelCiz(); } }, 4000);
      return;
    }
    D.silOnay = null;
    api().ajan_sil(ad).then((r) => {
      if (r && !r.ok) { toast(r.hata, "kotu"); return; }
      Ekip.D.secili.delete(ad);
      /* karakter kapidan cikar, sonra listeden duser */
      OfisSahne.hedefle(ad, "kapi", 1);
      panelAc(null);
      setTimeout(() => ajanlariTazele(), 2600);
    });
  }
  function ajanlariTazele() {
    const a = api();
    return Promise.all([Ekip.yenile(), a.ofis_duzeni ? a.ofis_duzeni() : null]).then(([, d]) => {
      if (d && d.ok !== false) { D.masalar = d.masalar || D.masalar; D.ajanlar = d.ajanlar || []; }
      D.durum = OfisDurum.ajanlariEsitle(durumAl(), ajanAdlari());
      if (D.iskelet) ciz();
    });
  }

  function masaKarti(c, kod) {
    const m = D.masalar.find((x) => x.kod === kod) || {kod, ad: kod, aciklama: ""};
    const d = gosterilen();
    baslikSatiri(c, "", m.ad, "");
    if (m.aciklama) c.appendChild(el("div", "ek-alt", m.aciklama));
    bolum(c, "ekip", "Şu an burada");
    const burada = Object.values(d.karakterler).filter((k) => k.masa === kod && !(k.gecici && k.ayrildi));
    if (!burada.length) c.appendChild(el("div", "ek-sonuk", T("Kimse yok.")));
    burada.forEach((k) => {
      const s = el("button", "of-kart-satir tikla");
      s.appendChild(el("span", "", gorunus(k).gorunenAd));
      s.appendChild(el("span", "of-rozet " + k.durum, T(DURUM_METNI[k.durum] || k.durum)));
      s.addEventListener("click", () => panelAc({tur: "ajan", kod: k.anahtar}));
      c.appendChild(s);
    });
    bolum(c, "gorev", "Son işler");
    const gecmis = (d.masaGecmisi[kod] || []).slice().reverse();
    if (!gecmis.length) c.appendChild(el("div", "ek-sonuk", T("Bu koşuda bu masada iş yapılmadı.")));
    gecmis.forEach((a) => {
      const s = aracSatiri(a);
      s.lastChild.textContent = d.karakterler[a.anahtar] ? gorunus(d.karakterler[a.anahtar]).gorunenAd : a.anahtar;
      c.appendChild(s);
    });
    if (kod === "istisare") panoBolumu(c, d);
  }
  /* Istisare masasi: butun pano. Kullanici herkese ya da tek isciye yazar
     (mevcut ekip_pano_yaz; mesaj izin vermez, isciye veri olarak teslim edilir). */
  function panoBolumu(c, d) {
    bolum(c, "pano", "Pano");
    const liste = el("div", "of-pano");
    const pano = (window.Ekip && Ekip.D.kosu && Ekip.D.kosu.pano) || [];
    if (!pano.length) liste.appendChild(el("div", "ek-sonuk", T("Henüz mesaj yok.")));
    pano.forEach((m) => {
      const s = el("div", "of-pano-mesaj");
      s.appendChild(el("span", "of-pano-kim", m.kimden + " → " + (m.kime || T("herkes"))));
      s.appendChild(el("span", "secilebilir", m.metin));
      liste.appendChild(s);
    });
    c.appendChild(liste);
    const surer = d.kosu && !["bitti", "hata", "reddedildi", "plan_hatasi"].includes(d.kosu.durum);
    if (!surer || D.oynatma) { c.appendChild(el("div", "ek-sonuk", T("Panoya yalnızca çalışan bir ekip görevinde yazılır."))); return; }
    const kime = el("select", "of-hiz");
    [["herkes", T("herkese")]].concat(Object.keys(d.isciler).map((i) => [i, i])).forEach(([v, e]) => { const o = el("option", "", e); o.value = v; kime.appendChild(o); });
    c.appendChild(kime);
    c.appendChild(panoGirdisi(() => kime.value, T("Ekibe not yaz…")));
  }

  /* Ise al: ad, rol, API baglantisi + model (Ayarlar > Model), renk.
     Kayit mevcut ajan_yaz (fail-closed dogrulama policy.toml'da). */
  const RENK_PALETI = ["#dcaa65", "#79b9a0", "#91a9e8", "#c4a0d9", "#e08f8f", "#8fd0e0", "#e0c98f", "#b9b2a6"];
  function iseAlKarti(c) {
    baslikSatiri(c, "", T("Yeni ajan"), "");
    ajanFormu(c, null, (isim) => {
      D.girenler.add(isim); Ekip.D.secili.add(isim);
      panelAc({tur: "ajan", kod: isim}); ajanlariTazele();
    });
  }
  function ajanDuzenleKarti(c, ad) {
    const ajan = Ekip.D.ajanlar.find((a) => a.ad === ad);
    if (!ajan || D.oynatma) return;
    baslikSatiri(c, ajan.renk, ad, T("Düzenle"));
    ajanFormu(c, ajan, (isim) => ajanlariTazele().then(() => panelAc({tur: "ajan", kod: isim})));
  }
  /* Ofis ve Ekip > Ajanlar ayni formu kullanir; izin dogrulamasi ajan_yaz'da. */
  function ajanFormu(c, ajan, kaydedildi) {
    const form = el("div", "of-form");
    form.appendChild(el("div", "ek-alt", T("Ajan, Ayarlar > Model'deki bir API bağlantısıyla çalışır.")));
    const satir = (etiket, girdi) => {
      const s = el("label", "of-form-satir"); s.appendChild(el("span", "", T(etiket)));
      if (["INPUT", "SELECT", "TEXTAREA"].includes(girdi.tagName)) girdi.setAttribute("aria-label", T(etiket));
      s.appendChild(girdi); form.appendChild(s); return girdi;
    };
    const ad = satir("Ad", el("input")); ad.placeholder = "yazar"; ad.spellcheck = false;
    ad.value = ajan ? ajan.ad : ""; ad.readOnly = !!ajan;
    const rol = satir("Rol (isteğe bağlı)", el("input")); rol.placeholder = T("Metinleri yazar");
    rol.value = ajan ? ajan.rol || "" : "";
    const bag = satir("Bağlantı", el("select"));
    const model = satir("Model", el("select"));
    let renk = (ajan && ajan.renk) || RENK_PALETI[D.ajanlar.length % RENK_PALETI.length];
    const palet = el("div", "of-palet");
    const paletCiz = () => {
      bosalt(palet);
      (RENK_PALETI.includes(renk) ? RENK_PALETI : [renk, ...RENK_PALETI]).forEach((r) => { const b = el("button", "of-renk" + (r === renk ? " secili" : "")); b.style.background = r; b.title = r;
        b.addEventListener("click", (e) => { e.preventDefault(); renk = r; paletCiz(); }); palet.appendChild(b); });
    };
    paletCiz(); satir("Renk", palet);
    const gorunum = satir("Görünüm", el("select"));
    const otomatik = el("option", "", T("Otomatik")); otomatik.value = ""; gorunum.appendChild(otomatik);
    for (let i = 0; i < 8; i++) { const o = el("option", "", String(i + 1)); o.value = String(i); gorunum.appendChild(o); }
    gorunum.value = ajan && ajan.gorunum != null ? String(ajan.gorunum) : "";
    let baglantilar = [];
    const modelleriDoldur = () => {
      bosalt(model);
      const b = baglantilar.find((x) => x.kimlik === bag.value);
      if (b && ajan && !ajan.model) { const o = el("option", "", T("Otomatik")); o.value = ""; model.appendChild(o); }
      if (!b && ajan && !ajan.baglanti) { const o = el("option", "", ajan.model || T("Otomatik")); o.value = ajan.model || ""; model.appendChild(o); return; }
      ((b && b.modeller) || []).forEach((m) => { const o = el("option", "", m); o.value = m; model.appendChild(o); });
      if (ajan && bag.value === ajan.baglanti) {
        if (ajan.model && ![...model.options].some((o) => o.value === ajan.model)) {
          const o = el("option", "", ajan.model); o.value = ajan.model; model.appendChild(o);
        }
        model.value = ajan.model || "";
      }
    };
    bag.addEventListener("change", modelleriDoldur);
    api().baglantilar().then((r) => {
      baglantilar = (r && r.baglantilar) || [];
      if (ajan && !ajan.baglanti) { const o = el("option", "", T("Mevcut bağlantıyı koru")); o.value = ""; bag.appendChild(o); }
      else if (!baglantilar.length) { const o = el("option", "", T("(bağlantı yok — Ayarlar > Model)")); o.value = ""; bag.appendChild(o); }
      baglantilar.forEach((b) => { const o = el("option", "", b.ad + (b.anahtar_var || b.anahtarsiz_olabilir ? "" : " — " + T("anahtar yok"))); o.value = b.kimlik; bag.appendChild(o); });
      if (ajan && ajan.baglanti) bag.value = ajan.baglanti;
      else if (ajan) bag.value = "";
      modelleriDoldur();
      kaydet.disabled = false;
    }).catch(() => {
      toast(T("Ajan kaydedilemedi."), "kotu");
    });
    const kaydet = ikonlu(el("button", "birincil ek-dugme"), "bot", T(ajan ? "Kaydet" : "İşe al"), 15);
    kaydet.disabled = true;
    kaydet.addEventListener("click", () => {
      const isim = ad.value.trim();
      if (!isim) { toast(T("Ajan adı gerekli"), "kotu"); return; }
      if (!bag.value && !(ajan && !ajan.baglanti)) { toast(T("Önce Ayarlar > Model'den bir API bağlantısı ekle."), "kotu"); return; }
      const eski = !bag.value && ajan;
      kaydet.disabled = true;
      api().ajan_yaz(isim, eski ? ajan.saglayici : "", model.value, eski ? ajan.anahtar_yuvasi || "" : "", rol.value.trim(), eski ? ajan.taban_url || "" : "", bag.value, renk, gorunum.value === "" ? null : Number(gorunum.value)).then((r) => {
        kaydet.disabled = false;
        if (r && !r.ok) { toast(r.hata, "kotu"); return; }
        toast(T("Ajan kaydedildi"), "iyi");
        kaydedildi(isim);
      }).catch(() => {
        kaydet.disabled = false; toast(T("Ajan kaydedilemedi."), "kotu");
      });
    });
    form.appendChild(kaydet);
    c.appendChild(form);
  }

  function sonucKarti(c) {
    const kosu = window.Ekip && Ekip.D.kosu;
    baslikSatiri(c, "", T("Birleştirici"), "");
    const md = el("div", "secilebilir of-sonuc");
    const metin = (kosu && kosu.sonuc) || "";
    md.appendChild(typeof markdown === "function" ? markdown(metin) : document.createTextNode(metin));
    c.appendChild(md);
  }

  /* ---------------- gorev cubugu ----------------
     Proje, ekip (cip ya da sahnede Ctrl/Shift+tik), gorev metni. Baslatma
     ekip.js'in AYNI yolu (Ekip.gorevBaslat -> ekip_gorev_baslat). */
  function gorevCubugu(c) {
    bosalt(c);
    if (D.oynatma) { c.classList.remove("acik"); return; }
    c.classList.add("acik");
    const surer = Ekip.kosuSurer();
    const proje = el("select", "of-proje"); proje.title = T("Proje");
    if (!Ekip.D.projeler.length) { const o = el("option", "", T("(varsayılan klasör)")); o.value = ""; proje.appendChild(o); }
    Ekip.D.projeler.forEach((p) => { const o = el("option", "", p.ad); o.value = p.kimlik; o.title = p.klasor; if (p.kimlik === Ekip.D.proje) o.selected = true; proje.appendChild(o); });
    proje.addEventListener("change", () => { Ekip.D.proje = proje.value; });
    c.appendChild(proje);
    const cipler = el("div", "of-cipler");
    Ekip.D.ajanlar.forEach((a) => {
      const b = el("button", "of-cip" + (Ekip.D.secili.has(a.ad) ? " secili" : ""));
      const n = el("span", "ek-nokta"); n.style.background = a.renk || Ekip.renk(a.ad); b.appendChild(n);
      b.appendChild(el("span", "", a.ad));
      b.title = T("Ekibe ekle / çıkar (sahnede Ctrl + tık)");
      b.addEventListener("click", () => ekipDegistir(a.ad));
      cipler.appendChild(b);
    });
    if (!Ekip.D.ajanlar.length) {
      const b = ikonlu(el("button", "of-cip"), "yeni", T("Önce bir ajan işe al"), 13);
      b.addEventListener("click", () => panelAc({tur: "ise_al"}));
      cipler.appendChild(b);
    }
    c.appendChild(cipler);
    const alan = el("input", "of-gorev-metin"); alan.placeholder = T("Ekibe görev ver…"); alan.value = D.taslak || "";
    alan.addEventListener("input", () => { D.taslak = alan.value; });
    const baslat = ikonlu(el("button", "birincil ek-dugme"), "oynat", T("Ekibi başlat"), 15);
    baslat.disabled = !Ekip.D.ajanlar.length || surer;
    const git = () => { if (baslat.disabled) return; Ekip.gorevBaslat(alan.value).then((ok) => { if (ok) { D.taslak = ""; alan.value = ""; ciz(); } }); };
    baslat.addEventListener("click", git);
    alan.addEventListener("keydown", (e) => { if (e.key === "Enter") git(); });
    c.appendChild(alan); c.appendChild(baslat);
    if (surer) {
      const dur = ikonlu(el("button", "ikincil ek-dugme"), "dur", T("Durdur"), 15);
      dur.addEventListener("click", () => api().durdur());
      c.appendChild(dur);
    }
  }

  /* Ana olay akisindan (index.olayIsle -> Ekip.olay -> Ofis.olay). */
  function olay(o) {
    if (!o || !window.OfisDurum || !window.OfisSahne) return;
    D.durum = OfisDurum.durumUygula(durumAl(), {tip: o.tip, veri: o.veri || {}, zaman: Date.now()});
    if (o.tip === "ekip_mesaj" && o.veri && o.veri.durum === "planlaniyor") D.cikanlar.clear();
    saatKur();
    if (!etkin() || !D.iskelet) return;
    if (o.tip === "onay_sonucu") {
      /* Karar izi kisa bir sure gorunsun, sonra panel bosalir. */
      const panel = D.iskelet.onay;
      setTimeout(() => { panel.querySelectorAll(".onay.bitti").forEach((k) => k.remove()); }, 1200);
    }
    if (D.acik) {
      ustCiz(D.iskelet.ust);
      if (!D.oynatma) uygula(D.durum);
      if (D.panel && ["ajan", "masa", "sonuc", "dosyalar"].includes(D.panel.tur)) panelCiz();
      if (o.tip === "ekip_mesaj" || o.tip === "gorev_bitti") gorevCubugu(D.iskelet.gorev);
    }
  }

  /* ---------------- gecmis oynatma ----------------
     Kayitli olaylar AYNI durum makinesinden gecer; zaman hizlandirilir.
     Oynatma hicbir kopru YAZMA cagrisi yapmaz (yalnizca ekip_kosu_olaylari
     okunur) ve ekranda canli olmadigini acikca soyler. */
  function oynat(kimlik) {
    const a = api(); if (!a || !etkin()) return Promise.resolve(false);
    return a.ekip_kosu_olaylari(kimlik).then((r) => {
      const olaylar = (r && r.olaylar) || [];
      if (!olaylar.length) { toast(T("Bu koşunun olay kaydı yok; kart görünümü gösteriliyor."), "kotu"); return false; }
      oynatmaBitir();
      D.oynatma = {kimlik, olaylar, i: 0, hiz: 4, duraklat: false, durum: OfisDurum.bos(ajanAdlari(), OfisSahne.noktaSayilari()),
                   zamanlayici: null};
      D.cekmece = false; D.panel = null; ciz();
      oynatmaAdim();
      return true;
    });
  }
  /* tek: duraklatilmis olsa da bir olay uygula (Sonraki olay dugmesi) */
  function oynatmaAdim(tek) {
    const o = D.oynatma; if (!o) return;
    clearTimeout(o.zamanlayici);
    if ((o.duraklat && !tek) || o.i >= o.olaylar.length) { oynatmaCiz(); return; }
    const k = o.olaylar[o.i];
    o.durum = OfisDurum.durumUygula(o.durum, {tip: k.tip, veri: k.veri || {}, zaman: 0});
    o.i += 1;
    uygula(o.durum); oynatmaCiz();
    if (o.i < o.olaylar.length && !o.duraklat) {
      /* kayittaki aralik hizlandirilir; uzun bekleyisler 1.5 sn'ye kisalir */
      const ara = Math.min(1500, Math.max(40, ((o.olaylar[o.i].t || 0) - (k.t || 0)) * 1000 / o.hiz));
      o.zamanlayici = setTimeout(oynatmaAdim, ara);
    }
  }
  function oynatmaBitir() {
    if (!D.oynatma) return;
    clearTimeout(D.oynatma.zamanlayici);
    D.oynatma = null;
    if (D.iskelet) { oynatmaCiz(); uygula(durumAl()); gorevCubugu(D.iskelet.gorev); panelCiz(); }
  }
  function oynatmaCiz() {
    if (!D.iskelet) return;
    let c = D.iskelet.sahne.querySelector(".of-oynatma");
    if (!D.oynatma) { if (c) c.remove(); return; }
    if (!c) { c = el("div", "of-oynatma"); D.iskelet.sahne.appendChild(c); }
    bosalt(c);
    const o = D.oynatma, bitti = o.i >= o.olaylar.length;
    c.appendChild(ikonlu(el("span", "of-oynatma-baslik"), "degisiklik",
      bitti ? T("Oynatma bitti — canlı değil") : T("Geçmiş oynatılıyor — canlı değil"), 14));
    c.appendChild(el("span", "of-oynatma-sayac", o.i + " / " + o.olaylar.length));
    const dugme = (im, baslik, f) => { const b = el("button", "of-dugme"); b.title = T(baslik); b.appendChild(ikon(im, 14)); b.addEventListener("click", f); c.appendChild(b); return b; };
    if (!bitti) dugme(o.duraklat ? "oynat" : "dur", o.duraklat ? "Sürdür" : "Duraklat", () => { o.duraklat = !o.duraklat; oynatmaAdim(); });
    if (!bitti) dugme("sagok", "Sonraki olay", () => oynatmaAdim(true));
    const hiz = el("select", "of-hiz"); hiz.title = T("Oynatma hızı");
    [1, 4, 16].forEach((h) => { const s = el("option", "", h + "×"); s.value = String(h); if (h === o.hiz) s.selected = true; hiz.appendChild(s); });
    hiz.addEventListener("change", () => { o.hiz = Number(hiz.value); });
    c.appendChild(hiz);
    dugme("ret", "Oynatmayı kapat", oynatmaBitir);
  }

  return {D, ac, kapat, ciz, olay, hazirla, etkin, onayHedefi, oynat, oynatmaBitir, SISTEM, ajanFormu};
})();
