/* Local-only plugin shell and schema-backed forms. No HTML parsing of user data. */
"use strict";
window.PluginViews = {};
window.LocalPlugins = (() => {
  /* Ceviri koprusu: ana arayuzun t() fonksiyonu (index.html). Kaynak dil Turkce,
     CEVIRI.en sozlugu; yoksa metin aynen. Sozluk tablolari (labels/values)
     ARAMA noktasinda cevrilir ki dil degisince yeniden yuklemeye gerek olmasin. */
  const T = (s, p) => (typeof t === "function" ? t(s, p) : s);
  const state = {catalog:[], active:"today", tab:{}, workspace:null, noteId:null, timer:null, generation:0, drafts:new Map(), chatWorkspace:null, focus:null};
  let draftQueue=Promise.resolve(),draftsLoaded=false,draftsLoading=null;
  class Drafts extends Map {
    set(id,value){super.set(id,value);this.persist(id,value);return this;}
    delete(id){const existed=super.delete(id);if(existed)this.persist(id,null);return existed;}
    persist(id,value){
      try{localStorage.setItem("pevrai.not-taslaklari",JSON.stringify([...this]));}catch(e){error(new Error(T("Taslak bu cihazda kaydedilemedi.")));}
      const snapshot=value?{...value}:null;
      draftQueue=draftQueue.then(async()=>{const r=await window.pywebview.api.not_taslak_yaz(id,snapshot);if(!r?.ok)throw new Error(r?.hata||T("Taslak bu cihazda kaydedilemedi."));}).catch(error);
    }
  }
  state.drafts=new Drafts();
  try{for(const [id,draft] of JSON.parse(localStorage.getItem("pevrai.not-taslaklari")||"[]"))Map.prototype.set.call(state.drafts,id,draft);}catch(e){}
  async function loadDrafts(){if(draftsLoaded)return;if(draftsLoading)return draftsLoading;draftsLoading=(async()=>{await draftQueue;const r=await window.pywebview.api.not_taslaklari();if(!r?.ok)throw new Error(r?.hata||T("Taslaklar okunamadı."));for(const [id,draft] of Object.entries(r.taslaklar||{}))if(!state.drafts.has(id))Map.prototype.set.call(state.drafts,id,draft);draftsLoaded=true;})();try{await draftsLoading;}finally{draftsLoading=null;}}
  const node = (tag, cls, value) => { const n=document.createElement(tag); if(cls)n.className=cls; if(value!==undefined)n.textContent=String(value); return n; };
  const clear = n => n.replaceChildren();
  const paths = {
    brain:["M12 4v16M12 5C9 0 4 3 5 7C1 8 2 13 4 14C2 19 7 23 10 20L12 18M12 5C15 0 20 3 19 7C23 8 22 13 20 14C22 19 17 23 14 20L12 18","M5 7l3 2M4 14l4-1M19 7l-3 2M20 14l-4-1"],
    book:["M12 5v16M12 5C8 2 4 3 2 4v15c4-2 7-1 10 2c3-3 6-4 10-2V4c-2-1-6-2-10 1"],
    calendar:["M4 5h16v16H4zM8 2v6M16 2v6M4 10h16M8 14h2M14 14h2M8 18h2"],
    play:["M8 4l12 8-12 8z"], pause:["M8 5v14M16 5v14"],
    edit:["M15 4l5 5M4 20l5-1L21 7a2 2 0 00-5-5L4 15z"],
    link:["M10 13a5 5 0 007 0l4-4a5 5 0 00-7-7l-3 3M14 11a5 5 0 00-7 0l-4 4a5 5 0 007 7l3-3"],
    network:["M12 9V5M9 13l-5 4M15 13l5 4M15 11l5-5M9 11L4 6","M12 9a3 3 0 100 6 3 3 0 000-6M12 1a2 2 0 100 4 2 2 0 000-4M3 3a2 2 0 100 4 2 2 0 000-4M21 3a2 2 0 100 4 2 2 0 000-4M3 17a2 2 0 100 4 2 2 0 000-4M21 17a2 2 0 100 4 2 2 0 000-4"],
    target:["M12 2a10 10 0 100 20 10 10 0 000-20M12 6a6 6 0 100 12 6 6 0 000-12M12 10a2 2 0 100 4 2 2 0 000-4"],
    archive:["M3 3h18v5H3zM5 8v13h14V8M10 12h4"],
    sun:["M12 8a4 4 0 100 8 4 4 0 000-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1"]
  };
  function icon(name,size=18){
    if(!paths[name])return ikon(name,size);
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    for(const [key,value] of Object.entries({viewBox:"0 0 24 24",width:size,height:size,fill:"none",stroke:"currentColor","stroke-width":1.7,"stroke-linecap":"round","stroke-linejoin":"round","aria-hidden":"true"}))svg.setAttribute(key,value);
    for(const d of paths[name]){const p=document.createElementNS(svg.namespaceURI,"path");p.setAttribute("d",d);svg.append(p);}return svg;
  }
  function buttonIcon(label){
    if(label.startsWith("+"))return "yeni";
    for(const [name,labels] of Object.entries({edit:["Düzenle","Projeyi düzenle"],cop:["Sil"],archive:["Arşivle","Arşivden çıkar"],degisiklik:["Geçmiş / geri al","Geçmiş","Bu sürümü geri yükle"],link:["Not bağla","İlişki ekle","Mevcut not bağla","Dosya / çıktı bağla"],play:["Odak başlat","Devam et","Çalışmaya başla","Bu göreve odaklan"],pause:["Duraklat"],dur:["Bitir"],onay:["Kaydet","Tamamla"],ret:["Vazgeç","Kaldır","Bağlantıyı kaldır"],konusma:["Sohbete dön","Sohbette devam et"],dosya:["Yeni not","Hızlı not","Proje notu oluştur"],ok:["Sonraki","Projeyi aç","Bağlı notu aç"],geri:["Önceki","← Projeler","Notlara dön"],ayarlar:["Yenile","Devre dışı bırak"]}))if(labels.some(x=>T(x)===label))return name;
    return null;
  }
  const button = (title, action, cls="", symbol=null) => {
    const b=node("button","ep-button "+cls);b.type="button";
    const i=symbol||buttonIcon(title);if(i)b.append(icon(i));b.append(node("span","",i==="yeni"?title.replace(/^\+\s*/,""):title));if(title.startsWith("+"))b.setAttribute("aria-label",title);
    b.addEventListener("click",async()=>{b.disabled=true;try{await action();}catch(e){error(e);}finally{b.disabled=false;}});return b;
  };
  function error(e) { if(typeof toast==="function") toast(e.message||String(e),"kotu"); }
  async function call(name,args={}) { const r=await window.pywebview.api.eklenti_cagir(name,args); if(!r.ok)throw new Error(r.hata);if(name.startsWith("focus_"))updateFocus(r.result);return r.result; }
  const can = name => state.catalog.some(p=>p.enabled&&p.tools.some(t=>t.name===name));
  const spec = name => state.catalog.flatMap(p=>p.tools).find(t=>t.name===name);
  const card = (parent,title,symbol=null) => {const c=node("section","ep-card");if(title){const h=node("h3","",title);if(symbol)h.prepend(icon(symbol));c.append(h);}parent.append(c);return c;};
  const actions = parent => {const a=node("div","ep-actions");parent.append(a);return a;};
  const muted = (parent,text) => parent.append(node("p","ep-muted",text));
  const datetime = value => value ? new Date(value).toLocaleString(document.documentElement.lang||undefined) : "";
  const title = row => row.name||row.title||row.message||row.date||T("Kayıt");
  const labels={name:"Ad",title:"Başlık",description:"Açıklama",at:"Sınav tarihi ve saati",course_id:"Ders",exam_id:"Sınav",topic_id:"Konu",workspace_id:"Proje",note_id:"Not",target_id:"Bağlanacak not",progress:"İlerleme (%)",difficulty:"Zorluk (1–5)",note:"Not",minutes:"Süre (dakika)",date:"Tarih",status:"Durum",priority:"Öncelik",body:"Not metni",tags:"Etiketler (virgülle ayır)",references:"İlişkiler",archived:"Arşivlendi",root:"Proje klasörü",instructions:"Amaç ve proje talimatları",summary:"Devam özeti",next_steps:"Sonraki adımlar (her satıra bir adım)",mode:"Odak türü",work_minutes:"Çalışma süresi (dakika)",break_minutes:"Mola süresi (dakika)",rounds:"Tur sayısı",start:"Başlangıç",end:"Bitiş",type:"Çalışma türü",completed:"Tamamlandı",path:"Dosya veya klasör yolu",kind:"Tür",label:"Görünen ad",message:"Çalışma günlüğü",category:"Kategori",remove:"Bağlantıyı kaldır"};
  const values={low:"Düşük",normal:"Normal",high:"Yüksek",upcoming:"Yaklaşan",completed:"Tamamlandı",cancelled:"İptal",planned:"Planlandı",skipped:"Atlandı",todo:"Yapılacak",in_progress:"Devam ediyor",blocked:"Engellendi",pomodoro:"Pomodoro",free:"Serbest odak",study:"Çalışma",review:"Tekrar",practice:"Alıştırma",file:"Dosya",folder:"Klasör",artifact:"Çıktı",progress:"İlerleme",decision:"Karar",blocker:"Engel",output:"Çıktı",course:"Ders",exam:"Sınav",topic:"Konu",workspace:"Proje",task:"Görev",note:"Not"};
  const human = x => T(values[x]||x);
  const kindIcon = {course:"book",exam:"calendar",topic:"fikir",workspace:"klasor",task:"onay",note:"dosya"};
  function more(parent,items){const d=node("details","ep-more"),s=node("summary");s.setAttribute("aria-label",T("Diğer işlemler"));s.title=T("Diğer işlemler");s.append(icon("nokta3"));d.append(s);const menu=node("div","ep-more-menu");for(const [label,fn,symbol] of items)menu.append(button(label,async()=>{d.open=false;await fn();},"",symbol));d.append(menu);d.addEventListener("keydown",e=>{if(e.key==="Escape"){d.open=false;s.focus();}});parent.append(d);return d;}
  function empty(parent,symbol,heading,description,action){const e=node("div","ep-empty");e.append(icon(symbol,32),node("h3","",T(heading)),node("p","ep-muted",T(description)));if(action)e.append(button(T(action[0]),action[1],"ep-primary","yeni"));parent.append(e);}
  async function navigate(active,tab=null,id=null){state.active=active;if(tab)state.tab[active]=tab;if(id&&active==="workspace")state.workspace=id;if(id&&active==="notes")state.noteId=id;open();}
  async function openReference(ref){
    if(ref.type==="workspace")return navigate("workspace","tasks",ref.id);
    if(ref.type==="note")return navigate("notes","active",ref.id);
    if(ref.type==="task"){const task=await call("task_get",{id:ref.id});return navigate("workspace","tasks",task.workspace_id);}
    const row=await call(ref.type+"_get",{id:ref.id});return edit(ref.type,row);
  }
  async function references(parent,refs,center=null){
    if(!refs?.length)return;
    const area=node("div","ep-connections");if(center){const label=node("div","ep-connection-center");label.append(icon("network"),node("span","",center));area.append(label);}
    parent.append(area);
    await Promise.all(refs.slice(0,30).map(async ref=>{const item=node("div","ep-connection");area.append(item);try{const row=await call(ref.type+"_get",{id:ref.id});const b=button(title(row),()=>openReference(ref),"ep-chip ep-kind-"+ref.type,kindIcon[ref.type]);b.title=human(ref.type)+": "+title(row);item.append(b);}catch(e){const b=node("span","ep-chip ep-unavailable",human(ref.type)+" · "+T("Erişilemiyor"));b.title=e.message;item.append(b);}}));
    if(refs.length>30)muted(area,T("Diğer bağlantıları düzenleme ekranından görebilirsin."));
  }
  async function quickNote(body=""){
    if(!can("note_create")){await navigate("notes");return;}
    const inPlugins=document.getElementById("eklentiler-gorunum").classList.contains("acik");
    const workspace=inPlugins?(state.active==="workspace"&&state.workspace?await call("workspace_get",{id:state.workspace}):null):state.chatWorkspace;
    const seed={body,...(workspace?{references:[{type:"workspace",id:workspace.id}]}:{})};
    await form("note_create",T("Hızlı not")+(workspace?" · "+workspace.name:""),seed,{},async note=>{
      if(workspace&&can("workspace_note_link")){try{const w=await call("workspace_get",{id:workspace.id});await call("workspace_note_link",{id:w.id,note_id:note.id,expected_revision:w.revision});}catch(e){error(e);}}
      state.noteId=note.id;toast(T("Not kaydedildi"),"iyi");if(document.getElementById("eklentiler-gorunum").classList.contains("acik"))await refresh();
    });
  }
  async function continueChat(workspace){const r=await window.pywebview.api.sohbet_projesi(workspace.id);if(!r?.ok)throw new Error(r?.hata);state.chatWorkspace=r.proje_baglami||{id:workspace.id,name:workspace.name};renderChatContext();gorunum("sohbet");document.getElementById("girdi").focus();}
  function chatContext(value,id,reset=false){if(id!==state.chatId||reset){state.chatId=id;state.chatWorkspace=value;renderChatContext();}else if(value?.id!==state.chatWorkspace?.id){state.chatWorkspace=value;renderChatContext();}}
  function renderChatContext(){const bar=document.getElementById("ep-chat-context");clear(bar);bar.hidden=!state.chatWorkspace;if(!state.chatWorkspace)return;bar.append(icon("klasor"),node("span","",state.chatWorkspace.name),button(T("Projeyi aç"),()=>navigate("workspace","tasks",state.chatWorkspace.id),"ep-quiet","ok"),button(T("Bağlantıyı kaldır"),async()=>{const r=await window.pywebview.api.sohbet_projesi(null);if(!r?.ok)throw new Error(r?.hata);state.chatWorkspace=null;renderChatContext();},"ep-quiet","ret"));}
  async function chatPrompt(text){
    if(!state.chatWorkspace)return text;
    const w={...state.chatWorkspace},context=await call("workspace_context",{id:w.id,limit:10});
    if(state.chatWorkspace?.id!==w.id)throw new Error(T("Proje seçimi değişti; mesajı yeniden gönder."));
    function bounded(v){if(typeof v==="string")return v.slice(0,4000);if(Array.isArray(v))return v.slice(0,20).map(bounded);if(v&&typeof v==="object")return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,bounded(x)]));return v;}
    const payload=JSON.stringify(bounded(context)).replace(/</g,"\\u003c").replace(/>/g,"\\u003e");
    return text+"\n\n"+T("İlgili proje: ")+"\n<untrusted_content source=\"workspace\">\n"+payload+"\n</untrusted_content>";
  }
  function timeText(f){const seconds=Math.max(0,Math.ceil(f.mode==="free"?f.work_seconds||0:f.remaining_seconds||0));return String(Math.floor(seconds/60)).padStart(2,"0")+":"+String(seconds%60).padStart(2,"0");}
  function placeFocus(){const dock=document.getElementById("ep-focus-dock");if(!dock)return;const target=document.getElementById("dip").style.display==="none"?document.body:document.querySelector("#dip .kolon");if(dock.parentElement!==target)target.prepend(dock);}
  function updateFocus(f){if(!f||!f.status)return;state.focus=f;const dock=document.getElementById("ep-focus-dock");if(!dock)return;const active=["active","paused"].includes(f.status);dock.hidden=!active;if(!active){clear(dock);return;}
    const key=f.id+f.status+f.phase;if(dock.dataset.key!==key){dock.dataset.key=key;clear(dock);dock.append(icon("target"),node("span","ep-dock-time"));dock.append(button(f.status==="paused"?T("Devam et"):T("Duraklat"),()=>call(f.status==="paused"?"focus_resume":"focus_pause",{id:f.id}),"ep-quiet",f.status==="paused"?"play":"pause"),button(T("Odak"),()=>navigate("study","focus"),"ep-quiet","ok"));}dock.querySelector(".ep-dock-time").textContent=(f.status==="paused"?T("Duraklatıldı"):f.phase==="break"?T("Mola"):T("Odak"))+" · "+timeText(f);
  }
  let heartbeatBusy=false;
  async function heartbeat(){if(heartbeatBusy||!window.pywebview?.api)return;heartbeatBusy=true;try{if(!state.catalog.length){const c=await window.pywebview.api.eklenti_katalog();state.catalog=c.plugins||[];}if(can("focus_status"))await call("focus_status");else{state.focus=null;document.getElementById("ep-focus-dock").hidden=true;}}catch(e){const dock=document.getElementById("ep-focus-dock");if(dock&&!dock.hidden)dock.title=T("Sayaç güncellenemedi");}finally{heartbeatBusy=false;}}
  async function options(kind) {
    const name=kind+"_list";
    if(!can(name))return [];
    const all=[];
    for(let offset=0;offset<1000;offset+=100){const r=await call(name,{limit:100,offset});all.push(...r.items);if(all.length>=r.total)break;}
    return all;
  }
  function selectOptions(select, rows, selected, optional=true) {
    clear(select);if(optional){const o=node("option","",T("Seçilmedi"));o.value="";select.append(o);}
    for(const r of rows){const o=node("option","",title(r));o.value=r.id;select.append(o);}
    if(selected&&!rows.some(r=>r.id===selected)){const o=node("option","",T("Erişilemeyen kayıt: ")+selected);o.value=selected;select.append(o);}
    select.value=selected||"";
  }
  async function referenceEditor(seed) {
    const box=node("div"), rows=[];
    async function add(ref={type:"course",id:""}) {
      const line=node("div","ep-reference"),kind=node("select"),id=node("select");
      for(const v of ["course","exam","topic","workspace","task","note"]){const o=node("option","",human(v));o.value=v;kind.append(o);}kind.value=ref.type;
      await fill(ref.id);kind.addEventListener("change",()=>fill(""));
      async function fill(value){selectOptions(id,await options(kind.value),value);}
      const entry={line,kind,id};rows.push(entry);line.append(kind,id,button(T("Kaldır"),()=>{line.remove();rows.splice(rows.indexOf(entry),1);}));box.insertBefore(line,addButton);
    }
    const addButton=button(T("İlişki ekle"),()=>add());box.append(addButton);
    for(const ref of seed||[])await add(ref);
    return {input:box,read:()=>rows.filter(r=>r.id.value).map(r=>({type:r.kind.value,id:r.id.value}))};
  }
  async function form(name, heading, seed={}, hidden={}, after=refresh) {
    const tool=spec(name);if(!tool)throw new Error(T("Bu işlem etkin değil."));
    const overlay=node("div","ep-dialog"),f=node("form","ep-form");f.setAttribute("role","dialog");f.setAttribute("aria-modal","true");f.setAttribute("aria-label",heading);overlay.append(f);f.append(node("h3","",heading));
    const readers={}, controls={};
    const extras=node("details","ep-form-options");extras.append(node("summary","",T("Diğer ayrıntılar")));
    for(const [key,schema] of Object.entries(tool.parameters.properties)){
      if(key in hidden||key==="expected_revision"||key==="id")continue;
      const label=node("label","ep-field"),caption=node("span","",T(labels[key]||schema.description||key));label.append(caption);
      let input,read;
      const required=tool.parameters.required.includes(key);
      if(key==="references") {const editor=await referenceEditor(seed[key]);input=editor.input;read=editor.read;}
      else if(schema.enum){input=node("select");if(!required){const o=node("option","",T("Varsayılan"));o.value="";input.append(o);}for(const value of schema.enum){const o=node("option","",human(value));o.value=value;input.append(o);}input.value=seed[key]??"";read=()=>input.value||undefined;}
      else if(key.endsWith("_id")){input=node("select");const kind={target:"note"}[key.slice(0,-3)]||key.slice(0,-3);selectOptions(input,await options(kind),seed[key],!required);read=()=>input.value||undefined;}
      else if(schema.type==="boolean"){input=node("input");input.type="checkbox";input.checked=seed[key]??false;read=()=>input.checked;}
      else if(schema.type==="array"){input=node("textarea");input.value=(seed[key]||[]).join(key==="tags"?", ":"\n");read=()=>input.value.split(key==="tags"?",":"\n").map(s=>s.trim()).filter(Boolean);}
      else if(schema.type==="integer"){input=node("input");input.type="number";input.min=schema.minimum;input.max=schema.maximum;input.step=1;input.value=seed[key]??"";read=()=>input.value===""?undefined:Number(input.value);}
      else if(schema.format==="date-time"){input=node("input");input.type="datetime-local";if(seed[key]){const date=new Date(seed[key]);input.value=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}read=()=>input.value?new Date(input.value).toISOString():undefined;caption.append(node("small","ep-muted",T(" (yerel saat)")));}
      else if(schema.format==="date"){input=node("input");input.type="date";input.value=seed[key]||"";read=()=>input.value||undefined;}
      else {input=node(schema.maxLength>2000?"textarea":"input");input.value=seed[key]??"";input.maxLength=schema.maxLength||10000;if(key==="body")input.className="ep-editor";read=()=>input.value;}
      if(required&&input.tagName!=="DIV")input.required=true;
      input.setAttribute("aria-label",T(labels[key]||schema.description||key));
      controls[key]=input;readers[key]=read;label.append(input);
      const primary=required||["title","body","name","root","status","progress","mode","work_minutes","break_minutes","rounds"].includes(key);
      (primary?f:extras).append(label);
    }
    if(extras.children.length>1)f.append(extras);
    const err=node("p","ep-error");err.setAttribute("role","alert");f.append(err);
    const a=actions(f),save=node("button","ep-button ep-primary");save.append(icon("onay"),node("span","",T("Kaydet")));save.type="submit";a.append(save,button(T("Vazgeç"),close));
    const previous=document.activeElement;
    function close(){overlay.remove();previous?.focus();}
    overlay.addEventListener("keydown",e=>{if(e.key==="Escape")close();if(e.key==="Tab"){const all=[...f.querySelectorAll("input,select,textarea,button,summary")].filter(n=>!n.disabled&&n.getClientRects().length);if(e.shiftKey&&document.activeElement===all[0]){e.preventDefault();all.at(-1).focus();}else if(!e.shiftKey&&document.activeElement===all.at(-1)){e.preventDefault();all[0].focus();}}});
    f.addEventListener("submit",async e=>{e.preventDefault();save.disabled=true;err.textContent="";try{const args={...hidden};for(const [key,read] of Object.entries(readers)){const value=read();if(value!==undefined)args[key]=value;}const result=await call(name,args);close();await after(result);}catch(ex){err.textContent=ex.message;}finally{save.disabled=false;}});
    document.body.append(overlay);f.querySelector("input,select,textarea,button")?.focus();
  }
  async function edit(kind,row,after=refresh,hide={}) {
    const fresh=await call(kind+"_get",{id:row.id});
    return form(kind+"_update",T("Düzenle: ")+title(fresh),fresh,{id:fresh.id,expected_revision:fresh.revision,...hide},after);
  }
  function confirmAction(heading,action) {
    const overlay=node("div","ep-dialog"),box=node("div","ep-form");box.setAttribute("role","alertdialog");overlay.append(box);box.append(node("h3","",heading));muted(box,T("Kayıt silindi olarak işaretlenecek; geçmiş korunur."));const a=actions(box);a.append(button(T("Sil"),async()=>{await action();overlay.remove();}),button(T("Vazgeç"),()=>overlay.remove()));document.body.append(overlay);
  }
  function remove(kind,row,after=refresh){confirmAction(title(row)+T(" silinsin mi?"),async()=>{await call(kind+"_delete",{id:row.id,expected_revision:row.revision});await after();});}
  async function listing(parent,kind,heading,filters={},detail=null,seed={}) {
    const top=actions(parent);top.append(button("+ "+heading,()=>form(kind+"_create",heading+T(" oluştur"),seed,filters)));
    const box=card(parent,heading),page={offset:0};
    async function load(){clear(box);const r=await call(kind+"_list",{...filters,limit:20,offset:page.offset});if(!r.items.length)muted(box,T("Henüz kayıt yok."));
      for(const row of r.items){const line=node("div","ep-row"),heading=node("div","ep-row-heading");heading.append(icon(kindIcon[kind]||"calendar"),node("strong","",title(row)));line.append(heading);if(detail)await detail(line,row);const a=actions(line);a.append(button(T("Düzenle"),()=>edit(kind,row,load,filters),"ep-quiet"));more(a,[[T("Sil"),()=>remove(kind,row,load),"cop"]]);box.append(line);}
      const pages=actions(box);muted(pages,`${Math.min(page.offset+r.items.length,r.total)} / ${r.total}`);if(page.offset)pages.append(button(T("Önceki"),()=>{page.offset-=20;return load();}));if(page.offset+20<r.total)pages.append(button(T("Sonraki"),()=>{page.offset+=20;return load();}));
    }await load();return {load,box};
  }
  function tabs(parent,items,selected,onSelect){const nav=node("div","ep-tabs");nav.setAttribute("role","tablist");const icons={today:"sun",focus:"target",courses:"book",exams:"calendar",topics:"fikir",plans:"calendar",history:"degisiklik",tasks:"onay",files:"klasor",notes:"dosya",log:"degisiklik",active:"dosya",archived:"archive",deleted:"cop"};for(const [key,label,symbol] of items){const b=button(label,()=>onSelect(key),"",symbol||icons[key]);b.setAttribute("aria-selected",String(key===selected));b.setAttribute("role","tab");nav.append(b);}parent.append(nav);}
  async function refresh(){
    await loadDrafts();
    if(state.timer){clearInterval(state.timer);state.timer=null;}
    const host=document.getElementById("eklentiler-gorunum");if(!host)return;
    const generation=++state.generation;
    const c=await window.pywebview.api.eklenti_katalog();if(!c.ok)throw new Error(c.hata);
    if(generation!==state.generation||!host.classList.contains("acik"))return;
    state.catalog=c.plugins;
    clear(host);const shell=node("div","ep-shell"),side=node("aside","ep-sidebar"),main=node("div","ep-main");host.append(shell);shell.append(side,main);
    const brand=node("div","ep-brand");brand.append(icon("brain",27),node("strong","",T("Çalışma")));side.append(brand);muted(side,T("Düşün. Bağla. İlerle."));
    const routes=[["today",T("Bugün"),"sun"],["study","Study & Focus","book"],["notes","Smart Notes","dosya"],["workspace","Workspace","klasor"],["connections",T("Bağlantılar"),"network"]];
    tabs(side,routes,state.active,key=>{state.active=key;return refresh();});
    const foot=node("div","ep-sidebar-foot");foot.append(icon("kalkan",14),node("span","",T("Sana ait. Bu cihazda.")));side.append(foot);
    const plugin=state.catalog.find(p=>p.id===state.active),route=routes.find(r=>r[0]===state.active);
    const head=node("div","ep-head"),heading=node("div");heading.append(node("div","ep-eyebrow",T("KİŞİSEL ÇALIŞMA ALANIN")),node("h2","",route?.[1]||T("Çalışma")));head.append(heading);
    const controls=actions(head);if(can("note_create"))controls.append(button(T("Hızlı not"),()=>quickNote(),"ep-quiet","yeni"));controls.append(button(T("Sohbete dön"),()=>gorunum("sohbet"),"ep-quiet","konusma"));
    const menu=[[T("Yenile"),refresh,"degisiklik"]];if(plugin?.enabled)menu.push([T("Devre dışı bırak"),async()=>{const r=await window.pywebview.api.eklenti_ayarla(plugin.id,false);if(!r.ok)throw new Error(r.hata);await refresh();await heartbeat();},"dur"]);more(controls,menu);main.append(head);
    if(plugin&&!plugin.enabled){const c=card(main,plugin.name,{study:"book",notes:"dosya",workspace:"klasor"}[plugin.id]);muted(c,T(plugin.description));muted(c,T("Veriler bu cihazda saklanır. Temel işlemler model çağrısı gerektirmez."));if(plugin.available)actions(c).append(button(T("Etkinleştir"),async()=>{const r=await window.pywebview.api.eklenti_ayarla(plugin.id,true);if(!r.ok)throw new Error(r.hata);await refresh();},"ep-primary","yeni"));else muted(c,plugin.error||T("Eklenti dosyaları kurulu değil."));return;}
    const body=node("div","ep-content");main.append(body);
    try{
      const render=window.PluginViews[state.active];
      if(typeof render!=="function")throw new Error(T("Bu eklentinin arayüz dosyası yüklenemedi. Uygulamayı yeniden başlatın; sorun sürerse kurulumu güncelleyin."));
      await render(body);
    }catch(e){if(generation===state.generation)body.append(node("p","ep-error",e.message));}
  }
  function open(){if(!yanSabit){clearTimeout(yanZaman);yan.classList.remove("acik");}gorunum("eklentiler");refresh().catch(error);}
  document.getElementById("ray-eklentiler").addEventListener("click",open);
  document.getElementById("ray-eklentiler").replaceChildren(icon("brain",21));
  const dock=node("div","ep-focus-dock");dock.id="ep-focus-dock";dock.hidden=true;document.body.append(dock);
  const chat=node("div","ep-chat-context");chat.id="ep-chat-context";chat.hidden=true;document.querySelector("#dip .kolon").prepend(chat);
  placeFocus();
  window.addEventListener("pywebviewready",heartbeat);setInterval(heartbeat,2000);
  window.addEventListener("pevrai-languagechange",()=>{renderChatContext();dock.dataset.key="";if(state.focus)updateFocus(state.focus);if(document.getElementById("eklentiler-gorunum").classList.contains("acik"))refresh().catch(error);});
  return {state,node,clear,button,call,can,card,actions,muted,datetime,title,labels,human,options,form,edit,remove,listing,tabs,refresh,error,T,icon,more,empty,navigate,references,openReference,kindIcon,quickNote,continueChat,chatPrompt,chatContext,timeText,placeFocus};
})();
