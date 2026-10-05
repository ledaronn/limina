/* ofis/durum.js — Ekip ofisinin SAF durum makinesi: durumUygula(durum, olay) -> yeniDurum.

   DOM'a ve three.js'e DOKUNMAZ; girdi olay, cikti her karakterin
   {masa, nokta, durum, balon, ...} bilgisi. Ayni olay dizisi her zaman ayni
   durumu verir; girdi durumu degistirilmez (yeni nesne doner). Butun
   olay -> durum mantigi burada (docs/OFIS_TASARIM.md 3.3); sahne yalnizca cizer.

   Karakterler:
     - tanimli ajanlar (policy.toml [ajanlar.<ad>]) ve iki sistem karakteri
       (@planlayici, @birlestirici);
     - GECICI kopyalar: ayni ajan bir kosuda iki alt gorev alirsa ya da alt
       gorev 'varsayilan' ajanla calisirsa, karakter iki masada birden
       duramaz — o isci icin kapidan bir kopya girer, kosu bitince cikar.
   Olaylardaki 'ajan' alani ALT GOREV adidir (isci); hangi karaktere ait
   oldugu ekip_isci baslangic olayindan (args.ajan) ogrenilir.

   Durustluk (6.3): hareket yalnizca gercek olaydan. Calisan bir karakterden
   uzun sure olay gelmezse (_zaman olayi) ya da gorev bittigi halde bitis
   olayi gelmediyse karakter 'bilinmiyor' olur: gri, calisiyormus gibi yapmaz. */
