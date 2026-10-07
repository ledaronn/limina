/* ofis/sahne.js — Ekip ofisinin 3B sahnesi (three.js r159, vendor/three.min.js).

   Sahne CIZER, KARAR VERMEZ: hangi ajanin nerede ve ne durumda oldugu ofis
   durumundan (ofis/durum.js) gelir. Burada yalnizca geometri, kamera, isik,
   etiketlerin ekrandaki yeri ve tiklamanin neye denk geldigi var.

   Masalarin KONUMU burada (OFIS_DUZENI): bir sunum karari. Hangi aracin hangi
   masaya gittigi Python'da (pevrai/ofis.py), olayla gelir.

   Performans: kare TALEP UZERINE cizilir (iste()). Hareket yoksa rAF hic
   kurulmaz; ofis gorunmezken (durdur()) bekleyen kare de iptal edilir. Logo
   animasyonunun arka planda butun pencereyi cizdigi hata olculup duzeltildi;
   ayni hata burada tekrarlanmasin.

   Metin DOM'da: masa ve ajan etiketleri tuval uzerindeki bir katmanda, 3B
   noktanin izdusumune konur (ceviri ve secilemezlik kurallari gecerli). */
"use strict";
window.OfisSahne = (() => {
  /* Oda: x sag, z kameraya dogru. Arka duvar z=-9, sol duvar x=-13; kamera
     tarafi acik. noktalar: masadaki calisma noktalari [x, z, yuz acisi]. */
  const ODA = {gen: 26, der: 18};
  const OFIS_DUZENI = {
    /* noktalar: [x, z, yuz acisi, oturur]. Oturulan noktalar sandalyenin/kanepenin
       tam ustunde; masa basinda calisan ajan oturur (eskiden ayakta yaziyordu). */
    kod:      {x: -8,   z: -5.5, tip: "kod",      noktalar: [[-8.7, -4.65, Math.PI, true], [-7.3, -4.65, Math.PI, true], [-9.4, -5.5, -Math.PI / 2]]},
    dosya:    {x: -3.5, z: -5.5, tip: "dosya",    noktalar: [[-4.2, -4.65, Math.PI, true], [-2.8, -4.65, Math.PI, true], [-2.1, -5.5, Math.PI / 2]]},
    arsiv:    {x: 2.5,  z: -6,   tip: "arsiv",    noktalar: [[2.5, -5.15, Math.PI, true], [1.4, -4.7, Math.PI], [3.6, -4.7, Math.PI]]},
    ag:       {x: 8.5,  z: -5.5, tip: "ag",       noktalar: [[7.6, -4.4, Math.PI], [9.4, -4.4, Math.PI]]},
    web:      {x: 8.5,  z: 0,    tip: "web",      noktalar: [[8.5, 0.85, Math.PI, true], [9.6, 1.2, Math.PI]]},
    istisare: {x: -1,   z: 1.5,  tip: "istisare", noktalar: [[-1, -0.25, 0, true], [0.75, 1.5, -Math.PI / 2, true], [-1, 3.25, Math.PI, true], [-2.75, 1.5, Math.PI / 2, true]]},
    kapi:     {x: -12.8, z: 5,   tip: "kapi",     noktalar: [[-11.6, 4.3, -Math.PI / 2], [-11.6, 5.7, -Math.PI / 2], [-10.8, 5, -Math.PI / 2]]},
    bekleme:  {x: 6.5,  z: 5,    tip: "bekleme",  etiket: [0, 2.2, 0.35],
               noktalar: [[5.7, 3.05, 0, true], [6.5, 3.05, 0, true], [7.3, 3.05, 0, true], [5.2, 5.4, 0], [7.8, 5.4, 0], [6.5, 5.9, 0]]},
    /* Masasi eslenmeyen arac (pevrai/ofis.py 'diger'): ajan burada, yerinde calisir. */
    diger:    {x: -6,   z: 5.5,  tip: "diger",    noktalar: [[-6.8, 5.5, 0], [-5.2, 5.5, 0], [-6, 6.5, 0]]},
  };
  /* Yuruyus: masalar arasi SABIT ara noktalar (A* gereksiz, grafik kucuk).
     Arka koridor masalarin onunden, istisare masasinin cevresinde halka, sag
     tarafta acik koridor. Masa -> baglandigi ara nokta. */
  const ARA = {
    k1: [-8, -3.2], d1: [-3.5, -3.2], a1: [2.5, -3.6], g1: [8.5, -3.6], r1: [10.9, -3.6], r2: [10.9, 2.3], w1: [8.5, 2.3],
    i1: [-1, -0.9], i2: [1.5, 1.5], i3: [-1, 3.9], i4: [-3.5, 1.5], kp: [-10.4, 5], b1: [5.3, 4.4], dg: [-6, 4.3],
  };
  const KENARLAR = [["k1", "d1"], ["d1", "a1"], ["a1", "g1"], ["g1", "r1"], ["r1", "r2"], ["r2", "w1"], ["d1", "i1"], ["a1", "i1"],
                    ["i1", "i2"], ["i2", "i3"], ["i3", "i4"], ["i4", "i1"], ["i4", "kp"], ["k1", "kp"], ["i3", "b1"], ["i2", "b1"],
                    ["w1", "b1"], ["dg", "i3"], ["dg", "kp"], ["dg", "i4"], ["a1", "i2"]];
  const MASA_ARA = {kod: "k1", dosya: "d1", arsiv: "a1", ag: "g1", web: "w1", kapi: "kp", bekleme: "b1", diger: "dg",
                    istisare: ["i1", "i2", "i3", "i4"]};
  const AZAMI_YURUYUS = 2.5;            // sn: uzun yolda hizlanir, ekran gercegin gerisinde kalmaz
  const RENK = {zemin: 0x1b1814, zeminCizgi: 0x2a241d, duvar: 0x211c17, suPayi: 0x2c251e, ahsap: 0x5b4431,
                ahsapKoyu: 0x3f2f22, metal: 0x3b3631, kumas: 0x4a3a2c, vurgu: 0xd98f35, ekran: 0x1c2a33,
                bitki: 0x4f7a55, kitap: [0x8a5a3a, 0x6f7e5a, 0x7a6048, 0x9a7b4f, 0x5c6a7a]};

  const YAZILIM_OLCEK = 0.5;       // yazilim GL'de cizim cozunurlugu (CSS boyutu degismez)
  const D = {
    kap: null, tuval: null, renderer: null, sahne: null, kamera: null, katman: null,
    kare: null, gorunur: false, kareSayisi: 0, isSuresi: 0, boyut: {g: 1, y: 1},
    hedef: null, kuresel: {r: 30, kutup: 0.9, yon: 0.38}, merkez: null,      // kamera
    gecis: null,                      // kamera yumusak gecisi {bas, son, t}
    masalar: {}, ajanlar: {}, secilebilir: [], secili: null,
    etiketler: [], onSec: null, onCiftTik: null, animasyonlar: new Set(),
  };

  /* WebGL var mi, varsa YAZILIM mi (SwiftShader / llvmpipe: GPU'suz sanal
     makine, uzak masaustu). Yazilimda her piksel islemcide boyanir: kenar
     yumusatma ve tam cozunurluk kareyi 60 ms'ye cikariyordu (olculdu), orada
     kalite dusurulur. */
  function webglVar() {
    try {
      const c = document.createElement("canvas");
      const gl = window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl"));
      if (!gl) return false;
      const bilgi = gl.getExtension("WEBGL_debug_renderer_info");
      const ad = String(bilgi ? gl.getParameter(bilgi.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
      D.yazilimGL = /swiftshader|llvmpipe|software|basic render/i.test(ad);
      D.glAdi = ad;
      const kayip = gl.getExtension("WEBGL_lose_context"); if (kayip) kayip.loseContext();
      return true;
    } catch (e) { return false; }
  }

  /* ---------------- malzeme ve kucuk geometri yardimcilari ---------------- */
  const onbellek = {};
  function malzeme(renk, secenek) {
    const anahtar = renk + JSON.stringify(secenek || {});
    if (!onbellek[anahtar]) onbellek[anahtar] = new THREE.MeshLambertMaterial(Object.assign({color: renk, flatShading: true}, secenek || {}));
    return onbellek[anahtar];
  }
  function kutu(g, y, d, renk, x, yy, z, secenek) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(g, y, d), malzeme(renk, secenek));
    m.position.set(x || 0, yy || 0, z || 0); return m;
  }
  function silindir(r1, r2, y, renk, parca, x, yy, z) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, y, parca || 8), malzeme(renk));
    m.position.set(x || 0, yy || 0, z || 0); return m;
  }
  function kure(r, renk, x, y, z, parca, secenek) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, parca || 8, Math.max(4, Math.round((parca || 8) * 0.7))), malzeme(renk, secenek));
    m.position.set(x || 0, y || 0, z || 0); return m;
  }
  /* Karakterin ve mobilyanin altinda yumusak golge: golge haritasi yerine
     tek bir saydam disk (ucuz, low-poly uslubuna uygun). */
  let golgeDokusu = null;
  function golge(r) {
    if (!golgeDokusu) {
      const c = document.createElement("canvas"); c.width = c.height = 64;
      const x = c.getContext("2d"); const g = x.createRadialGradient(32, 32, 2, 32, 32, 32);
      g.addColorStop(0, "rgba(0,0,0,0.55)"); g.addColorStop(1, "rgba(0,0,0,0)");
      x.fillStyle = g; x.fillRect(0, 0, 64, 64);
      golgeDokusu = new THREE.CanvasTexture(c);
    }
    if (!onbellek.golge) onbellek.golge = new THREE.MeshBasicMaterial({map: golgeDokusu, transparent: true, depthWrite: false});
    const m = new THREE.Mesh(new THREE.PlaneGeometry(r * 2, r * 2), onbellek.golge);
    m.rotation.x = -Math.PI / 2; m.position.y = 0.012; m.userData.golge = true; return m;
  }

  /* ---------------- oda ---------------- */
  function odaKur(s) {
    const zemin = new THREE.Mesh(new THREE.PlaneGeometry(ODA.gen, ODA.der), malzeme(RENK.zemin));
    zemin.rotation.x = -Math.PI / 2; s.add(zemin);
    const izgara = new THREE.GridHelper(ODA.gen, 26, RENK.zeminCizgi, RENK.zeminCizgi);
    izgara.scale.z = ODA.der / ODA.gen; izgara.position.y = 0.005;
    izgara.material.transparent = true; izgara.material.opacity = 0.45; s.add(izgara);
    const yuk = 2.6, kal = 0.25;
    s.add(kutu(ODA.gen + kal, yuk, kal, RENK.duvar, 0, yuk / 2, -ODA.der / 2));          // arka duvar
    s.add(kutu(kal, yuk, ODA.der, RENK.duvar, -ODA.gen / 2, yuk / 2, 0));                 // sol duvar
    s.add(kutu(ODA.gen + kal, 0.12, kal + 0.04, RENK.suPayi, 0, 0.06, -ODA.der / 2 + 0.02));   // supurgelik
    s.add(kutu(kal + 0.04, 0.12, ODA.der, RENK.suPayi, -ODA.gen / 2 + 0.02, 0.06, 0));
    /* arka duvarda iki pencere izi: sahne olu durmasin, yon versin */
    [-6, 5].forEach((x) => s.add(kutu(3.2, 1.2, 0.05, 0x2d3a42, x, 1.6, -ODA.der / 2 + 0.14, {emissive: 0x0c1418})));
  }

  /* ---------------- mobilya ---------------- */
  function masaGovdesi(g, gen, der) {
    g.add(kutu(gen, 0.08, der, RENK.ahsap, 0, 0.76, 0));
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([a, b]) =>
      g.add(kutu(0.07, 0.74, 0.07, RENK.ahsapKoyu, a * (gen / 2 - 0.1), 0.37, b * (der / 2 - 0.1))));
  }
  function sandalye(g, x, z, aci) {
    const s = new THREE.Group();
    s.add(kutu(0.46, 0.06, 0.46, RENK.kumas, 0, 0.46, 0));
    s.add(kutu(0.46, 0.5, 0.06, RENK.kumas, 0, 0.74, 0.21));
    s.add(silindir(0.03, 0.03, 0.43, RENK.metal, 6, 0, 0.215, 0));
    s.add(silindir(0.22, 0.22, 0.03, RENK.metal, 8, 0, 0.02, 0));
    s.position.set(x, 0, z); s.rotation.y = aci || 0; g.add(s);
  }
  function monitor(g, x, z, isik) {
    g.add(kutu(0.7, 0.44, 0.05, RENK.metal, x, 1.14, z));
    const ekran = kutu(0.62, 0.36, 0.01, RENK.ekran, x, 1.14, z + 0.03, {emissive: isik || 0x152a36});
    ekran.material = ekran.material.clone(); ekran.userData.canli = true;     // calisirken yanar: birlestirilmez
    g.add(ekran); g.add(kutu(0.06, 0.16, 0.06, RENK.metal, x, 0.88, z)); return ekran;
  }

  const MOBILYA = {
    kod(g) {
      masaGovdesi(g, 2.4, 1.1);
      const e1 = monitor(g, -0.55, -0.25, 0x1d3b2c), e2 = monitor(g, 0.55, -0.25, 0x1d3b2c);
      g.add(kutu(0.6, 0.03, 0.2, RENK.metal, 0, 0.815, 0.2));
      sandalye(g, -0.7, 0.85, 0); sandalye(g, 0.7, 0.85, 0);
      return [e1, e2];
    },
    dosya(g) {
      masaGovdesi(g, 2.4, 1.1);
      const e = monitor(g, 0.5, -0.25);
      [0, 0.06, 0.12].forEach((y, i) => g.add(kutu(0.42, 0.05, 0.3, [0xe8e0d0, 0xd9cfbd, 0xefe7d8][i], -0.6, 0.83 + y, 0)));
      g.add(silindir(0.02, 0.02, 0.4, RENK.metal, 6, -0.95, 1.0, -0.3));
      g.add(kure(0.09, RENK.vurgu, -0.95, 1.22, -0.3, 8, {emissive: 0x4a2a08}));
      sandalye(g, -0.7, 0.85, 0); sandalye(g, 0.7, 0.85, 0);
      return [e];
    },
    arsiv(g) {
      /* raflar arka duvarda, okuma masasi onunde */
      for (let i = -1; i <= 1; i += 1) {
        const r = new THREE.Group(); r.position.set(i * 1.4, 0, -2.6);
        r.add(kutu(1.3, 2.2, 0.4, RENK.ahsapKoyu, 0, 1.1, 0));
        [0.35, 0.95, 1.55].forEach((y, k) => {
          r.add(kutu(1.2, 0.04, 0.36, RENK.ahsap, 0, y, 0.03));
          for (let b = 0; b < 6; b += 1) r.add(kutu(0.14, 0.4 - ((b + k) % 3) * 0.06, 0.28, RENK.kitap[(b + k + i + 5) % 5], -0.48 + b * 0.19, y + 0.22, 0.04));
        });
        g.add(r);
      }
      masaGovdesi(g, 2.2, 1.0);
      g.add(kutu(0.5, 0.04, 0.35, 0xe8e0d0, 0.2, 0.82, 0.1));
      sandalye(g, 0, 0.85, 0);
      return [];
    },
    istisare(g) {
      g.add(silindir(1.3, 1.3, 0.08, RENK.ahsap, 14, 0, 0.76, 0));
      g.add(silindir(0.12, 0.2, 0.72, RENK.ahsapKoyu, 8, 0, 0.36, 0));
      [[0, -1.75, 0], [1.75, 0, -Math.PI / 2], [0, 1.75, Math.PI], [-1.75, 0, Math.PI / 2]]
        .forEach(([x, z, a]) => sandalye(g, x, z, a + Math.PI));
      g.add(kure(0.12, RENK.vurgu, 0, 0.9, 0, 8, {emissive: 0x3a2206}));
      return [];
    },
    ag(g) {
      g.add(silindir(0.55, 0.65, 0.9, RENK.metal, 8, 0, 0.45, 0));
      const dugumler = [[0, 1.55, 0], [-0.45, 1.25, 0.2], [0.42, 1.3, -0.15], [0.1, 1.9, 0.3], [-0.2, 1.75, -0.35]];
      dugumler.forEach(([x, y, z], i) => g.add(kure(i ? 0.09 : 0.14, i ? 0xc4a0d9 : RENK.vurgu, x, y, z, 8, {emissive: i ? 0x2a1a33 : 0x3a2206})));
      const noktalar = [];
      for (let i = 1; i < dugumler.length; i += 1) noktalar.push(new THREE.Vector3(...dugumler[0]), new THREE.Vector3(...dugumler[i]));
      g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(noktalar),
        new THREE.LineBasicMaterial({color: 0x7d7266})));
      return [];
    },
    web(g) {
      masaGovdesi(g, 2.0, 1.0);
      const e = monitor(g, 0.35, -0.2, 0x16283a);
      const kure_ = new THREE.Mesh(new THREE.IcosahedronGeometry(0.2, 1), new THREE.MeshBasicMaterial({color: 0x91a9e8, wireframe: true}));
      kure_.position.set(-0.55, 1.08, -0.1); g.add(kure_);
      g.add(silindir(0.03, 0.08, 0.2, RENK.metal, 6, -0.55, 0.9, -0.1));
      sandalye(g, 0, 0.85, 0);
      return [e];
    },
    kapi(g) {
      /* sol duvarda kapi cercevesi: onay beklenirken ajan burada durur */
      g.add(kutu(0.3, 2.3, 0.14, RENK.vurgu, 0.05, 1.15, -0.9, {emissive: 0x3a2206}));
      g.add(kutu(0.3, 2.3, 0.14, RENK.vurgu, 0.05, 1.15, 0.9, {emissive: 0x3a2206}));
      g.add(kutu(0.3, 0.16, 1.94, RENK.vurgu, 0.05, 2.3, 0, {emissive: 0x3a2206}));
      g.add(kutu(0.06, 2.2, 1.66, 0x2a221b, -0.05, 1.1, 0));
      const paspas = kutu(1.1, 0.02, 1.6, 0x3a2e24, 0.9, 0.01, 0); g.add(paspas);
      return [];
    },
    bekleme(g) {
      /* kanepe arkada (kameraya bakar), ajanlar onunde durur */
      const hali = new THREE.Mesh(new THREE.CircleGeometry(2.8, 20), malzeme(0x2e241c));
      hali.rotation.x = -Math.PI / 2; hali.position.y = 0.008; g.add(hali);
      g.add(kutu(2.6, 0.42, 0.9, RENK.kumas, 0, 0.21, -2.1));
      g.add(kutu(2.6, 0.62, 0.22, RENK.kumas, 0, 0.6, -2.52));
      g.add(kutu(0.2, 0.55, 0.9, RENK.kumas, -1.3, 0.35, -2.1)); g.add(kutu(0.2, 0.55, 0.9, RENK.kumas, 1.3, 0.35, -2.1));
      g.add(kutu(0.9, 0.3, 0.55, RENK.ahsap, 0, 0.3, -0.8));               // sehpa
      g.add(silindir(0.22, 0.18, 0.4, 0x5a4a3c, 8, 2.3, 0.2, -2.3));       // saksi
      const yaprak = new THREE.Mesh(new THREE.ConeGeometry(0.45, 1.3, 7), malzeme(RENK.bitki));
      yaprak.position.set(2.3, 1.05, -2.3); g.add(yaprak);
      return [];
    },
    diger() { return []; },
  };

  function masalariKur(s) {
    Object.keys(OFIS_DUZENI).forEach((kod) => {
      const d = OFIS_DUZENI[kod];
      const g = new THREE.Group(); g.position.set(d.x, 0, d.z);
      const ekranlar = MOBILYA[d.tip](g);
      if (!["kapi", "bekleme", "diger"].includes(kod)) g.add(golge(1.8));
      g.userData = {tur: "masa", kod};
      s.add(g); D.secilebilir.push(g);
      D.masalar[kod] = {grup: g, ekranlar, etiket: null};
    });
  }

  /* Hareket etmeyen geometriyi malzemeye gore TEK cizim cagrisinda birlestirir.
     Olculdu: 232 cizim cagrisi yazilim GL'de (SwiftShader) kareyi ~2 kat
     yavaslatiyordu; gercek GPU'da da ucuzlatir. Tiklama icin her masada
     gorunmez bir secim kutusu kalir (Raycaster gorunurluge bakmaz). Canli
     parcalar (ekranlar) ve karakterler birlestirilmez. */
  function statikBirlestir(s) {
    s.updateMatrixWorld(true);
    Object.values(D.masalar).forEach((m) => {
      const kutu_ = new THREE.Box3().setFromObject(m.grup);
      if (kutu_.isEmpty()) return;
      const boyut = kutu_.getSize(new THREE.Vector3()), merkez = kutu_.getCenter(new THREE.Vector3());
      const vekil = new THREE.Mesh(new THREE.BoxGeometry(boyut.x, boyut.y, boyut.z), new THREE.MeshBasicMaterial());
      vekil.visible = false; m.grup.worldToLocal(merkez); vekil.position.copy(merkez);
      m.grup.add(vekil); vekil.userData.secim = true;
    });
    const parcalar = [];
    s.traverse((o) => {
      if (!o.isMesh || o.userData.canli || o.userData.secim || o.material.wireframe) return;
      if (o.material.transparent && !o.userData.golge) return;
      parcalar.push(o);
    });
    s.updateMatrixWorld(true);
    birlestir(parcalar, s, null).forEach((m) => { if (m.material === onbellek.golge) m.renderOrder = 1; });
  }

  /* Meshleri tek cizim cagrisina indirir. Isik yaymayan, saydam olmayan
     Lambert parcalar KOSE RENGIYLE tek malzemede birlesir (renk basina ayri
     cagri yok); kalanlar (isik yayan, golge) malzemeye gore. Olculdu: yazilim
     GL'de kare suresini cizim cagrisi sayisi belirliyor. kok: sonucun eklenecegi
     nesne; donusum: dunya -> kok yerel (null = dunya). */
  function birlestir(meshler, kok, donusum) {
    const kovalar = new Map();
    meshler.forEach((o) => {
      const m = o.material;
      const renkli = m.isMeshLambertMaterial && !m.transparent && (!m.emissive || m.emissive.getHex() === 0);
      const anahtar = renkli ? "renkli" : m;
      let g = (o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone()).applyMatrix4(o.matrixWorld);
      if (donusum) g = g.applyMatrix4(donusum);
      if (renkli) {
        const n = g.attributes.position.count, r = new Float32Array(n * 3);
        for (let i = 0; i < n; i += 1) { r[i * 3] = m.color.r; r[i * 3 + 1] = m.color.g; r[i * 3 + 2] = m.color.b; }
        g.setAttribute("color", new THREE.BufferAttribute(r, 3));
      }
      if (!kovalar.has(anahtar)) kovalar.set(anahtar, []);
      kovalar.get(anahtar).push(g);
      o.parent.remove(o); o.geometry.dispose();
    });
    const sonuc = [];
    kovalar.forEach((parcalar, anahtar) => {
      const n = parcalar.reduce((t, g) => t + g.attributes.position.count, 0);
      const konum = new Float32Array(n * 3), normal = new Float32Array(n * 3), uv = new Float32Array(n * 2);
      const renk = anahtar === "renkli" ? new Float32Array(n * 3) : null;
      let i = 0;
      parcalar.forEach((g) => {
        konum.set(g.attributes.position.array, i * 3);
        if (g.attributes.normal) normal.set(g.attributes.normal.array, i * 3);
        if (g.attributes.uv) uv.set(g.attributes.uv.array, i * 2);
        if (renk) renk.set(g.attributes.color.array, i * 3);
        i += g.attributes.position.count; g.dispose();
      });
      const bg = new THREE.BufferGeometry();
      bg.setAttribute("position", new THREE.BufferAttribute(konum, 3));
      bg.setAttribute("normal", new THREE.BufferAttribute(normal, 3));
      bg.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
      if (renk) bg.setAttribute("color", new THREE.BufferAttribute(renk, 3));
      bg.computeBoundingSphere();
      if (anahtar === "renkli" && !onbellek.renkli) onbellek.renkli = new THREE.MeshLambertMaterial({vertexColors: true, flatShading: true});
      const birlesik = new THREE.Mesh(bg, anahtar === "renkli" ? onbellek.renkli : anahtar);
      kok.add(birlesik); sonuc.push(birlesik);
    });
    return sonuc;
  }

  /* Tiklanabilir nesneler: masadaki bir esyaya dokununca ilgili yere gidilir
     (kagit yigini -> yazilan dosyalar, ag dugumleri -> Dusunce Agi...). Geometri
     birlestirildigi icin her nesnenin gorunmez bir secim kutusu var; isabet
     onceligi: ajan > nesne > masa. [masa, kod, merkez(yerel), boyut] */
  const NESNELER = [
    ["dosya", "dosyalar", [-0.6, 0.95, 0], [0.7, 0.5, 0.6]],
    ["kod", "kodlar", [0, 1.12, -0.25], [2.0, 0.7, 0.4]],
    ["ag", "ag", [0, 1.55, 0], [1.4, 1.1, 1.2]],
    ["arsiv", "gecmis", [0, 1.1, -2.6], [4.3, 2.3, 0.6]],
  ];
  function nesneleriKur() {
    NESNELER.forEach(([masa, kod, m, b]) => {
      const kayit = D.masalar[masa]; if (!kayit) return;
      const v = new THREE.Mesh(new THREE.BoxGeometry(b[0], b[1], b[2]), new THREE.MeshBasicMaterial());
      v.visible = false; v.position.set(m[0], m[1], m[2]); v.userData = {tur: "nesne", kod, masa};
      kayit.grup.add(v);
    });
  }

  /* ---------------- karakterler ----------------
     Gorunus koddan: kapsul govde, kure bas, iki kol, iki bacak. gorunum 0-7
     sac/aksesuar varyanti (pevrai/ofis.py GORUNUM_SAYISI). Hazir model dosyasi
     yok: lisans sorunu yok, dosya boyutu kucuk, cevrimdisi. */
  const TEN = [0xe0b48f, 0xc8966d, 0xa9744f, 0x8a5a3c, 0xf0c9a5, 0xd4a27a];
  function karakterKur(ajan) {
    const k = new THREE.Group();
    const renk = new THREE.Color(ajan.renk || "#dcaa65").getHex();
    const koyu = new THREE.Color(ajan.renk || "#dcaa65").multiplyScalar(0.55).getHex();
    const g = Number.isInteger(ajan.gorunum) ? ajan.gorunum : 0;
    const ten = TEN[(g * 7 + (ajan.ad || "").length) % TEN.length];
    /* Govde, kollar, bacaklar ve golge butun karakterler icin ORNEKLENMIS tek
       cizim cagrisi (ornekleriGuncelle); burada yalnizca donusum tasiyan yer
       tutucular var. Yazilim GL'de kareyi cizim cagrisi sayisi belirliyordu. */
    const govde = new THREE.Object3D(); govde.position.y = 0.92; k.add(govde);
    const bas = kure(0.19, ajan.sistem ? 0x9c9a94 : ten, 0, 1.42, 0, 10);
    k.add(bas);
    const uzuv = (x, y, dy) => {
      const g = new THREE.Group(); g.position.set(x, y, 0);
      const o = new THREE.Object3D(); o.position.y = dy; g.add(o); k.add(g); g.userData.ic = o; return g;
    };
    const bacaklar = [-0.1, 0.1].map((x) => uzuv(x, 0.62, -0.3));
    const kollar = [-0.3, 0.3].map((x) => uzuv(x, 1.1, -0.22));
    /* sac / aksesuar: sistem karakterlerinde vizor (ajan degil, ekip islevi) */
    const sac = koyuSac(g);
    if (ajan.sistem) {
      k.add(kutu(0.3, 0.07, 0.08, RENK.vurgu, 0, 1.45, 0.16, {emissive: 0x3a2206}));
    } else if (g % 4 === 0) {
      const s = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), malzeme(sac));
      s.position.y = 1.45; k.add(s);
    } else if (g % 4 === 1) {
      const s = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), malzeme(sac));
      s.position.y = 1.45; k.add(s); k.add(kure(0.09, sac, 0, 1.62, -0.1, 6));
    } else if (g % 4 === 2) {
      k.add(silindir(0.2, 0.2, 0.12, koyu, 10, 0, 1.6, 0)); k.add(silindir(0.27, 0.27, 0.02, koyu, 10, 0, 1.55, 0));
    } else {
      const s = new THREE.Mesh(new THREE.SphereGeometry(0.205, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2.4), malzeme(sac));
      s.position.y = 1.43; s.rotation.x = -0.25; k.add(s);
    }
    if (!ajan.sistem && g >= 4) {                // ikinci varyant: kulaklik ya da gozluk
      if (g % 2 === 0) {
        const t = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.025, 4, 12, Math.PI), malzeme(RENK.metal));
        t.position.y = 1.44; k.add(t);
        [-0.2, 0.2].forEach((x) => k.add(kutu(0.05, 0.1, 0.1, RENK.metal, x, 1.4, 0)));
      } else {
        k.add(kutu(0.3, 0.05, 0.03, 0x1a1a1a, 0, 1.44, 0.18));
      }
    }
    /* bas, sac ve aksesuarlar karaktere gore sabit: tek cizim cagrisi */
    k.updateMatrixWorld(true);
    const sabit = k.children.filter((c) => c.isMesh);
    birlestir(sabit, k, new THREE.Matrix4().copy(k.matrixWorld).invert());
    /* calisirken bas ustunde donen halka (dusunuyor) ve secim halkasi */
    const halka = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.02, 4, 16), new THREE.MeshBasicMaterial({color: 0xd98f35}));
    halka.rotation.x = Math.PI / 2; halka.position.y = 1.85; halka.visible = false; k.add(halka);
    const secim = new THREE.Mesh(new THREE.RingGeometry(0.42, 0.5, 24), new THREE.MeshBasicMaterial({color: 0xd98f35, transparent: true, opacity: 0.85, side: THREE.DoubleSide}));
    secim.rotation.x = -Math.PI / 2; secim.position.y = 0.02; secim.visible = false; k.add(secim);
    /* ekip secimi: gorev cubugunda secili uye hafif parlar */
    const ekip = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.38, 24), new THREE.MeshBasicMaterial({color: 0x6fa97e, transparent: true, opacity: 0.7, side: THREE.DoubleSide}));
    ekip.rotation.x = -Math.PI / 2; ekip.position.y = 0.025; ekip.visible = false; k.add(ekip);
    /* tiklama: govde ornekli cizildigi icin gorunmez secim kutusu */
    const vekil = new THREE.Mesh(new THREE.BoxGeometry(0.6, 1.7, 0.5), new THREE.MeshBasicMaterial());
    vekil.position.y = 0.85; vekil.visible = false; k.add(vekil);
    k.userData = {tur: "ajan", kod: ajan.ad};
    return {grup: k, govde, kollar, bacaklar, halka, secim, ekip, renk: new THREE.Color(renk), koyu: new THREE.Color(koyu)};
  }
  function koyuSac(g) { return [0x2b1d14, 0x5a3a22, 0x1c1c1c, 0x7a5a3a, 0x3a2a1e, 0x8a6a4a, 0x241a12, 0x4a4038][g % 8]; }

  /* ---------------- etiketler (DOM) ---------------- */
  function etiketKur(sinif, metin) {
    const e = el("div", "of-etiket " + sinif);
    e.appendChild(el("span", "of-etiket-ad", metin));
    D.katman.appendChild(e);
    return e;
  }

  /* ---------------- kurulum ---------------- */
  function kur(kap) {
    if (D.renderer) {                 /* tuval bir kez kurulur; kap degistiyse tasinir */
      if (D.kap !== kap) { kap.appendChild(D.tuval); kap.appendChild(D.katman); D.kap = kap; boyutla(); }
      return true;
    }
    if (!window.THREE || !webglVar()) return false;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({antialias: !D.yazilimGL, powerPreference: "low-power"});
    } catch (e) { return false; }
    D.kap = kap; D.renderer = renderer;
    renderer.setPixelRatio(D.yazilimGL ? YAZILIM_OLCEK : Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x0c0c0c, 1);
    D.tuval = renderer.domElement; D.tuval.className = "of-tuval";
    kap.appendChild(D.tuval);
    D.katman = el("div", "of-etiketler"); kap.appendChild(D.katman);
    gecici = new THREE.Vector3(); isin = new THREE.Raycaster();
    zeminDuzlemi = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const s = new THREE.Scene(); D.sahne = s;
    s.fog = new THREE.Fog(0x0c0c0c, 40, 70);
    s.add(new THREE.HemisphereLight(0xfff1e0, 0x1a140f, 1.45));
    const gunes = new THREE.DirectionalLight(0xffe2bf, 1.7); gunes.position.set(-8, 14, 10); s.add(gunes);
    const dolgu = new THREE.DirectionalLight(0x9fb0d0, 0.35); dolgu.position.set(10, 6, -6); s.add(dolgu);
    odaKur(s); masalariKur(s); statikBirlestir(s); nesneleriKur();
    D.kamera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);
    /* Donme merkezi SAHNENIN ortasi (dunya orijini degil) ve BIR KEZ
       hesaplanir; kare basina yeniden hesaplansaydi karakterler yurudukce
       kamera kayardi (ag.js dersi). */
    D.merkez = new THREE.Vector3(-0.8, 0, 0.6);
    D.hedef = D.merkez.clone();
    kameraGuncelle();
    tuvalOlaylari(D.tuval);
    if (window.ResizeObserver) new ResizeObserver(() => { boyutla(); }).observe(kap);
    boyutla();
    return true;
  }

  function boyutla() {
    if (!D.renderer || !D.kap) return;
    const g = D.kap.clientWidth, y = D.kap.clientHeight;
    if (!g || !y) return;
    D.boyut = {g, y};
    D.renderer.setSize(g, y, false);
    D.kamera.aspect = g / y; D.kamera.updateProjectionMatrix();
    iste();
  }

  function kameraGuncelle() {
    const k = D.kuresel;
    const sin = Math.sin(k.kutup);
    D.kamera.position.set(D.hedef.x + k.r * sin * Math.sin(k.yon), D.hedef.y + k.r * Math.cos(k.kutup),
                          D.hedef.z + k.r * sin * Math.cos(k.yon));
    D.kamera.lookAt(D.hedef);
  }

  /* ---------------- kare dongusu (talep uzerine) ---------------- */
  function iste() {
    if (!D.gorunur || D.kare || !D.renderer) return;
    D.kare = requestAnimationFrame(kareCiz);
  }
  let sonZaman = 0;
  function kareCiz(zaman) {
    D.kare = null;
    if (!D.gorunur) return;
    const dt = Math.min(0.1, sonZaman ? (zaman - sonZaman) / 1000 : 0.016);
    sonZaman = zaman;
    let devam = false;
    if (D.gecis) devam = gecisIlerle(dt) || devam;
    D.animasyonlar.forEach((f) => { if (f(dt, zaman)) devam = true; else D.animasyonlar.delete(f); });
    const b = performance.now();
    ornekleriGuncelle();
    D.renderer.render(D.sahne, D.kamera);
    etiketleriKonumla();
    D.isSuresi = D.isSuresi * 0.9 + (performance.now() - b) * 0.1;    // kare basina is (ms), olcum icin
    D.kareSayisi += 1;
    if (devam) iste(); else sonZaman = 0;
  }
  function baslat() { D.gorunur = true; boyutla(); iste(); }
  function durdur() {
    D.gorunur = false;
    if (D.kare) cancelAnimationFrame(D.kare);
    D.kare = null; sonZaman = 0;
  }
  /* Animasyon kaydi: f(dt) true dondukce kareler cizilir. */
  function animasyonEkle(f) { D.animasyonlar.add(f); iste(); }

  let gecici = null;                 /* THREE tembel yuklenir: kur()'da */
  /* Kare basina yalnizca DEGISEN stil yazilir ve yerlesim OKUNMAZ (boyut
     boyutla()'da onbellekte): her karede clientWidth okumak bir onceki karenin
     yazimlarindan sonra zorunlu yerlesim hesabi tetikliyordu (olculdu: CPU 4x'te
     karenin ~6 ms'si). Derinlige gore z-index de yok: her karede degisince
     katmanlar yeniden boyaniyordu. */
  function etiketleriKonumla() {
    const g = D.boyut.g, y = D.boyut.y;
    D.etiketler.forEach((e) => {
      e.nesne.getWorldPosition(gecici);
      gecici.y += e.yukseklik;
      gecici.project(D.kamera);
      const gizli = gecici.z > 1 || gecici.x < -1.2 || gecici.x > 1.2 || gecici.y < -1.2 || gecici.y > 1.2;
      if (gizli !== e.gizli) { e.dugum.style.visibility = gizli ? "hidden" : ""; e.gizli = gizli; }
      if (gizli) return;
      const tr = "translate3d(" + Math.round((gecici.x + 1) / 2 * g) + "px, " + Math.round((1 - gecici.y) / 2 * y) + "px, 0) translate(-50%, -100%)";   // 3d: her etiket kendi katmaninda (olculdu: 2d tek katmandan hizli)
      if (tr !== e.tr) { e.dugum.style.transform = tr; e.tr = tr; }
    });
  }

  /* ---------------- kamera etkilesimi ----------------
     Sol surukle: yorunge. Tekerlek: IMLECIN oldugu noktaya dogru yakinlas.
     Sag/orta surukle: kaydir. Cift tik: masa/ajana odaklan. */
  let isin = null, zeminDuzlemi = null;
  function ekranNoktasi(e) {
    const k = D.tuval.getBoundingClientRect();
    return new THREE.Vector2(((e.clientX - k.left) / k.width) * 2 - 1, -((e.clientY - k.top) / k.height) * 2 + 1);
  }
  function zemindeNokta(n) {
    isin.setFromCamera(n, D.kamera);
    const p = new THREE.Vector3();
    return isin.ray.intersectPlane(zeminDuzlemi, p) ? p : null;
  }
  function vurulan(n) {
    isin.setFromCamera(n, D.kamera);
    /* Ajan once: masanin gorunmez secim kutusu masada duran karakteri de
       kapsiyor; isin ikisine de degiyorsa tiklanan karakterdir. */
    let masa = null, nesne = null;
    for (const s of isin.intersectObjects(D.secilebilir, true)) {
      let o = s.object;
      while (o && !(o.userData && o.userData.tur)) o = o.parent;
      if (!o) continue;
      if (o.userData.tur === "ajan") return {tur: "ajan", kod: o.userData.kod};
      if (o.userData.tur === "nesne") nesne = nesne || {tur: "nesne", kod: o.userData.kod, masa: o.userData.masa};
      else masa = masa || {tur: o.userData.tur, kod: o.userData.kod};
    }
    return nesne || masa;
  }
  function tuvalOlaylari(t) {
    let surukle = null;
    t.addEventListener("contextmenu", (e) => e.preventDefault());
    t.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 && e.button !== 1 && e.button !== 2) return;
      D.gecis = null;
      /* ONCE durum, SONRA yakalama: setPointerCapture bazi WebView/dokunma
         durumlarinda firlatiyor; firlatinca surukleme olmemeli (ag.js dersi). */
      surukle = {tur: e.button === 0 && !e.shiftKey ? "dondur" : "kaydir", x: e.clientX, y: e.clientY, bas: [e.clientX, e.clientY]};
      try { t.setPointerCapture(e.pointerId); } catch (hata) { /* yakalama bir iyilestirme */ }
      if (e.button === 1) e.preventDefault();
    });
    let sonImlec = 0;
    t.addEventListener("pointermove", (e) => {
      if (!surukle && e.timeStamp - sonImlec > 60) {
        sonImlec = e.timeStamp;
        const v = vurulan(ekranNoktasi(e));
        t.style.cursor = v && (v.tur === "ajan" || v.tur === "nesne") ? "pointer" : "";
      }
      if (!surukle) return;
      const dx = e.clientX - surukle.x, dy = e.clientY - surukle.y;
      surukle.x = e.clientX; surukle.y = e.clientY;
      if (surukle.tur === "dondur") {
        D.kuresel.yon -= dx * 0.006;
        D.kuresel.kutup = Math.max(0.28, Math.min(1.38, D.kuresel.kutup - dy * 0.005));
      } else {
        /* Kaydirma zeminde: imlecin altindaki zemin noktasi imlecle gelsin. */
        const olcek = D.kuresel.r * 0.0016;
        const yon = D.kuresel.yon;
        const ileri = new THREE.Vector3(-Math.sin(yon), 0, -Math.cos(yon));
        const sag = new THREE.Vector3(Math.cos(yon), 0, -Math.sin(yon));
        D.hedef.addScaledVector(sag, -dx * olcek).addScaledVector(ileri, dy * olcek);
        sinirla();
      }
      kameraGuncelle(); iste();
    });
    const birak = (e) => {
      if (!surukle) return;
      const tik = Math.hypot(e.clientX - surukle.bas[0], e.clientY - surukle.bas[1]) < 5;
      const tur = surukle.tur;
      surukle = null;
      if (tik && tur === "dondur" && e.type === "pointerup") {
        const v = vurulan(ekranNoktasi(e));
        if (D.onSec) D.onSec(v, {ekle: e.ctrlKey || e.metaKey || e.shiftKey});
      }
    };
    t.addEventListener("pointerup", birak);
    t.addEventListener("pointercancel", () => { surukle = null; });
    t.addEventListener("wheel", (e) => {
      e.preventDefault();
      D.gecis = null;
      const eski = D.kuresel.r;
      const yeni = Math.max(5, Math.min(48, eski * (e.deltaY < 0 ? 0.88 : 1.12)));
      if (yeni === eski) return;
      /* Imlecin altindaki zemin noktasi yerinde kalsin: hedef o noktaya
         yakinlasma oraninda yaklasir. */
      const p = zemindeNokta(ekranNoktasi(e));
      if (p) { D.hedef.lerp(p, 1 - yeni / eski); D.hedef.y = 0; sinirla(); }
      D.kuresel.r = yeni;
      kameraGuncelle(); iste();
    }, {passive: false});
    t.addEventListener("dblclick", (e) => {
      const v = vurulan(ekranNoktasi(e));
      if (v) odaklan(v);
      if (D.onCiftTik) D.onCiftTik(v);
    });
  }
  /* Dunya noktasi -> sayfa koordinati; sayfa koordinati -> zemin noktasi.
     Etiketler ve testler (imlecin altindaki nokta yerinde kaliyor mu) icin. */
  function izdusum(x, y, z) {
    const v = new THREE.Vector3(x, y, z).project(D.kamera);
    const r = D.tuval.getBoundingClientRect();
    return {x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height};
  }
  function zemineIndir(cx, cy) {
    const p = zemindeNokta(ekranNoktasi({clientX: cx, clientY: cy}));
    return p ? {x: p.x, y: p.y, z: p.z} : null;
  }
  function sinirla() {
    D.hedef.x = Math.max(-ODA.gen / 2, Math.min(ODA.gen / 2, D.hedef.x));
    D.hedef.z = Math.max(-ODA.der / 2, Math.min(ODA.der / 2, D.hedef.z));
  }

  function animasyonAzMi() {
    return document.body.classList.contains("animasyon-kapali") || document.body.classList.contains("animasyon-az");
  }
  /* Kamerayi yumusakca bir hedefe tasir (animasyon kapaliysa aninda). */
  function kameraGit(hedef, r, kutup, yon) {
    const son = {h: hedef.clone(), r, kutup: kutup === undefined ? D.kuresel.kutup : kutup, yon: yon === undefined ? D.kuresel.yon : yon};
    if (animasyonAzMi()) {
      D.hedef.copy(son.h); Object.assign(D.kuresel, {r: son.r, kutup: son.kutup, yon: son.yon});
      kameraGuncelle(); iste(); return;
    }
    D.gecis = {bas: {h: D.hedef.clone(), r: D.kuresel.r, kutup: D.kuresel.kutup, yon: D.kuresel.yon}, son, t: 0};
    iste();
  }
  function gecisIlerle(dt) {
    const g = D.gecis; g.t = Math.min(1, g.t + dt / 0.55);
    const e = 1 - Math.pow(1 - g.t, 3);
    D.hedef.lerpVectors(g.bas.h, g.son.h, e);
    D.kuresel.r = g.bas.r + (g.son.r - g.bas.r) * e;
    D.kuresel.kutup = g.bas.kutup + (g.son.kutup - g.bas.kutup) * e;
    D.kuresel.yon = g.bas.yon + (g.son.yon - g.bas.yon) * e;
    kameraGuncelle();
    if (g.t >= 1) { D.gecis = null; return false; }
    return true;
  }
  function odaklan(v) {
    if (v.tur === "masa" && D.masalar[v.kod]) {
      const p = D.masalar[v.kod].grup.position; kameraGit(new THREE.Vector3(p.x, 0, p.z), 9);
    } else if (v.tur === "ajan" && D.ajanlar[v.kod]) {
      const p = D.ajanlar[v.kod].grup.position; kameraGit(new THREE.Vector3(p.x, 0.8, p.z), 6.5);
    }
  }
  function ofiseDon() { kameraGit(D.merkez, 30, 0.9, 0.38); }

  /* ---------------- ajanlar ve masalar: disaridan ---------------- */
  /* Masa etiketleri: kopruden gelen adlar (Python, o anki dilde). */
  function masaAdlari(masalar) {
    (masalar || []).forEach((m) => {
      const kayit = D.masalar[m.kod]; if (!kayit) return;
      if (!kayit.etiket) {
        kayit.etiket = etiketKur("masa", m.ad);
        /* etiket noktasi: masanin ustu; bazi masalarda kaydirilmis (dinlenme: kanepenin ustu) */
        const [dx, dz, y] = OFIS_DUZENI[m.kod].etiket || [0, 0, m.kod === "arsiv" ? 2.7 : m.kod === "kapi" ? 2.8 : 2.1];
        const nokta = new THREE.Object3D(); nokta.position.set(dx, 0, dz); kayit.grup.add(nokta);
        D.etiketler.push({dugum: kayit.etiket, nesne: nokta, yukseklik: y});
      } else kayit.etiket.firstChild.textContent = m.ad;
      kayit.etiket.title = m.aciklama || "";
    });
    iste();
  }

  /* ---------------- ornekli (instanced) karakter parcalari ---------------- */
  const AZAMI_KARAKTER = 64;
  let havuz = null;
  function havuzKur() {
    if (havuz) return havuz;
    const ornek = (geo, mat, n) => {
      const m = new THREE.InstancedMesh(geo, mat, n); m.count = 0; m.frustumCulled = false; D.sahne.add(m); return m;
    };
    const renkli = new THREE.MeshLambertMaterial({flatShading: true});
    havuz = {
      govde: ornek(new THREE.CapsuleGeometry(0.22, 0.42, 3, 8), renkli, AZAMI_KARAKTER),
      kol: ornek(new THREE.CapsuleGeometry(0.06, 0.34, 2, 6), renkli.clone(), AZAMI_KARAKTER * 2),
      bacak: ornek(new THREE.CapsuleGeometry(0.075, 0.42, 2, 6), malzeme(0x2b2520), AZAMI_KARAKTER * 2),
      golge: null,
    };
    golge(0.5);                                   // golge dokusu ve malzemesi hazir olsun
    havuz.golge = ornek(new THREE.PlaneGeometry(1, 1), onbellek.golge, AZAMI_KARAKTER);
    havuz.golge.renderOrder = 1;
    return havuz;
  }
  const GRI = 0x55524d;
  /* Her karede cizimden once: karakterlerin (animasyonlu) donusumleri ornek
     matrislerine yazilir. En fazla 64 karakter; 30 matris yazmak ucuz. */
  function ornekleriGuncelle() {
    const h = havuzKur();
    let i = 0;
    const gri = new THREE.Color(GRI), m = new THREE.Matrix4();
    Object.values(D.ajanlar).forEach((k) => {
      if (i >= AZAMI_KARAKTER || !k.grup.visible) return;
      k.grup.updateMatrixWorld(true);
      h.govde.setMatrixAt(i, k.govde.matrixWorld);
      h.govde.setColorAt(i, k.gri ? gri : k.renk);
      [0, 1].forEach((j) => {
        h.bacak.setMatrixAt(i * 2 + j, k.bacaklar[j].userData.ic.matrixWorld);
        h.kol.setMatrixAt(i * 2 + j, k.kollar[j].userData.ic.matrixWorld);
        h.kol.setColorAt(i * 2 + j, k.gri ? gri : k.koyu);
      });
      const p = k.grup.position;
      h.golge.setMatrixAt(i, m.makeRotationX(-Math.PI / 2).setPosition(p.x, 0.012, p.z));
      i += 1;
    });
    h.govde.count = i; h.golge.count = i; h.bacak.count = i * 2; h.kol.count = i * 2;
    [h.govde, h.kol, h.bacak, h.golge].forEach((o) => {
      o.instanceMatrix.needsUpdate = true;
      if (o.instanceColor) o.instanceColor.needsUpdate = true;
    });
  }

  /* liste: [{ad, renk, gorunum, sistem?}] — yoksa yaratilir, listede
     olmayan silinir. Konum/durum disaridan (konumla / durumAyarla). */
  function ajanlariAyarla(liste) {
    const adlar = new Set(liste.map((a) => a.ad));
    let degisti = false;
    Object.keys(D.ajanlar).forEach((ad) => {
      if (adlar.has(ad)) return;
      const k = D.ajanlar[ad];
      D.sahne.remove(k.grup); k.etiket.remove();
      D.secilebilir = D.secilebilir.filter((x) => x !== k.grup);
      D.etiketler = D.etiketler.filter((x) => x.dugum !== k.etiket);
      delete D.ajanlar[ad]; degisti = true;
    });
    liste.forEach((a) => {
      const imza = (a.renk || "") + "|" + a.gorunum + "|" + (a.sistem ? 1 : 0);
      let k = D.ajanlar[a.ad];
      if (k && k.imza !== imza) {           /* gorunus degisti: yeniden kur, konum korunur */
        const p = k.grup.position.clone(), r = k.grup.rotation.y;
        D.sahne.remove(k.grup); D.secilebilir = D.secilebilir.filter((x) => x !== k.grup);
        const yeni = karakterKur(a); yeni.grup.position.copy(p); yeni.grup.rotation.y = r;
        Object.assign(k, yeni, {imza, gri: false}); degisti = true;
        D.sahne.add(k.grup); D.secilebilir.push(k.grup);
        D.etiketler.forEach((e) => { if (e.dugum === k.etiket) e.nesne = k.grup; });
      }
      if (!k) {
        k = Object.assign(karakterKur(a), {imza}); degisti = true;
        k.etiket = etiketKur("ajan" + (a.sistem ? " sistem" : ""), a.gorunenAd || a.ad);
        k.rozet = el("span", "of-rozet"); k.etiket.appendChild(k.rozet);
        D.ajanlar[a.ad] = k;
        D.sahne.add(k.grup); D.secilebilir.push(k.grup);
        D.etiketler.push({dugum: k.etiket, nesne: k.grup, yukseklik: 2.05});
      }
      if (k.etiket.firstChild.textContent !== (a.gorunenAd || a.ad)) k.etiket.firstChild.textContent = a.gorunenAd || a.ad;
    });
    if (degisti) iste();                      /* yalnizca karakter eklendi/silindi/degistiyse kare */
  }

  /* ---------------- yurume ve durum gorselleri ---------------- */
  function yakinAra(x, z) {
    let en = null, enU = Infinity;
    Object.keys(ARA).forEach((k) => { const u = Math.hypot(ARA[k][0] - x, ARA[k][1] - z); if (u < enU) { enU = u; en = k; } });
    return en;
  }
  /* Dijkstra: kucuk sabit grafikte en kisa ara nokta dizisi. */
  function araYol(bas, son) {
    const uz = {}, onceki = {}, kalan = new Set(Object.keys(ARA));
    Object.keys(ARA).forEach((k) => { uz[k] = Infinity; }); uz[bas] = 0;
    while (kalan.size) {
      let u = null; kalan.forEach((k) => { if (u === null || uz[k] < uz[u]) u = k; });
      kalan.delete(u); if (u === son || uz[u] === Infinity) break;
      KENARLAR.forEach(([a, b]) => {
        const v = a === u ? b : b === u ? a : null; if (!v || !kalan.has(v)) return;
        const d = uz[u] + Math.hypot(ARA[u][0] - ARA[v][0], ARA[u][1] - ARA[v][1]);
        if (d < uz[v]) { uz[v] = d; onceki[v] = u; }
      });
    }
    const yol = []; let k = son;
    while (k) { yol.unshift(k); k = onceki[k]; }
    return yol[0] === bas ? yol : [bas, son];
  }
  function masaNoktasi(masa, i) {
    const d = OFIS_DUZENI[masa] || OFIS_DUZENI.diger;
    if (i < d.noktalar.length) return d.noktalar[i];
    const j = i - d.noktalar.length, aci = j * 1.1, r = 2.2 + Math.floor(j / 6) * 0.9;     // tasma: masanin cevresi
    return [d.x + Math.cos(aci) * r, d.z + 1.2 + Math.sin(aci) * r * 0.6, Math.PI];
  }
  function noktaSayilari() {
    const n = {}; Object.keys(OFIS_DUZENI).forEach((m) => { n[m] = OFIS_DUZENI[m].noktalar.length; }); return n;
  }

  /* Karakteri masadaki noktasina gonderir. Yurume bir ANIMASYON durumu:
     yolda yeni hedef gelirse yol su anki konumdan yeniden kurulur (olay
     kuyrukta beklemez). Animasyon azaltilmissa ya da ilk yerlesimse isinlanir. */
  function hedefle(ad, masa, nokta) {
    const k = D.ajanlar[ad]; if (!k) return;
    const [x, z, aci, oturur] = masaNoktasi(masa, nokta);
    if (k.hedef && k.hedef.x === x && k.hedef.z === z) return;
    k.hedef = {x, z, aci, masa, oturur: !!oturur};
    const p = k.grup.position;
    if (animasyonAzMi() || !k.yerlesti) {
      p.set(x, 0, z); k.grup.rotation.y = aci; k.yol = null; k.yerlesti = true; pozAyarla(k); iste(); return;
    }
    p.y = 0; k.bacaklar[0].rotation.x = 0; k.bacaklar[1].rotation.x = 0;       // kalkar, yurur
    const bas = yakinAra(p.x, p.z);
    const ara = MASA_ARA[masa];
    const hedefAra = Array.isArray(ara)
      ? ara.reduce((a, b) => (Math.hypot(ARA[a][0] - x, ARA[a][1] - z) <= Math.hypot(ARA[b][0] - x, ARA[b][1] - z) ? a : b))
      : ara || yakinAra(x, z);
    const ayniYer = Math.hypot(p.x - x, p.z - z) < 3.2;
    const noktalar = (ayniYer ? [] : araYol(bas, hedefAra).map((a) => ARA[a])).concat([[x, z]]);
    let uz = 0, onceki = [p.x, p.z];
    noktalar.forEach((n) => { uz += Math.hypot(n[0] - onceki[0], n[1] - onceki[1]); onceki = n; });
    k.yol = {noktalar, i: 0, hiz: Math.max(3.2, uz / AZAMI_YURUYUS)};
    animasyonEkle(karakterAnimasyonu);
  }

  /* Durum DEGISMEDIYSE kare istenmez: her uygula() (balon suresi dolmasi gibi
     yalnizca DOM'u ilgilendiren degisiklikler dahil) bos yere kare cizdiriyordu. */
  /* Oturma pozu: kalca koltuk hizasina iner, bacaklar one uzanir. Yalnizca
     varilan nokta oturulan bir yerse (sandalye, kanepe). */
  function pozAyarla(k) {
    const otur = !!(k.hedef && k.hedef.oturur && !k.yol);
    k.oturuyor = otur;
    k.grup.position.y = otur ? (k.hedef.masa === "bekleme" ? -0.18 : -0.1) : 0;
    const b = otur ? -Math.PI / 2 : 0;
    k.bacaklar[0].rotation.x = b; k.bacaklar[1].rotation.x = b;
  }

  function durumGoster(ad, durum) {
    const k = D.ajanlar[ad]; if (!k || k.durum === durum) return;
    k.durum = durum;
    k.gri = durum === "bilinmiyor";          /* renk ornekleriGuncelle'de (govde ve kollar gri) */
    k.halka.visible = durum === "dusunuyor";
    animasyonEkle(karakterAnimasyonu);
  }

  /* Tek animasyon: yuruyen karakterler, calisanlarin kol hareketi, dusunenin
     halkasi, masadaki ekran isigi. Kimse yurumuyor ve kimse calismiyorsa
     false doner: kare durur. Animasyon azaltilmissa yalnizca yurume (zaten
     isinlanir) — calisma hareketi yok. */
  let saat = 0;
  function karakterAnimasyonu(dt) {
    saat += dt;
    const az = animasyonAzMi();
    let devam = false;
    const calisanMasa = {};
    Object.values(D.ajanlar).forEach((k) => {
      if (k.yol) {
        devam = true;
        const n = k.yol.noktalar[k.yol.i], p = k.grup.position;
        const dx = n[0] - p.x, dz = n[1] - p.z, u = Math.hypot(dx, dz), adim = k.yol.hiz * dt;
        if (u <= adim) {
          p.x = n[0]; p.z = n[1]; k.yol.i += 1;
          if (k.yol.i >= k.yol.noktalar.length) { k.yol = null; k.grup.rotation.y = k.hedef.aci; pozAyarla(k); }
        } else {
          p.x += dx / u * adim; p.z += dz / u * adim;
          let fark = Math.atan2(dx, dz) - k.grup.rotation.y; fark = Math.atan2(Math.sin(fark), Math.cos(fark));
          k.grup.rotation.y += fark * Math.min(1, dt * 12);
        }
        const s = Math.sin(saat * 11) * 0.55;
        k.bacaklar[0].rotation.x = s; k.bacaklar[1].rotation.x = -s;
        k.kollar[0].rotation.x = -s * 0.8; k.kollar[1].rotation.x = s * 0.8;
        k.govde.position.y = 0.92 + Math.abs(Math.cos(saat * 11)) * 0.04;
        return;
      }
      pozAyarla(k); k.govde.position.y = 0.92;
      const calisiyor = k.durum === "calisiyor" || k.durum === "dusunuyor";
      if (calisiyor && k.hedef) calisanMasa[k.hedef.masa] = true;
      if (calisiyor && !az) {
        devam = true;
        const s = Math.sin(saat * 9 + k.grup.id);
        k.kollar[0].rotation.x = -0.9 + s * 0.15; k.kollar[1].rotation.x = -0.9 - s * 0.15;
        if (k.halka.visible) k.halka.rotation.z = saat * 3;
      } else {
        k.kollar[0].rotation.x = calisiyor ? -0.9 : 0; k.kollar[1].rotation.x = calisiyor ? -0.9 : 0;
      }
    });
    Object.keys(D.masalar).forEach((m) => {
      const yan = !!calisanMasa[m];
      D.masalar[m].ekranlar.forEach((e) => { e.material.emissiveIntensity = yan ? 2.6 : 1; });
    });
    return devam;
  }

  function konumla(ad, x, z, aci) {
    const k = D.ajanlar[ad]; if (!k) return;
    k.grup.position.set(x, 0, z);
    if (aci !== undefined) k.grup.rotation.y = aci;
    iste();
  }

  function ekipVurgula(adlar) {
    Object.keys(D.ajanlar).forEach((a) => { D.ajanlar[a].ekip.visible = adlar.has(a); });
    iste();
  }
  /* Yeni ajan kapidan girer: once kapiya konur, sonra hedefine yurur. */
  function kapidanGir(ad) {
    const k = D.ajanlar[ad]; if (!k) return;
    const [x, z, aci] = masaNoktasi("kapi", 0);
    k.grup.position.set(x, 0, z); k.grup.rotation.y = aci; k.yerlesti = true; k.hedef = null; k.kapidanGirdi = true;
    pozAyarla(k);
  }

  function sec(ad) {
    D.secili = ad;
    Object.keys(D.ajanlar).forEach((a) => {
      D.ajanlar[a].secim.visible = a === ad;
      D.ajanlar[a].etiket.classList.toggle("secili", a === ad);
    });
    iste();
  }

  return {D, OFIS_DUZENI, webglVar, kur, baslat, durdur, iste, boyutla, masaAdlari, ajanlariAyarla,
          konumla, sec, odaklan, ofiseDon, animasyonEkle, animasyonAzMi, kameraGit, izdusum, zemineIndir,
          hedefle, durumGoster, noktaSayilari, masaNoktasi, ekipVurgula, kapidanGir};
})();
