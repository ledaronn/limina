/* ag.js — Düşünce Ağı alanı: 3B baloncuklar, bağlantılar, ateşleme.

   Üç boyut kendi elimizle: her düğümün konumu [x,y,z], döndürme iki açı,
   izdüşüm basit perspektif (k = FOV / (FOV + z)). Uzak baloncuk küçülür ve
   soluklaşır; çizim derinliğe göre sıralanır. Dış kütüphane YOK (çevrimdışı
   çalışır, uzak kaynak yok — ARAYUZ.md 9).

   Ateşleme: Python ateşler (ag.ates), biz sonucu OYNATIRIZ. Koşudaki her
   düğümün bir "tik" damgası var; animasyon sanal zamanı ilerletir, düğüm
   kendi tikinde yanar, aksonda ilerleyen ışık kaynağın tikinden hedefin
   varışına kadar yol alır. Yani ekrandaki sıra, modele giden sıranın ta
   kendisidir.

   Ana arayüzden (index.html): el, t, ikon, toast, bosalt, kisalt, markdown. */
"use strict";
window.Ag = (() => {
  const T = (s, p) => (typeof t === "function" ? t(s, p) : s);
  const D = {
    acik: false, aglar: [], ag: null, secili: null, baglaniyor: null,
    secililer: new Set(), kutu: null, secKipi: false,   // alan secimi ve toplu islem
    kosu: null, metin: "", sekme: "denetci",
    donme: {x: -0.35, y: 0.6}, olcek: 1.25, kaydirma: {x: 0, y: 0}, merkez: [0, 0, 0],
    animasyon: null, vurgulu: new Set(), _kare: null, _kaydet: null,
    zaman: 0, nefes: true,   // nefes: duran sahne olu gorunuyordu; kayitli konuma dokunmaz
    uyarilar: [], sonUyari: "",   // statik analiz: olu dugum, etkisiz baskilayici...
  };
  const FOV = 420;
  const TUR_RENGI = {fikir: "#dcaa65", dosya: "#91a9e8", kural: "#c4a0d9", soru: "#79b9a0",
                     cikti: "#7fd18c", not: "#b9b2a6"};
  const TUR_ADI = {fikir: "Fikir", dosya: "Dosya", kural: "Kural", soru: "Soru", cikti: "Çıktı", not: "Not"};
  /* Kapilar kullanicinin dilinde: "eşik 1.5" degil, "Bunların hepsi gelince".
     Sayisal ayar (esik, k, agirlik) yalnizca gerektiginde gorunur. */
  const PALET = ["#dcaa65", "#e08f8f", "#91a9e8", "#79b9a0", "#c4a0d9", "#7fd18c", "#e0c98f", "#9aa0a6"];
  const KAPI_ADI = {herhangi: "Herhangi biri gelince", hepsi: "Bunların hepsi gelince",
                    en_az: "En az şu kadarı gelince", hicbiri: "Hiçbiri gelmezse",
                    tam_bir: "Yalnızca biri gelince", esik: "Ağırlıklı toplam eşiği geçince"};

  function kap() { return document.getElementById("ag-gorunum"); }
  function api() { return window.pywebview && window.pywebview.api; }
  function dugum(kimlik) { return D.ag && D.ag.dugumler.find((x) => x.kimlik === kimlik); }

  async function yukle() {
    const a = api(); if (!a) return;
    const r = await a.ag_listesi();
    D.aglar = (r && r.aglar) || [];
    /* Acik agi da diskten TAZELE: ajan araclarla (ag_dugum_ekle) aga yazmis
       olabilir; alan yeniden acildiginda bellekteki eski hali gostermeyelim. */
    if (D.ag && D.aglar.some((x) => x.ad === D.ag.ad)) await agSec(D.ag.ad);
    else if (D.aglar.length) await agSec(D.aglar[0].ad);
    else D.ag = null;
  }

  async function agSec(ad) {
    const r = await api().ag_getir(ad);
    if (!r || !r.ok) { toast(r && r.hata, "kotu"); return; }
    D.ag = r.ag; D.secili = null; D.secililer.clear(); D.kutu = null;
    D.sonIyi = JSON.stringify(r.ag);        // reddedilen degisiklikte bu hale donulur
    D.kosu = null; D.metin = ""; D.vurgulu.clear();
    merkeziTazele();
    D.kaydirma = {x: 0, y: 0};
    durdur();
  }

  function ac() { D.acik = true; yukle().then(ciz); }
  function kapat() { D.acik = false; durdur(); }

  /* Kaydedilemez durumlar: motor fail-closed, yani tek bir eksik alan butun
     agin kaydini reddeder. Kaydetmeden once burada yakalayip kullaniciya
     SEBEBINI gosteriyoruz; art arda kirmizi bildirim yagmuru olmuyor. */
  function eksikler() {
    const d = (D.ag ? D.ag.dugumler : []).filter((x) => x.tur === "dosya" && !String(x.yol || "").trim());
    return d.length ? T("Dosya baloncuğu için bir yol gerekli: {liste}",
                        {liste: d.map((x) => x.baslik || x.kimlik).join(", ")}) : "";
  }

  /* Kaydetme: her küçük değişiklikte değil, 600 ms sessizlikten sonra. */
  function kaydet() {
    if (!D.ag) return;
    /* Engel dogdugunda VE kalktiginda yeniden ciz: yoksa "yol gerekli" uyarisi
       yol girildikten sonra da ekranda kalirdi (kaydet() tek basina cizmez). */
    const engel = eksikler();
    if (engel !== D._sonEksik) { D._sonEksik = engel; ciz(); }
    if (engel) return;
    clearTimeout(D._kaydet);
    D._kaydet = setTimeout(() => {
      api().ag_kaydet(D.ag).then((r) => {
        if (r && !r.ok) {
          /* Motorun kurallarinin tamami burada tekrarlanmaz; reddedilen
             degisiklikten SON IYI hale donuyoruz ki ag kaydedilemez
             durumda kalmasin. */
          toast(r.hata, "kotu");
          if (D.sonIyi) {
            D.ag = JSON.parse(D.sonIyi);
            D.secili = null; D.secililer.clear(); D.baglaniyor = null;
            merkeziTazele(); ciz();
          }
          return;
        }
        D.sonIyi = JSON.stringify(D.ag);
        const yeni = ((r && r.uyarilar) || []).join("\n");
        if (yeni && yeni !== D.sonUyari) { D.sonUyari = yeni; toast((r.uyarilar || [])[0], "kotu"); }
        if (!yeni) D.sonUyari = "";
        D.uyarilar = (r && r.uyarilar) || [];
      });
    }, 600);
  }

  /* ---------------- 3B: döndürme ve izdüşüm ---------------- */

  /* Kumenin agirlik merkezi: donme ve yakinlasma bunun etrafinda olur. */
  /* Donme/yakinlasma ekseni: dugumlerin agirlik merkezi. Ag yuklenince ve
     "Yerlestir"den sonra BIR KEZ hesaplanir, sonra sabit kalir. Her karede
     yeniden hesaplansaydi tek bir dugumu tasimak butun sahneyi kaydirirdi
     (tek dugumlu agda dugum birakildigi anda merkeze geri ziplardi). */
  function merkeziTazele() {
    const ds = (D.ag && D.ag.dugumler) || [];
    if (!ds.length) { D.merkez = [0, 0, 0]; return; }
    const t = [0, 0, 0];
    ds.forEach((d) => { t[0] += d.konum[0]; t[1] += d.konum[1]; t[2] += d.konum[2]; });
    D.merkez = [t[0] / ds.length, t[1] / ds.length, t[2] / ds.length];
  }

  function salinim(kimlik) {
    if (!D.nefes) return [0, 0, 0];
    let h = 0;
    for (const c of String(kimlik)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    const f = D.zaman + (h % 628) / 100;
    return [Math.sin(f * 0.7) * 3.2, Math.cos(f * 0.53) * 3.2, Math.sin(f * 0.41) * 3.2];
  }

  function izdusum(konum, genislik, yukseklik, kimlik, mrk) {
    const sal = kimlik ? salinim(kimlik) : [0, 0, 0];
    const m = mrk || D.merkez || [0, 0, 0];
    const x0 = konum[0] + sal[0] - m[0], y0 = konum[1] + sal[1] - m[1], z0 = konum[2] + sal[2] - m[2];
    const cy = Math.cos(D.donme.y), sy = Math.sin(D.donme.y);
    const cx = Math.cos(D.donme.x), sx = Math.sin(D.donme.x);
    const x1 = x0 * cy + z0 * sy, z1 = -x0 * sy + z0 * cy;      // Y ekseni
    const y1 = y0 * cx - z1 * sx, z2 = y0 * sx + z1 * cx;        // X ekseni
    const k = FOV / (FOV + z2 + 120);
    return {x: genislik / 2 + D.kaydirma.x + x1 * k * D.olcek,
            y: yukseklik / 2 + D.kaydirma.y + y1 * k * D.olcek, k, z: z2};
  }

  function tuvalCiz() {
    const tuval = document.getElementById("ag-tuval");
    if (!tuval || !D.acik) return;
    const oran = window.devicePixelRatio || 1;
    const g = tuval.clientWidth, y = tuval.clientHeight;
    if (tuval.width !== Math.floor(g * oran)) { tuval.width = Math.floor(g * oran); tuval.height = Math.floor(y * oran); }
    const c = tuval.getContext("2d");
    c.setTransform(oran, 0, 0, oran, 0, 0);
    c.clearRect(0, 0, g, y);
    if (!D.ag) return;

    const nokta = {};
    D.ag.dugumler.forEach((d) => { nokta[d.kimlik] = izdusum(d.konum, g, y, d.kimlik, D.merkez); });
    const zaman = D.animasyon ? D.animasyon.tik : null;

    /* Bağlantılar (önce: baloncukların arkasında kalsınlar) */
    D.ag.baglantilar.forEach((b) => {
      const a = nokta[b.kaynak], h = nokta[b.hedef];
      if (!a || !h) return;
      const derinlik = Math.max(0.25, Math.min(1, (a.k + h.k) / 2));
      const baskilayici = b.agirlik < 0;
      c.save();
      c.globalAlpha = 0.18 + derinlik * 0.5;
      c.strokeStyle = baskilayici ? "#e08f8f" : "#7d7266";
      c.lineWidth = Math.max(0.6, Math.abs(b.agirlik) * derinlik * 1.4);
      if (baskilayici) c.setLineDash([4, 3]);
      c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(h.x, h.y); c.stroke();
      c.restore();
      /* ok ucu */
      const acisi = Math.atan2(h.y - a.y, h.x - a.x);
      const ur = 12 * derinlik;
      c.save(); c.globalAlpha = 0.3 + derinlik * 0.4; c.fillStyle = baskilayici ? "#e08f8f" : "#7d7266";
      c.translate(h.x - Math.cos(acisi) * 16 * derinlik, h.y - Math.sin(acisi) * 16 * derinlik);
      c.rotate(acisi); c.beginPath(); c.moveTo(0, 0); c.lineTo(-ur, ur * 0.4); c.lineTo(-ur, -ur * 0.4);
      c.closePath(); c.fill(); c.restore();
      /* aksiyon potansiyeli: aksonda ilerleyen ışık */
      if (zaman !== null) {
        const kt = D.animasyon.atesleyen[b.kaynak];
        if (kt !== undefined) {
          const varis = kt + b.gecikme;
          if (zaman >= kt && zaman <= varis + 0.15) {
            const o = Math.max(0, Math.min(1, (zaman - kt) / Math.max(0.001, b.gecikme)));
            const px = a.x + (h.x - a.x) * o, py = a.y + (h.y - a.y) * o;
            c.save();
            c.globalAlpha = 0.9;
            c.fillStyle = baskilayici ? "#e08f8f" : "#f0c07a";
            c.shadowBlur = 14; c.shadowColor = c.fillStyle;
            c.beginPath(); c.arc(px, py, 3.6 * derinlik + 1.6, 0, 6.2832); c.fill();
            c.restore();
          }
        }
      }
    });

    /* Baglama kipinde kaynaktan imlece giden ipucu cizgisi */
    if (D.baglaniyor && nokta[D.baglaniyor] && D._imlec) {
      const a = nokta[D.baglaniyor];
      c.save(); c.strokeStyle = "#79b9a0"; c.lineWidth = 1.5; c.setLineDash([5, 4]);
      c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(D._imlec[0], D._imlec[1]); c.stroke(); c.restore();
    }

    /* Baloncuklar: uzaktan yakına */
    const sirali = D.ag.dugumler.slice().sort((a, b) => nokta[b.kimlik].z - nokta[a.kimlik].z);
    sirali.forEach((d) => {
      const p = nokta[d.kimlik];
      const r = Math.max(8, 27 * p.k * D.olcek);
      const renk = d.renk || TUR_RENGI[d.tur] || "#dcaa65";
      const atesTik = D.animasyon ? D.animasyon.atesleyen[d.kimlik] : undefined;
      const yandi = atesTik !== undefined && zaman >= atesTik;
      const taze = yandi && zaman - atesTik < 1.2;
      const engel = D.animasyon && D.animasyon.engellenen.has(d.kimlik) && zaman > 0.3;

      c.save();
      /* Atesleme oynarken henuz yanmamis dugum belirgin sekilde sonuk: ekrandaki
         karsitlik, modele giden baglamdaki "sessiz kaldi" ile ayni sey. */
      c.globalAlpha = (0.35 + p.k * 0.65) * (D.animasyon && !yandi ? 0.32 : 1);
      if (taze || D.vurgulu.has(d.kimlik)) { c.shadowBlur = 26; c.shadowColor = renk; }
      const gr = c.createRadialGradient(p.x - r * 0.35, p.y - r * 0.4, r * 0.15, p.x, p.y, r);
      gr.addColorStop(0, yandi || !D.animasyon ? "#ffffff" : "#6b6157");
      gr.addColorStop(0.35, renk);
      gr.addColorStop(1, D.animasyon && !yandi ? "#2a2520" : "#3a332b");
      c.fillStyle = gr;
      c.beginPath(); c.arc(p.x, p.y, r, 0, 6.2832); c.fill();
      c.restore();

      if (d.kaynak === "ajan") {                    /* ajanın yazdığı: kesik gri halka */
        c.save(); c.globalAlpha = 0.5 + p.k * 0.4; c.strokeStyle = "#b9b2a6";
        c.lineWidth = 1.5; c.setLineDash([3, 3]);
        c.beginPath(); c.arc(p.x, p.y, r + 3, 0, 6.2832); c.stroke(); c.restore();
      }
      if (engel) {                                  /* kapı reddetti: kırmızı halka */
        c.save(); c.strokeStyle = "#e08f8f"; c.lineWidth = 2; c.setLineDash([3, 3]);
        c.beginPath(); c.arc(p.x, p.y, r + 4, 0, 6.2832); c.stroke(); c.restore();
      }
      if (D.secili === d.kimlik || D.baglaniyor === d.kimlik || D.secililer.has(d.kimlik)) {
        c.save();
        c.strokeStyle = D.baglaniyor === d.kimlik ? "#79b9a0"
          : (D.secililer.has(d.kimlik) && D.secili !== d.kimlik ? "#91a9e8" : "#f0c07a");
        c.lineWidth = 2; c.beginPath(); c.arc(p.x, p.y, r + 6, 0, 6.2832); c.stroke(); c.restore();
      }
      if (p.k > 0.55 || D.secili === d.kimlik) {
        c.save();
        c.globalAlpha = Math.min(1, 0.4 + p.k * 0.7);
        c.fillStyle = "#e9e2d8";
        c.font = `${Math.max(10, Math.round(12 * p.k * D.olcek))}px ui-sans-serif, system-ui, sans-serif`;
        c.textAlign = "center";
        c.fillText(kisalt(d.baslik || d.kimlik, 26), p.x, p.y + r + 13);
        c.restore();
      }
    });
    /* Alan secim kutusu */
    if (D.kutu) {
      const [x0, y0, x1, y1] = D.kutu;
      c.save();
      c.fillStyle = "rgba(145,169,232,0.12)"; c.strokeStyle = "#91a9e8";
      c.lineWidth = 1; c.setLineDash([4, 3]);
      c.fillRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
      c.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
      c.restore();
    }
    D._nokta = nokta;
  }

  function dongu() {
    if (!D.acik) return;
    D.nefes = !document.body.classList.contains("animasyon-az");
    D.zaman += 0.016;
    if (D.animasyon) {
      D.animasyon.tik += 0.06;
      if (D.animasyon.tik > D.animasyon.son + 1.6) {
        D.animasyon.tik = D.animasyon.son + 1.6;
        if (!D.animasyon.bitti) { D.animasyon.bitti = true; durumTazele(); }
      }
    }
    tuvalCiz();
    D._kare = requestAnimationFrame(dongu);
  }

  function durumTazele() {
    const d = document.querySelector(".ag-durum");
    if (!d || !D.animasyon) return;
    bosalt(d);
    d.appendChild(ikon(D.animasyon.bitti ? "tamam" : "kivilcim", 15));
    d.appendChild(el("span", "", D.animasyon.bitti
      ? T("{n} düğüm ateşledi, {m} sessiz", {n: D.animasyon.sayi, m: D.animasyon.sessiz})
      : T("Ateşleniyor…")));
  }

  function durdur() { if (D._kare) cancelAnimationFrame(D._kare); D._kare = null; D.animasyon = null; }

  /* ---------------- Alan ---------------- */

  /* Iskelet BIR KEZ kurulur. Tuvali her cizimde yeniden yaratmak, suruklemeyi
     daha basvurmadan oldururdu: pointerdown -> ciz() -> YENI tuval -> sonraki
     pointermove eski (kopmus) tuvale giderdi. Tuval ve olaylari sabit kalir,
     ciz() yalnizca panelleri tazeler. */
  function iskelet() {
    const k = kap(); if (!k) return null;
    let dis = k.querySelector(".ag-dis");
    if (dis) return dis;
    bosalt(k);
    dis = el("div", "ag-dis");
    dis.appendChild(el("aside", "ag-yan"));
    const orta = el("div", "ag-orta");
    orta.appendChild(el("div", "ag-araclar"));
    const sarmal = el("div", "ag-tuval-sarmal");
    const tuval = el("canvas"); tuval.id = "ag-tuval";
    sarmal.appendChild(tuval);
    sarmal.appendChild(el("div", "ag-bos"));
    orta.appendChild(sarmal);
    dis.appendChild(orta);
    dis.appendChild(el("aside", "ag-sag"));
    k.appendChild(dis);
    tuvalOlaylari(tuval);
    return dis;
  }

  function ciz() {
    const dis = iskelet(); if (!dis) return;
    const temizle = (secici) => { const d = dis.querySelector(secici); bosalt(d); return d; };
    yanPanel(temizle(".ag-yan"));
    araclar(temizle(".ag-araclar"));
    sagPanel(temizle(".ag-sag"));
    const bos = temizle(".ag-bos");
    bos.style.display = D.ag ? "none" : "";
    if (!D.ag) {
      bos.appendChild(ikon("ag", 40));
      bos.appendChild(el("div", "", T("Henüz ağ yok. Soldaki panelden yeni bir ağ oluştur.")));
      bos.appendChild(el("p", "ag-sonuk", T("Düşünce ağı, göreve hangi not ve kuralların hangi sırayla ekleneceğini belirler. Örneğin araştırma için kaynak, kontrol ve özet adımlarını bağlayabilirsin.")));
    }
    if (!D._kare) dongu();
  }

  function yanPanel(y) {
    y.appendChild(ikonlu(el("h3"), "ag", T("Ağlar"), 15));
    const liste = el("div", "ag-liste");
    if (!D.aglar.length) liste.appendChild(el("div", "ag-sonuk", T("Henüz ağ yok.")));
    D.aglar.forEach((a) => {
      const b = el("button", "ag-oge" + (D.ag && D.ag.ad === a.ad ? " aktif" : ""));
      b.appendChild(ikon("baloncuk", 14));
      const ic = el("div", "");
      ic.appendChild(el("strong", "", a.ad));
      const alt = el("div", "ag-sonuk");
      alt.appendChild(el("span", "", T("{d} düğüm · {b} bağlantı", {d: a.dugum, b: a.baglanti})));
      if (a.ajan) alt.appendChild(el("span", "ag-rozet", T("ajan")));
      ic.appendChild(alt);
      b.appendChild(ic);
      b.addEventListener("click", () => agSec(a.ad).then(ciz));
      liste.appendChild(b);
    });
    y.appendChild(liste);
    if (D.ag) {
      /* Ag duzeyindeki alanlar. Tetik talimata girdigi icin burada: "bu ag ne
         zaman atesLENMELI" sorusu agin kendi ozelligi, bir dugumunki degil. */
      const b = el("div", "ag-bolum");
      const l1 = el("label", ""); l1.appendChild(ikon("kivilcim", 12));
      l1.appendChild(el("span", "", T("Ne zaman ateşlensin?")));
      b.appendChild(l1);
      const tetik = el("textarea"); tetik.rows = 2;
      tetik.placeholder = T("ör. haftalık rapor istendiğinde");
      tetik.value = D.ag.tetik || "";
      tetik.addEventListener("input", () => { D.ag.tetik = tetik.value; kaydet(); });
      b.appendChild(tetik);
      b.appendChild(el("div", "ag-sonuk", T("Ajan, bu tanıma uyan görevlerde ağı kendisi ateşler.")));
      const l2 = el("label", ""); l2.appendChild(ikon("bilgi", 12));
      l2.appendChild(el("span", "", T("Ne işe yarar? (isteğe bağlı)")));
      b.appendChild(l2);
      const acik = el("input");
      acik.value = D.ag.aciklama || "";
      acik.addEventListener("input", () => { D.ag.aciklama = acik.value; kaydet(); });
      b.appendChild(acik);
      y.appendChild(b);
    }
    const yeni = el("div", "ag-yeni");
    const ad = el("input"); ad.placeholder = T("Yeni ağın adı"); ad.spellcheck = false;
    const ekle = ikonlu(el("button", "birincil ag-dugme"), "yeni", T("Ağ oluştur"), 15);
    const olustur = () => {
      const isim = ad.value.trim(); if (!isim) { toast(T("Ağ adı gerekli"), "kotu"); return; }
      api().ag_kaydet({ad: isim, dugumler: [], baglantilar: []}).then((r) => {
        if (r && !r.ok) { toast(r.hata, "kotu"); return; }
        ad.value = ""; yukle().then(() => agSec(isim)).then(ciz);
      });
    };
    ekle.addEventListener("click", olustur);
    ad.addEventListener("keydown", (e) => { if (e.key === "Enter") olustur(); });
    yeni.appendChild(ad); yeni.appendChild(ekle);
    y.appendChild(yeni);
    if (D.ag) {
      const sil = ikonlu(el("button", "ikincil tehlike ag-dugme"), "cop", T("Bu ağı sil"), 14);
      sil.addEventListener("click", () => api().ag_sil(D.ag.ad).then((r) => {
        if (r && !r.ok) { toast(r.hata, "kotu"); return; }
        D.ag = null; yukle().then(ciz);
      }));
      y.appendChild(sil);
    }
  }

  function ikonlu(dugum, im, metin, boyut) {
    dugum.appendChild(ikon(im, boyut || 15)); dugum.appendChild(el("span", "", metin)); return dugum;
  }

  function araclar(c) {
    const dugmeler = [
      ["kivilcim", "Ateşle", () => atesle(), "birincil"],
      ["baloncuk", "Baloncuk ekle", () => dugumEkle(), "ikincil"],
      ["ag", "Bağla", () => { D.baglaniyor = D.baglaniyor ? null : (D.secili || null);
                              if (!D.secili && !D.baglaniyor) toast(T("Önce kaynağı seç."), "kotu"); ciz(); }, "ikincil"],
      ["secim", "Seç", () => { D.secKipi = !D.secKipi; if (!D.secKipi) D.kutu = null; ciz(); }, "ikincil"],
      ["hedef", "Yerleştir", () => yerlestir(), "ikincil"],
    ];
    dugmeler.forEach(([im, ad, tikla, sinif]) => {
      const acik = (ad === "Bağla" && D.baglaniyor) || (ad === "Seç" && D.secKipi);
      const b = ikonlu(el("button", sinif + " ag-dugme" + (acik ? " acik" : "")), im, T(ad), 15);
      b.disabled = !D.ag && ad !== "Ateşle";
      b.addEventListener("click", tikla);
      c.appendChild(b);
    });
    const bosluk = el("div", "ag-bosluk"); c.appendChild(bosluk);
    /* Kaydetmeyi engelleyen durum HER ZAMAN gorunsun: kullanici baska bir
       baloncuk secmisken de "neden kaydedilmiyor" sorusu ortada kalmasin. */
    const engel = eksikler();
    if (engel) {
      const u = el("div", "ag-durum eksik");
      u.appendChild(ikon("uyari", 15)); u.appendChild(el("span", "", engel));
      c.appendChild(u);
    } else if (D.animasyon) {
      const d = el("div", "ag-durum");
      d.appendChild(ikon(D.animasyon.bitti ? "tamam" : "kivilcim", 15));
      d.appendChild(el("span", "", D.animasyon.bitti
        ? T("{n} düğüm ateşledi, {m} sessiz", {n: D.animasyon.sayi, m: D.animasyon.sessiz})
        : T("Ateşleniyor…")));
      c.appendChild(d);
    }
  }

  function sagPanel(s) {
    const sekmeler = el("div", "ag-sekmeler");
    [["denetci", "Baloncuk"], ["okuma", "Okuma"]].forEach(([kod, ad]) => {
      const b = el("button", "ag-sekme" + (D.sekme === kod ? " aktif" : ""), T(ad));
      b.addEventListener("click", () => { D.sekme = kod; ciz(); });
      sekmeler.appendChild(b);
    });
    s.appendChild(sekmeler);
    const ic = el("div", "ag-sag-ic");
    (D.sekme === "okuma" ? okumaPaneli : denetciPaneli)(ic);
    s.appendChild(ic);
  }

  function satir(ic, etiket, im, girdi) {
    const s = el("div", "ag-satir");
    const l = el("label", ""); l.appendChild(ikon(im, 13)); l.appendChild(el("span", "", T(etiket)));
    s.appendChild(l); s.appendChild(girdi); ic.appendChild(s); return girdi;
  }

  function topluPanel(ic) {
    const secili = Array.from(D.secililer).filter(dugum);
    ic.appendChild(ikonlu(el("h4"), "secim", T("{n} baloncuk seçili", {n: secili.length}), 13));
    ic.appendChild(ikonlu(el("div", "ag-not"), "bilgi",
      T("Renk ve tür tüm seçime uygulanır. Silme bağlantıları da kaldırır; önceki sürüm geçmişte saklanır."), 13));

    const rs = el("div", "ag-satir");
    const rl = el("label", ""); rl.appendChild(ikon("gorsel", 13)); rl.appendChild(el("span", "", T("Renk")));
    rs.appendChild(rl);
    const palet = el("div", "ag-palet");
    const hepsineRenk = (v) => { secili.forEach((k) => { dugum(k).renk = v; }); kaydet(); ciz(); };
    const varsayilan = el("button", "ag-renk"); varsayilan.style.background = "var(--yuzey-2)";
    varsayilan.title = T("Türün rengi");
    varsayilan.addEventListener("click", () => hepsineRenk(""));
    palet.appendChild(varsayilan);
    PALET.forEach((v) => {
      const b = el("button", "ag-renk"); b.style.background = v; b.title = v;
      b.addEventListener("click", () => hepsineRenk(v));
      palet.appendChild(b);
    });
    rs.appendChild(palet); ic.appendChild(rs);

    const tur = satir(ic, "Tür", "baloncuk", el("select"));
    const o0 = el("option", "", T("(değiştirme)")); o0.value = ""; tur.appendChild(o0);
    /* Toplu islemde 'dosya' yok: her baloncuga ayri bir yol gerekirdi. */
    Object.keys(TUR_ADI).filter((k) => k !== "dosya").forEach((k) => {
      const o = el("option", "", T(TUR_ADI[k])); o.value = k; tur.appendChild(o);
    });
    tur.addEventListener("change", () => {
      if (!tur.value) return;
      secili.forEach((k) => { const d = dugum(k); if (d.tur !== "dosya" && tur.value !== "dosya") d.tur = tur.value; });
      kaydet(); ciz();
    });

    const ajanlar = secili.filter((k) => dugum(k).kaynak === "ajan");
    if (ajanlar.length) {
      const bn = ikonlu(el("button", "ikincil ag-dugme"), "onay",
                        T("Ajan notlarını benimse ({n})", {n: ajanlar.length}), 14);
      bn.addEventListener("click", () => {
        ajanlar.forEach((k) => { dugum(k).kaynak = "kullanici"; });
        kaydet(); ciz();
      });
      ic.appendChild(bn);
    }

    const ates = ikonlu(el("button", "ikincil ag-dugme"), "kivilcim", T("Seçilenlerden ateşle"), 14);
    ates.addEventListener("click", () => atesle(secili));
    ic.appendChild(ates);

    /* Silme iki adimli: cok dugumu tek tikla kaybetmek kolay olmasin. */
    const sil = ikonlu(el("button", "ikincil tehlike ag-dugme"), "cop",
                       D.silOnay ? T("Emin misin? ({n})", {n: secili.length})
                                 : T("Seçilenleri sil ({n})", {n: secili.length}), 14);
    sil.addEventListener("click", () => {
      if (!D.silOnay) {
        D.silOnay = true; ciz();
        clearTimeout(D._silZaman);
        D._silZaman = setTimeout(() => { if (D.silOnay) { D.silOnay = false; ciz(); } }, 4000);
        return;
      }
      D.silOnay = false;
      const kume = new Set(secili);
      D.ag.dugumler = D.ag.dugumler.filter((x) => !kume.has(x.kimlik));
      D.ag.baglantilar = D.ag.baglantilar.filter((b) => !kume.has(b.kaynak) && !kume.has(b.hedef));
      D.secililer.clear(); D.secili = null;
      merkeziTazele(); kaydet(); ciz();
      toast(T("{n} baloncuk silindi.", {n: kume.size}), "iyi");
    });
    ic.appendChild(sil);

    const birak = ikonlu(el("button", "ikincil ag-dugme"), "ret", T("Seçimi bırak"), 14);
    birak.addEventListener("click", () => { D.secililer.clear(); D.secili = null; D.silOnay = false; ciz(); });
    ic.appendChild(birak);
  }

  function denetciPaneli(ic) {
    if (D.secililer.size > 1) { topluPanel(ic); return; }
    const d = D.secili && dugum(D.secili);
    if (!d) {
      ic.appendChild(el("div", "ag-sonuk", T("Düzenlemek için bir baloncuk seç. Baloncuğu sürükleyerek taşı, boş "
                                             + "alanı sürükleyerek ağı döndür.")));
      ic.appendChild(ikonlu(el("div", "ag-not"), "secim",
        T("Alan seçimi: Ctrl + sürükle, boş alanda basılı tut ya da Seç düğmesini kullan."), 13));
      return;
    }
    const bas = el("div", "ag-uye-bas");
    const n = el("span", "ag-nokta"); n.style.background = d.renk || TUR_RENGI[d.tur] || "#dcaa65";
    bas.appendChild(n);
    bas.appendChild(el("strong", "", d.kimlik));
    const sil = el("button", "ag-sil"); sil.title = T("Baloncuğu sil"); sil.appendChild(ikon("ret", 14));
    sil.addEventListener("click", () => {
      D.ag.dugumler = D.ag.dugumler.filter((x) => x.kimlik !== d.kimlik);
      D.ag.baglantilar = D.ag.baglantilar.filter((b) => b.kaynak !== d.kimlik && b.hedef !== d.kimlik);
      D.secili = null; merkeziTazele(); kaydet(); ciz();
    });
    bas.appendChild(sil); ic.appendChild(bas);
    if (d.kaynak === "ajan") {
      ic.appendChild(ikonlu(el("div", "ag-not"), "bot",
        T("Ajan tarafından eklendi; okumalarda güvenilmeyen içerik olarak işaretlenir. İnceledikten sonra "
          + "benimseyebilirsin."), 13));
      const bn = ikonlu(el("button", "ikincil ag-dugme"), "onay", T("Benimse"), 14);
      bn.addEventListener("click", () => { d.kaynak = "kullanici"; kaydet(); ciz(); });
      ic.appendChild(bn);
    }

    const baslik = satir(ic, "Başlık", "kalem", el("input"));
    baslik.value = d.baslik || "";
    baslik.addEventListener("input", () => { d.baslik = baslik.value; kaydet(); });

    const tur = satir(ic, "Tür", "baloncuk", el("select"));
    Object.keys(TUR_ADI).forEach((k) => {
      const o = el("option", "", T(TUR_ADI[k])); o.value = k; if (d.tur === k) o.selected = true; tur.appendChild(o);
    });
    tur.addEventListener("change", () => {
      d.tur = tur.value;
      if (d.tur !== "dosya") d.yol = "";     /* yol yalnizca dosya dugumunde olur */
      kaydet(); ciz();
      const g = document.querySelector(".ag-sag-ic .ag-satir input");
      if (d.tur === "dosya" && g) g.focus();
    });

    if (d.tur === "dosya") {
      const yol = satir(ic, "Dosya", "dosya", el("input"));
      yol.value = d.yol || ""; yol.placeholder = T("Tam yol");
      yol.addEventListener("input", () => { d.yol = yol.value; kaydet(); });
      if (!String(d.yol || "").trim()) {
        ic.appendChild(ikonlu(el("div", "ag-not eksik"), "uyari",
          T("Yol boşken ağ kaydedilemez."), 13));
      }
      ic.appendChild(ikonlu(el("div", "ag-not"), "kalkan", T("Dosya baloncukları okuma iznine tabidir; izin yoksa "
                                                             + "ateşlemez."), 13));
    } else {
      const metin = satir(ic, "İçerik", "kalem", el("textarea"));
      metin.rows = 6; metin.value = d.metin || "";
      metin.addEventListener("input", () => { d.metin = metin.value; kaydet(); });
      if (String(d.metin || "").includes("{gorev}")) {
        ic.appendChild(ikonlu(el("div", "ag-not"), "bilgi",
          T("{gorev}: ateşleme anındaki istekle değiştirilir."), 13));
      }
    }

    /* Renk: turun rengi varsayilan; kullanici isterse kendi rengini secer.
       Paletten tek tikla, ya da tam sectigi renkle. */
    const rs = el("div", "ag-satir");
    const rl = el("label", ""); rl.appendChild(ikon("gorsel", 13)); rl.appendChild(el("span", "", T("Renk")));
    rs.appendChild(rl);
    const palet = el("div", "ag-palet");
    const renkAyarla = (v) => { d.renk = v; kaydet(); ciz(); };
    const varsayilan = el("button", "ag-renk" + (d.renk ? "" : " secili"));
    varsayilan.style.background = TUR_RENGI[d.tur] || "#dcaa65";
    varsayilan.title = T("Türün rengi");
    varsayilan.addEventListener("click", () => renkAyarla(""));
    palet.appendChild(varsayilan);
    PALET.forEach((v) => {
      const b = el("button", "ag-renk" + (d.renk === v ? " secili" : ""));
      b.style.background = v; b.title = v;
      b.addEventListener("click", () => renkAyarla(v));
      palet.appendChild(b);
    });
    const secici = el("input", "ag-renk-secici"); secici.type = "color";
    secici.value = d.renk || TUR_RENGI[d.tur] || "#dcaa65"; secici.title = T("Kendi rengin");
    secici.addEventListener("change", () => renkAyarla(secici.value.toLowerCase()));
    palet.appendChild(secici);
    rs.appendChild(palet); ic.appendChild(rs);

    const kapi = satir(ic, "Kapı", "ag", el("select"));
    Object.keys(KAPI_ADI).forEach((k) => {
      const o = el("option", "", T(KAPI_ADI[k])); o.value = k; if (d.kapi === k) o.selected = true; kapi.appendChild(o);
    });
    kapi.addEventListener("change", () => {
      d.kapi = kapi.value;
      /* Sema kati: esik yalnizca 'esik' kapisinda, k yalnizca 'en_az'da olur.
         Kapi degisince eski alanlari birakmak kaydi reddettirirdi. */
      d.esik = d.kapi === "esik" ? (d.esik === null || d.esik === undefined ? 1 : d.esik) : null;
      d.k = d.kapi === "en_az" ? (d.k || 2) : null;
      if (d.kapi !== "esik") d.yanlilik = 0;
      kaydet(); ciz();
    });

    if (d.kapi === "esik") {
      const esik = satir(ic, "Eşik", "hedef", el("input"));
      esik.type = "number"; esik.step = "0.1"; esik.value = d.esik === null || d.esik === undefined ? 1 : d.esik;
      esik.addEventListener("input", () => { d.esik = esik.value.trim() === "" ? 1 : Number(esik.value); kaydet(); });
      ic.appendChild(ikonlu(el("div", "ag-not"), "bilgi",
        T("Gelen ağırlıklar toplanır; toplam eşiği geçerse ateşler."), 13));
    }
    if (d.kapi === "en_az") {
      const kg = satir(ic, "Kaç girdi", "hedef", el("input"));
      kg.type = "number"; kg.min = "1"; kg.step = "1"; kg.value = d.k || 2;
      kg.addEventListener("input", () => { d.k = Math.max(1, Number(kg.value) || 1); kaydet(); });
    }

    const gelen = D.ag.baglantilar.filter((b) => b.hedef === d.kimlik);
    const giden = D.ag.baglantilar.filter((b) => b.kaynak === d.kimlik);
    if (gelen.length || giden.length) ic.appendChild(ikonlu(el("h4"), "ag", T("Bağlantılar"), 13));
    gelen.concat(giden).forEach((b) => {
      const s = el("div", "ag-baglanti");
      const gelenMi = b.hedef === d.kimlik;
      s.appendChild(ikon(gelenMi ? "solok" : "sagok", 12));   /* yon apacik: gelen mi giden mi */
      s.appendChild(el("span", "", gelenMi ? b.kaynak + " → " : " → " + b.hedef));
      const engelle = el("button", "ag-mini" + (b.agirlik < 0 ? " engel" : ""));
      engelle.textContent = b.agirlik < 0 ? T("engeller") : T("uyarır");
      engelle.title = T("Engelleyici bağlantı hedefi VETO eder.");
      engelle.addEventListener("click", () => { b.agirlik = -b.agirlik; kaydet(); ciz(); });
      const a = el("input", "ag-mini"); a.type = "number"; a.step = "0.1"; a.value = Math.abs(b.agirlik);
      a.title = T("Ağırlık (yalnızca eşik kapısında anlamlı)");
      a.addEventListener("input", () => {
        const v = Math.abs(Number(a.value) || 1); b.agirlik = b.agirlik < 0 ? -v : v; kaydet();
      });
      s.appendChild(engelle);
      const g = el("input", "ag-mini"); g.type = "number"; g.min = "1"; g.max = "20"; g.value = b.gecikme; g.title = T("Gecikme (tik)");
      g.addEventListener("input", () => { b.gecikme = Math.max(1, Math.min(20, Number(g.value) || 1)); kaydet(); });
      s.appendChild(a); s.appendChild(g);
      const sb = el("button", "ag-sil"); sb.title = T("Bağlantıyı sil"); sb.appendChild(ikon("ret", 13));
      sb.addEventListener("click", () => {
        D.ag.baglantilar = D.ag.baglantilar.filter((x) => x !== b); kaydet(); ciz();
      });
      s.appendChild(sb);
      ic.appendChild(s);
    });

    (D.uyarilar || []).filter((u) => u.includes("'" + d.kimlik + "'")).forEach((u) => {
      ic.appendChild(ikonlu(el("div", "ag-not eksik"), "uyari", u, 13));
    });
    const uyar = ikonlu(el("button", "ikincil ag-dugme"), "kivilcim", T("Buradan ateşle"), 14);
    uyar.addEventListener("click", () => atesle([d.kimlik]));
    ic.appendChild(uyar);
  }

  function okumaPaneli(ic) {
    if (!D.metin) {
      ic.appendChild(el("div", "ag-sonuk", T("Ateşlendiğinde düğümler ağın mantığına göre sırayla okunur. Sonuç "
                                             + "buradan bir göreve gönderilebilir.")));
      return;
    }
    if (D.kosu) {
      const ozet = el("div", "ag-ozet");
      ozet.appendChild(ikonlu(el("span", "ag-meta"), "tamam", T("{n} ateşledi", {n: D.kosu.sira.length}), 13));
      ozet.appendChild(ikonlu(el("span", "ag-meta"), "saat", T("{n} sessiz", {n: D.kosu.sessiz.length}), 13));
      if (D.kosu.engellenen.length) {
        ozet.appendChild(ikonlu(el("span", "ag-meta eksik"), "kalkan", T("{n} engellendi", {n: D.kosu.engellenen.length}), 13));
      }
      ic.appendChild(ozet);
      D.kosu.engellenen.forEach((e) => {
        ic.appendChild(ikonlu(el("div", "ag-not eksik"), "kalkan", (e.baslik || e.kimlik) + " — " + e.gerekce, 13));
      });
      (D.kosu.uyarilar || []).forEach((u) => {
        ic.appendChild(ikonlu(el("div", "ag-not eksik"), "uyari", u, 13));
      });
      const sira = el("div", "ag-sira");
      D.kosu.sira.forEach((a) => {
        const s = el("button", "ag-sira-oge");
        s.appendChild(el("span", "ag-sira-no", String(a.sira)));
        s.appendChild(el("span", "", a.baslik));
        s.appendChild(el("span", "ag-sonuk", T("tik {tik}", {tik: a.tik})));
        s.addEventListener("click", () => { D.secili = a.kimlik; D.sekme = "denetci"; ciz(); });
        sira.appendChild(s);
      });
      ic.appendChild(sira);
      if (D.kosu.sessiz.length) {
        ic.appendChild(ikonlu(el("h4"), "saat", T("Ateşlemeyenler"), 13));
        D.kosu.sessiz.forEach((x) => {
          const b = el("button", "ag-sira-oge sessiz");
          b.appendChild(el("span", "", x.baslik || x.kimlik));
          b.appendChild(el("span", "ag-sonuk", x.neden));
          b.addEventListener("click", () => { D.secili = x.kimlik; D.sekme = "denetci"; ciz(); });
          ic.appendChild(b);
        });
      }
    }
    const kutu = el("pre", "ag-metin", D.metin);
    ic.appendChild(kutu);
    const gonder = el("div", "ag-gonder");
    const g = el("input"); g.placeholder = T("Bu okumayla ne yapılsın?");
    const b = ikonlu(el("button", "birincil ag-dugme"), "yolla", T("Göreve gönder"), 15);
    const yolla = () => {
      const istek = g.value.trim(); if (!istek) { toast(T("Görev boş"), "kotu"); return; }
      const uyaran = (D.kosu && D.kosu.uyaran) || [];
      api().ag_gorev_baslat(D.ag.ad, uyaran, istek, "tam").then((r) => {
        if (r && !r.ok) { toast(r.hata, "kotu"); return; }
        g.value = "";
        toast(T("Görev başladı; sohbete geç."), "iyi");
      });
    };
    b.addEventListener("click", yolla);
    g.addEventListener("keydown", (e) => { if (e.key === "Enter") yolla(); });
    gonder.appendChild(g); gonder.appendChild(b);
    ic.appendChild(gonder);
  }

  /* ---------------- Eylemler ---------------- */

  function yeniKimlik() {
    let i = 1;
    while (dugum("n" + i)) i += 1;
    return "n" + i;
  }

  function dugumEkle() {
    if (!D.ag) { toast(T("Önce bir ağ oluştur."), "kotu"); return; }
    const kimlik = yeniKimlik();
    const n = D.ag.dugumler.length;
    D.ag.dugumler.push({kimlik, tur: "fikir", baslik: T("Yeni baloncuk"), metin: "", yol: "",
                        kapi: "veya", esik: null, yanlilik: 0, etiketler: [],
                        konum: [Math.cos(n) * 90, Math.sin(n * 1.7) * 70, Math.sin(n) * 80]});
    D.secili = kimlik; D.sekme = "denetci"; merkeziTazele(); kaydet(); ciz();
  }

  function bagla(kaynak, hedef) {
    /* Hangi sonucla biterse bitsin baglama kipi KAPANIR: acik kalirsa bir
       sonraki tik beklenmedik bir baglanti kurar. */
    D.baglaniyor = null;
    if (kaynak === hedef) { toast(T("Düğüm kendine bağlanamaz."), "kotu"); ciz(); return; }
    if (D.ag.baglantilar.some((b) => b.kaynak === kaynak && b.hedef === hedef)) {
      toast(T("Bu bağlantı zaten var."), "kotu"); ciz(); return;
    }
    D.ag.baglantilar.push({kaynak, hedef, agirlik: 1, gecikme: 1});
    kaydet(); ciz();
  }

  /* Kuvvet yerlesimi: bagli dugumler birbirini ceker, hepsi birbirini iter. */
  function yerlestir() {
    if (!D.ag || !D.ag.dugumler.length) return;
    const ds = D.ag.dugumler;
    for (let adim = 0; adim < 220; adim += 1) {
      const kuvvet = ds.map(() => [0, 0, 0]);
      for (let i = 0; i < ds.length; i += 1) {
        for (let j = i + 1; j < ds.length; j += 1) {
          const f = [0, 1, 2].map((k) => ds[i].konum[k] - ds[j].konum[k]);
          const uz = Math.max(18, Math.hypot(f[0], f[1], f[2]));
          const it = 5200 / (uz * uz);
          [0, 1, 2].forEach((k) => { kuvvet[i][k] += (f[k] / uz) * it; kuvvet[j][k] -= (f[k] / uz) * it; });
        }
      }
      D.ag.baglantilar.forEach((b) => {
        const i = ds.findIndex((x) => x.kimlik === b.kaynak), j = ds.findIndex((x) => x.kimlik === b.hedef);
        if (i < 0 || j < 0) return;
        const f = [0, 1, 2].map((k) => ds[j].konum[k] - ds[i].konum[k]);
        const uz = Math.max(1, Math.hypot(f[0], f[1], f[2]));
        const cek = (uz - 110) * 0.012;
        [0, 1, 2].forEach((k) => { kuvvet[i][k] += (f[k] / uz) * cek * uz; kuvvet[j][k] -= (f[k] / uz) * cek * uz; });
      });
      ds.forEach((d, i) => {
        [0, 1, 2].forEach((k) => {
          d.konum[k] = Math.max(-260, Math.min(260, d.konum[k] + Math.max(-6, Math.min(6, kuvvet[i][k] * 0.04))));
        });
      });
    }
    ds.forEach((d) => { d.konum = d.konum.map((v) => Math.round(v * 10) / 10); });
    merkeziTazele();
    kaydet();
  }

  function atesle(uyaran) {
    if (!D.ag) { toast(T("Önce bir ağ oluştur."), "kotu"); return; }
    const istek = (document.querySelector(".ag-gonder input") || {}).value || "";
    api().ag_atesle(D.ag.ad, uyaran || [], "tam", istek).then((r) => {
      if (!r || !r.ok) { toast(r && r.hata, "kotu"); return; }
      D.kosu = r.kosu; D.metin = r.metin; D.sekme = "okuma";
      const atesleyen = {};
      r.kosu.sira.forEach((a) => { atesleyen[a.kimlik] = a.tik; });
      D.animasyon = {tik: -0.4, atesleyen, son: r.kosu.sira.reduce((m, a) => Math.max(m, a.tik), 0),
                     engellenen: new Set(r.kosu.engellenen.map((e) => e.kimlik)),
                     sayi: r.kosu.sira.length, sessiz: r.kosu.sessiz.length, bitti: false};
      ciz();
    });
  }

  /* ---------------- Tuval olaylari ---------------- */

  function tuvalOlaylari(tuval) {
    let surukle = null;
    const yerelKonum = (e) => {
      const k = tuval.getBoundingClientRect();
      return {x: e.clientX - k.left, y: e.clientY - k.top};
    };
    const vurulan = (p) => {
      if (!D.ag || !D._nokta) return null;
      let en = null;
      D.ag.dugumler.forEach((d) => {
        const n = D._nokta[d.kimlik]; if (!n) return;
        const r = Math.max(8, 27 * n.k * D.olcek) + 4;
        const uz = Math.hypot(n.x - p.x, n.y - p.y);
        if (uz <= r && (!en || n.z < en.z)) en = {kimlik: d.kimlik, z: n.z};
      });
      return en && en.kimlik;
    };
    tuval.addEventListener("pointerdown", (e) => {
      /* Yalnizca birincil (sol) dugme surukler/secer. Sag tik kendi
         contextmenu isleyicisine aittir; ikisi birden calisirsa sag tikla
         baglama sonsuz zincire girer. */
      if (e.button !== 0) return;
      const p = yerelKonum(e);
      const k = vurulan(p);
      if (k && D.baglaniyor && D.baglaniyor !== k) { bagla(D.baglaniyor, k); return; }
      /* ONCE surukleme durumu, SONRA yakalama: setPointerCapture bazi kalem/
         dokunma ve WebView durumlarinda firlatiyor ve firlatinca asagisi hic
         calismiyordu — surukleme tamamen olurdu. Yakalama bir iyilestirme,
         sart degil. */
      if (k && (e.ctrlKey || e.metaKey || e.shiftKey)) {   /* Ctrl/Shift+tik: secime ekle/cikar */
        if (D.secililer.has(k)) D.secililer.delete(k); else D.secililer.add(k);
        D.secili = D.secililer.has(k) ? k : (D.secililer.size ? Array.from(D.secililer).pop() : null);
        D.silOnay = false; ciz();
        return;
      }
      /* DUZ tik = yalnizca bunu sec (bos alanda: secimi birak). Ctrl ile
         girilen secimden cikmak icin yine Ctrl'e basmak gerekmesin. */
      if (D.secililer.size) { D.secililer.clear(); D.silOnay = false; }
      if (k) D.secililer.add(k);
      if (!k && (e.ctrlKey || e.metaKey || D.secKipi)) {
        surukle = {tur: "kutu", p, bas: p};
        D.kutu = [p.x, p.y, p.x, p.y];
        return;
      }
      surukle = k ? {tur: "dugum", kimlik: k, p} : {tur: e.shiftKey ? "kaydir" : "dondur", p};
      if (!k) {
        /* "Bosluga basili tut" -> alan secimi. Hemen suruklersen donme olur:
           zamanlayici ilk kimildamada iptal edilir. */
        const baslangic = p;
        surukle.bekle = setTimeout(() => {
          if (surukle && surukle.tur === "dondur") {
            surukle = {tur: "kutu", p: baslangic, bas: baslangic};
            D.kutu = [baslangic.x, baslangic.y, baslangic.x, baslangic.y];
          }
        }, 250);
      }
      try { tuval.setPointerCapture(e.pointerId); } catch (hata) { /* yakalama yoksa da surukleriz */ }
      if (k) { D.secili = k; D.sekme = "denetci"; ciz(); }
      else { D.secili = null; D.secililer.clear(); ciz(); }
    });
    tuval.addEventListener("pointermove", (e) => {
      const yerel = yerelKonum(e);
      D._imlec = [yerel.x, yerel.y];            // baglama ipucu cizgisi icin
      if (!surukle) return;
      const p = yerel;
      const dx = p.x - surukle.p.x, dy = p.y - surukle.p.y;
      surukle.p = p;
      if (surukle.bekle && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
        clearTimeout(surukle.bekle); surukle.bekle = null;      // kimildadi: donme
      }
      if (surukle.tur === "kutu") {
        D.kutu = [surukle.bas.x, surukle.bas.y, p.x, p.y];
      } else if (surukle.tur === "dondur") {
        D.donme.y += dx * 0.006; D.donme.x = Math.max(-1.4, Math.min(1.4, D.donme.x + dy * 0.006));
      } else if (surukle.tur === "kaydir") {
        D.kaydirma.x += dx; D.kaydirma.y += dy;
      } else {
        const d = dugum(surukle.kimlik); if (!d) return;
        const n = D._nokta[surukle.kimlik];
        const k = Math.max(0.2, n ? n.k : 1) * D.olcek;
        /* Ekran düzlemindeki hareketi dünya eksenlerine geri çevir (ters döndürme). */
        const cy = Math.cos(D.donme.y), sy = Math.sin(D.donme.y);
        const cx = Math.cos(D.donme.x), sx = Math.sin(D.donme.x);
        const ex = dx / k, ey = dy / k;
        const x1 = ex, y1 = ey * cx, z1 = -ey * sx;
        d.konum[0] += x1 * cy - z1 * sy;
        d.konum[1] += y1;
        d.konum[2] += x1 * sy + z1 * cy;
        kaydet();
      }
    });
    const bitir = () => {
      if (surukle) {
        clearTimeout(surukle.bekle);
        if (surukle.tur === "kutu") kutuyuUygula(e_shift);
      }
      surukle = null;
    };
    let e_shift = false;   // birakirken Shift: secimi DEGISTIRME, EKLE
    tuval.addEventListener("pointerup", (e) => { e_shift = e.shiftKey; bitir(); });
    tuval.addEventListener("pointercancel", () => bitir());

    function kutuyuUygula(ekle) {
      const [x0, y0, x1, y1] = D.kutu || [0, 0, 0, 0];
      const sol = Math.min(x0, x1), sag = Math.max(x0, x1);
      const ust = Math.min(y0, y1), alt = Math.max(y0, y1);
      D.kutu = null;
      if (sag - sol < 4 && alt - ust < 4) {            /* tiklama sayilir: secimi birak */
        if (!ekle) { D.secililer.clear(); D.secili = null; }
        D.silOnay = false; ciz();
        return;
      }
      if (!ekle) D.secililer.clear();
      D.secKipi = false;        /* tek seferlik: kip acik kalip yapismasin */
      (D.ag ? D.ag.dugumler : []).forEach((d) => {
        const n = D._nokta && D._nokta[d.kimlik];
        if (n && n.x >= sol && n.x <= sag && n.y >= ust && n.y <= alt) D.secililer.add(d.kimlik);
      });
      D.secili = D.secililer.size === 1 ? Array.from(D.secililer)[0] : null;
      D.silOnay = false; D.sekme = "denetci"; ciz();
      if (D.secililer.size) toast(T("{n} baloncuk seçildi", {n: D.secililer.size}), "iyi");
    }
    /* Yakinlasma IMLECIN oldugu yere dogru: ekranda imlecin altindaki nokta
       yerinde kalsin (tek sabit merkez yerine). */
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || !D.acik) return;
      if (D.kutu || D.secililer.size || D.baglaniyor || D.secKipi) {
        D.kutu = null; D.secililer.clear(); D.baglaniyor = null; D.secKipi = false;
        D.silOnay = false; ciz();
      }
    });

    tuval.addEventListener("wheel", (e) => {
      e.preventDefault();
      const p = yerelKonum(e);
      const eski = D.olcek;
      const yeni = Math.max(0.2, Math.min(4, eski * (e.deltaY < 0 ? 1.12 : 0.89)));
      if (yeni === eski) return;
      const cx = tuval.clientWidth / 2, cy = tuval.clientHeight / 2;
      const ux = (p.x - cx - D.kaydirma.x) / eski, uy = (p.y - cy - D.kaydirma.y) / eski;
      D.kaydirma.x += ux * (eski - yeni);
      D.kaydirma.y += uy * (eski - yeni);
      D.olcek = yeni;
    }, {passive: false});

    /* Sag tik = bagla: ilk tik KAYNAK, ikinci tik HEDEF. Bos alana sag tik iptal. */
    tuval.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      const k = vurulan(yerelKonum(e));
      if (!k) { if (D.baglaniyor) { D.baglaniyor = null; ciz(); } return; }
      if (!D.baglaniyor) {
        D.baglaniyor = k; D.secili = k; D.sekme = "denetci"; ciz();
        toast(T("'{k}' kaynak seçildi — hedefe sağ tıkla.", {k: k}), "iyi");
        return;
      }
      if (D.baglaniyor === k) { D.baglaniyor = null; ciz(); return; }
      bagla(D.baglaniyor, k);
    });

    /* Cift tik: gorunumu sifirla (kaydirma + olcek). */
    tuval.addEventListener("dblclick", (e) => {
      if (vurulan(yerelKonum(e))) return;
      D.kaydirma = {x: 0, y: 0}; D.olcek = 1.25; merkeziTazele();
    });
  }

  return {ac, kapat, ciz, atesle, yerlestir, D};
})();