"use strict";
window.OfisDurum = (() => {
  const SISTEM = ["@planlayici", "@birlestirici"];
  const BITMIS_KOSU = ["bitti", "hata", "reddedildi", "plan_hatasi"];
  const SESSIZLIK_MS = 5 * 60 * 1000;        // calisan karakterden bu kadar olay yoksa: bilinmiyor
  const BALON_UZUNLUK = 60;
  const SON_ARAC = 5;

  function karakter(anahtar, ajan, gecici) {
    return {anahtar, ajan: ajan || null, isci: null, gecici: !!gecici, masa: gecici ? "kapi" : "bekleme",
            nokta: 0, durum: "bosta", balon: null, zarf: 0, sonAraclar: [], yazdiklari: [], modelGecis: null,
            sonOlay: 0, sonZaman: 0, ayrildi: false};
  }

  /* noktaSayilari: {masa: calisma noktasi sayisi} — sahnenin duzeni (OFIS_DUZENI). */
  function bos(ajanAdlari, noktaSayilari) {
    const d = {kosu: null, karakterler: {}, isciler: {}, masaGecmisi: {}, sira: 0, noktalar: Object.assign({}, noktaSayilari || {})};
    SISTEM.concat(ajanAdlari || []).forEach((a) => { d.karakterler[a] = karakter(a, SISTEM.includes(a) ? null : a, false); });
    return noktaAta(d);
  }

  /* Tanimli ajan listesi degisince (Ajanlar cekmecesinden ekleme/silme):
     yeni ajan eklenir, silinen (ve o an bir isciye bagli olmayan) kalkar. */
  function ajanlariEsitle(durum, ajanAdlari) {
    const d = kopya(durum);
    (ajanAdlari || []).forEach((a) => { if (!d.karakterler[a]) d.karakterler[a] = karakter(a, a, false); });
    Object.keys(d.karakterler).forEach((a) => {
      const k = d.karakterler[a];
      if (!k.gecici && !SISTEM.includes(a) && !(ajanAdlari || []).includes(a) && !k.isci) delete d.karakterler[a];
    });
    return noktaAta(d);
  }

  function kopya(d) {
    const y = {kosu: d.kosu ? Object.assign({}, d.kosu) : null, karakterler: {}, isciler: Object.assign({}, d.isciler),
               masaGecmisi: {}, sira: d.sira, noktalar: d.noktalar};
    Object.keys(d.karakterler).forEach((a) => {
      const k = d.karakterler[a];
      y.karakterler[a] = Object.assign({}, k, {sonAraclar: k.sonAraclar.slice(), yazdiklari: k.yazdiklari.slice()});
    });
    Object.keys(d.masaGecmisi).forEach((m) => { y.masaGecmisi[m] = d.masaGecmisi[m].slice(); });
    return y;
  }

  /* Her karakterin masadaki calisma noktasi: masa degisince o masadaki en
     kucuk BOS nokta. Dolu noktaya ikinci ajan konmaz; nokta sayisini asan
     karakter tasma sirasi alir (sahne masanin cevresine dizer). Karakter ayni
     masada kaldikca noktasi degismez. */
  function noktaAta(d) {
    const dolu = {};
    const sirali = Object.values(d.karakterler).sort((a, b) => (a.masaninSirasi || 0) - (b.masaninSirasi || 0) || (a.anahtar < b.anahtar ? -1 : 1));
    sirali.forEach((k) => {
      const m = dolu[k.masa] = dolu[k.masa] || new Set();
      if (k.noktaMasasi === k.masa && !m.has(k.nokta)) { m.add(k.nokta); return; }
      k.noktaMasasi = null;
    });
    sirali.forEach((k) => {
      if (k.noktaMasasi === k.masa) return;
      const m = dolu[k.masa];
      let i = 0; while (m.has(i)) i += 1;
      m.add(i); k.nokta = i; k.noktaMasasi = k.masa;
    });
    return d;
  }

  function tasi(d, k, masa) {
    if (k.masa !== masa) { k.masa = masa; k.noktaMasasi = null; k.masaninSirasi = d.sira; }
  }
  function dokun(d, k, zaman) { k.sonOlay = d.sira; if (zaman) k.sonZaman = zaman; }

  /* Isci (alt gorev adi) -> karakter anahtari. Bilinmeyen isci (ekip alani
     kosunun ortasinda acildi, baslangic olayi kacti) gecici bir karakter olur. */
  function isciKarakteri(d, isci, ajan) {
    if (d.isciler[isci] && d.karakterler[d.isciler[isci]]) return d.karakterler[d.isciler[isci]];
    let k = ajan && ajan !== "varsayilan" ? d.karakterler[ajan] : null;
    if (k && (k.gecici || (k.isci && k.isci !== isci))) k = null;       // mesgul: kopya girer
    if (!k) {
      const anahtar = "~" + isci;
      k = d.karakterler[anahtar] = d.karakterler[anahtar] || karakter(anahtar, ajan && ajan !== "varsayilan" ? ajan : null, true);
      k.ayrildi = false;
    }
    k.isci = isci; d.isciler[isci] = k.anahtar;
    return k;
  }

  function aracKaydi(d, k, v) {
    const yol = v.args && typeof v.args === "object" ? String(v.args.path || v.args.yol || "") : "";
    k.sonAraclar.push({arac: String(v.arac || ""), masa: v.masa || "diger", yol, sira: d.sira});
    if (k.sonAraclar.length > SON_ARAC) k.sonAraclar.shift();
    if (yol && ["write_file", "edit_file"].includes(v.arac) && v.karar === "ALLOW" && !k.yazdiklari.includes(yol)) k.yazdiklari.push(yol);
    const mg = d.masaGecmisi[v.masa || "diger"] = d.masaGecmisi[v.masa || "diger"] || [];
    mg.push({anahtar: k.anahtar, arac: String(v.arac || ""), yol, sira: d.sira});
    if (mg.length > 10) mg.shift();
  }

  function kosuBitti(d, durdu) {
    Object.values(d.karakterler).forEach((k) => {
      if (["calisiyor", "dusunuyor", "planda_bekliyor", "onay_bekliyor"].includes(k.durum)) {
        /* bitis olayi gelmeden gorev bitti: ne oldugunu bilmiyoruz */
        k.durum = durdu || !SISTEM.includes(k.anahtar) ? "bilinmiyor" : "bosta";
      }
      if (k.gecici) { tasi(d, k, "kapi"); k.ayrildi = true; }
      k.isci = null;
    });
  }

  function durumUygula(durum, olay) {
    const d = kopya(durum);
    d.sira += 1;
    const tip = olay && olay.tip, v = (olay && olay.veri) || {}, zaman = olay && olay.zaman;
    const kar = (a) => d.karakterler[a];
    const bir = kar("@birlestirici"), plan = kar("@planlayici");
    const birlestiriyor = bir && bir.durum !== "bosta" && bir.durum !== "bitti" && d.kosu && !BITMIS_KOSU.includes(d.kosu.durum);

    if (tip === "_zaman") {
      Object.values(d.karakterler).forEach((k) => {
        if (["calisiyor", "dusunuyor"].includes(k.durum) && k.sonZaman && v.simdi - k.sonZaman > SESSIZLIK_MS) k.durum = "bilinmiyor";
      });
      return d;
    }

    if (tip === "ekip_mesaj" && v.rol) {
      const k = v.rol === "planlayici" ? plan : v.rol === "birlestirici" ? bir : null;
      if (k) {
        if (v.durum === "calisiyor") { tasi(d, k, "istisare"); k.durum = "calisiyor"; }
        else { tasi(d, k, "bekleme"); k.durum = v.rol === "birlestirici" ? "bitti" : "bosta"; }
        dokun(d, k, zaman);
      }
      return noktaAta(d);
    }
    if (tip === "ekip_mesaj" && v.durum) {
      if (v.durum === "planlaniyor" || !d.kosu) {
        /* yeni kosu: gecici kopyalar gider, herkes dinlenme alaninda bastan */
        Object.keys(d.karakterler).forEach((a) => { if (d.karakterler[a].gecici) delete d.karakterler[a]; });
        Object.values(d.karakterler).forEach((k) => {
          Object.assign(k, {isci: null, durum: "bosta", balon: null, zarf: 0, sonAraclar: [], yazdiklari: [], modelGecis: null});
          tasi(d, k, "bekleme");
        });
        d.isciler = {}; d.masaGecmisi = {};
        d.kosu = {kimlik: v.kimlik || null, durum: v.durum, tek: v.tek || null};
      }
      d.kosu.durum = v.durum; if (v.kimlik) d.kosu.kimlik = v.kimlik;
      if (v.durum === "bitti") kosuBitti(d, false);
      return noktaAta(d);
    }
    if (tip === "ekip_mesaj" && v.kimden) {
      /* pano mesaji: gonderen istisare masasina gider, ustunde balon */
      const gonderen = v.kimden === "kullanici" ? null : isciKarakteri(d, String(v.kimden), null);
      if (gonderen) {
        tasi(d, gonderen, "istisare");
        const metin = String(v.metin || "");
        gonderen.balon = {metin: metin.length > BALON_UZUNLUK ? metin.slice(0, BALON_UZUNLUK) + "…" : metin, tam: metin,
                          kime: v.kime || "herkes", sira: d.sira};
        dokun(d, gonderen, zaman);
      }
      if (v.kime && v.kime !== "herkes" && d.isciler[v.kime]) {
        const alici = kar(d.isciler[v.kime]); if (alici) alici.zarf += 1;
      }
      return noktaAta(d);
    }
    if (tip === "ekip_mesaj" && v.teslim && v.ajan) {
      const k = d.isciler[v.ajan] && kar(d.isciler[v.ajan]); if (k) k.zarf = 0;
      return d;
    }
    if (!d.kosu) return d;            /* kosu disindaki (tek ajanli sohbet) olaylar ofisi oynatmaz */

    if (tip === "onay_gerekli") {
      const istek = v.istek || {};
      if (istek.arac === "ekip_plan") {
        /* tek ajan gorevinde planlayici yok: kapida ajanin kendisi bekler */
        const k = (istek.args && istek.args.tek && kar(istek.args.tek)) || plan;
        tasi(d, k, "kapi"); k.durum = "onay_bekliyor"; d.kosu.durum = "onay_bekliyor"; dokun(d, k, zaman);
      }
      else if (birlestiriyor) { tasi(d, bir, "kapi"); bir.durum = "onay_bekliyor"; dokun(d, bir, zaman); }
      return noktaAta(d);
    }
    if (tip === "onay_sonucu") {
      if (v.arac === "ekip_plan") {
        const k = (d.kosu.tek && kar(d.kosu.tek)) || plan;
        tasi(d, k, "bekleme"); k.durum = "bosta";
        if (v.cevap === "red") { d.kosu.durum = "reddedildi"; kosuBitti(d, false); }
      } else if (bir.durum === "onay_bekliyor") { tasi(d, bir, "istisare"); bir.durum = "calisiyor"; }
      return noktaAta(d);
    }
    if (tip === "arac_cagrildi" && v.arac === "ekip_isci") {
      const args = typeof v.args === "object" && v.args ? v.args : {};
      const k = isciKarakteri(d, String(v.ajan || args.ad || ""), args.ajan);
      k.durum = "planda_bekliyor"; k.balon = null;
      if (!k.gecici) tasi(d, k, "bekleme");
      dokun(d, k, zaman);
      return noktaAta(d);
    }
    if (tip === "arac_cagrildi") {
      const k = v.ajan ? isciKarakteri(d, String(v.ajan), null) : birlestiriyor ? bir : null;
      if (!k) return d;
      /* planlayici ve birlestirici istisare masasinda calisir (3.1) */
      /* 'yerinde' (mkdir gibi hazirlik adimi): ajan oldugu masada kalir */
      const masa = v.masa === "yerinde" ? k.masa : (v.masa || "diger");
      if (k !== bir) tasi(d, k, masa);
      if (k.durum !== "onay_bekliyor") k.durum = "calisiyor";
      aracKaydi(d, k, Object.assign({}, v, {masa}));
      dokun(d, k, zaman);
      return noktaAta(d);
    }
    if (tip === "adim_basladi" || tip === "olcum") {
      const k = v.ajan ? isciKarakteri(d, String(v.ajan), null) : birlestiriyor ? bir : null;
      if (!k || ["bitti", "hata"].includes(k.durum)) return d;
      k.durum = tip === "adim_basladi" ? "dusunuyor" : "calisiyor";
      dokun(d, k, zaman);
      return d;
    }
    if (tip === "arac_sonucu" && v.arac === "ekip_isci") {
      const k = v.ajan && d.isciler[v.ajan] ? kar(d.isciler[v.ajan]) : null;
      if (!k) return d;
      k.durum = v.hata ? "hata" : "bitti"; k.isci = null;
      if (k.durum === "bitti") tasi(d, k, "bekleme");            /* hata: oldugu yerde, kirmizi rozet */
      dokun(d, k, zaman);
      return noktaAta(d);
    }
    if (tip === "model_gecis" && v.ajan) {
      const k = d.isciler[v.ajan] && kar(d.isciler[v.ajan]); if (k) k.modelGecis = {eski: v.eski || "", yeni: v.yeni || ""};
      return d;
    }
    if (tip === "hata") {
      const k = v.ajan ? (d.isciler[v.ajan] && kar(d.isciler[v.ajan])) : birlestiriyor ? bir : null;
      if (k) { k.durum = "hata"; dokun(d, k, zaman); }
      return d;
    }
    if (tip === "gorev_bitti") {
      if (!BITMIS_KOSU.includes(d.kosu.durum)) d.kosu.durum = v.durduruldu ? "hata" : "bitti";
      kosuBitti(d, !!v.durduruldu);
      return noktaAta(d);
    }
    return d;
  }

  /* Tek seferde bir olay dizisi (test ve gecmis oynatma icin). */
  function oynat(durum, olaylar) { return (olaylar || []).reduce(durumUygula, durum); }

  return {bos, durumUygula, oynat, ajanlariEsitle, SISTEM, BALON_UZUNLUK};
})();
