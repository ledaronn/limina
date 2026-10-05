"use strict";
window.PluginViews.notes = async function(host) {
  const P=LocalPlugins,T=P.T,{node,button,call,card,actions,muted,state}=P;
  const mode=state.tab.notes||"active";
  const toolbar=actions(host);
  toolbar.append(button(T("+ Yeni not"),()=>P.form("note_create",T("Yeni not"),{},{},async note=>{state.noteId=note.id;await P.refresh();}),"ep-primary","yeni"));
  P.tabs(host,[["active",T("Notlar")],["archived",T("Arşiv")],["deleted",T("Silinenler")]],mode,key=>{state.tab.notes=key;state.noteId=null;return P.refresh();});
  const split=node("div","ep-split"),sidebar=node("div","ep-list-pane"),editor=node("section","ep-editor-pane");
  split.append(sidebar,editor);host.append(split);
  const search=node("input","ep-search");search.type="search";search.placeholder=T("Notlarında ara");search.setAttribute("aria-label",T("Notlarında ara"));
  const list=node("div","ep-note-list"),pager=actions(sidebar);sidebar.prepend(search,list);
  let offset=0,request=0,selection=0;
  async function history(note) {
    const ticket=++selection;P.clear(editor);const top=actions(editor);
    top.append(button(T("Notlara dön"),()=>select(note.id),"ep-quiet","geri"));
    editor.append(node("h3","",T("Değişiklik geçmişi")));
    const result=await call("note_history",{id:note.id,limit:50});if(ticket!==selection)return;
    const versions=node("select","ep-select");versions.setAttribute("aria-label",T("Karşılaştırılacak sürüm"));
    for(const version of result.items){const option=node("option","","#"+version.revision+" · "+P.datetime(version.updated_at)+" · "+(version.change_source==="ai"?T("Asistan"):T("Sen")));option.value=version.revision;versions.append(option);}
    editor.append(versions);
    const comparison=node("div","ep-compare");editor.append(comparison);
    const controls=actions(editor);
    function compare(){P.clear(comparison);P.clear(controls);const chosen=result.items.find(v=>String(v.revision)===versions.value),previous=result.items.find(v=>v.revision===chosen.revision-1);
      for(const [label,version] of [[T("Önce"),previous],[T("Sonra"),chosen]]){const c=card(comparison,label);c.append(node("strong","",version?.title||"—"),node("pre","ep-diff",version?.body||""));if(version?.tags?.length)muted(c,version.tags.join(", "));}
      if(chosen.revision!==note.revision||note.deleted)controls.append(button(T("Bu sürümü geri yükle"),async()=>{const latest=await call("note_get",{id:note.id,include_deleted:true});await call("note_restore",{id:note.id,revision:chosen.revision,expected_revision:latest.revision});state.drafts.delete(note.id);state.tab.notes="active";await P.refresh();},"ep-primary","geri"));
    }
    versions.addEventListener("change",compare);compare();
    if(result.total>50)muted(editor,T("En son 50 sürüm gösteriliyor."));
  }
  async function select(id) {
    const ticket=++selection;state.noteId=id;
    for(const b of list.querySelectorAll("[data-note-id]"))b.setAttribute("aria-pressed",String(b.dataset.noteId===id));
    const note=await call("note_get",{id,include_deleted:mode==="deleted"});if(ticket!==selection||!editor.isConnected)return;
    P.clear(editor);
    const meta=node("div","ep-editor-meta");meta.append(P.icon("dosya"),node("span","ep-muted",P.datetime(note.updated_at)));
    if(note.change_source==="ai"){const badge=node("span","ep-ai-badge");badge.append(P.icon("derin",14),node("span","",T("Asistan düzenledi")));meta.append(badge);}
    P.more(meta,[
      [T("Geçmiş / geri al"),()=>history(note),"degisiklik"],
      ...(!note.deleted?[
        [T("Etiketler ve bağlantılar"),()=>P.edit("note",note,()=>select(note.id)),"link"],
        [T("Not bağla"),()=>P.form("note_link",T("Not bağlantısı"),{},{id:note.id,expected_revision:note.revision},()=>select(note.id)),"link"],
        [note.archived?T("Arşivden çıkar"):T("Arşivle"),async()=>{await call("note_archive",{id:note.id,archived:!note.archived,expected_revision:note.revision});state.noteId=null;await load();},"archive"],
        [T("Sil"),()=>P.remove("note",note,async()=>{state.drafts.delete(note.id);state.noteId=null;await load();}),"cop"]
      ]:[])
    ]);editor.append(meta);
    if(note.deleted){editor.append(node("h2","",note.title),node("p","ep-body",note.body||""));actions(editor).append(button(T("Geçmiş / geri al"),()=>history(note),"ep-primary","geri"));return;}
    const draft=state.drafts.get(id),titleInput=node("input","ep-note-title"),bodyInput=node("textarea","ep-note-body");
    titleInput.value=draft?.title??note.title;titleInput.maxLength=500;titleInput.setAttribute("aria-label",T("Başlık"));
    bodyInput.value=draft?.body??note.body??"";bodyInput.maxLength=50000;bodyInput.placeholder=T("Düşünceni buraya bırak…");bodyInput.setAttribute("aria-label",T("Not metni"));
    const status=node("span","ep-muted"),bottom=node("div","ep-editor-bottom");
    const save=button(T("Kaydet"),async()=>{
      if(!titleInput.value.trim()){titleInput.focus();throw new Error(T("Başlık boş olamaz."));}
      titleInput.disabled=true;bodyInput.disabled=true;
      try{const updated=await call("note_update",{id,expected_revision:state.drafts.get(id)?.baseRevision??note.revision,title:titleInput.value,body:bodyInput.value});
        state.drafts.delete(id);await load(updated.id);
      }finally{titleInput.disabled=false;bodyInput.disabled=false;}
    },"ep-primary","onay");
    function changed(){const dirty=titleInput.value!==note.title||bodyInput.value!==(note.body||"");
      if(dirty)state.drafts.set(id,{title:titleInput.value,body:bodyInput.value,baseRevision:state.drafts.get(id)?.baseRevision??note.revision});else state.drafts.delete(id);
      status.textContent=dirty?T("Kaydedilmemiş değişiklikler"):T("Kaydedildi");save.disabled=!dirty;
    }
    titleInput.addEventListener("input",changed);bodyInput.addEventListener("input",changed);
    bodyInput.addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key==="s"){e.preventDefault();if(!save.disabled)save.click();}});
    bottom.append(status,button(T("Değişiklikleri bırak"),async()=>{state.drafts.delete(id);await select(id);},"ep-quiet","geri"),save);editor.append(titleInput,bodyInput);
    if(note.tags?.length){const tags=node("div","ep-tags");for(const tag of note.tags)tags.append(node("span","ep-chip","#"+tag));editor.append(tags);}
    const refs=[...(note.references||[]),...(note.links||[]).map(id=>({type:"note",id}))];
    if(refs.length)await P.references(editor,refs,T("Bu düşünce şunlara bağlı"));
    else {const box=node("div","ep-note-connect");box.append(P.icon("network"),node("span","ep-muted",T("Bir ders veya projeyle bağla.")),button(T("Bağlantı ekle"),()=>P.edit("note",note,()=>select(id)),"ep-quiet","link"));editor.append(box);}
    editor.append(bottom);changed();
    const sources=[...new Set((note.body||"").match(/okuma:\/\/[a-f0-9]{24}\/[a-f0-9]{32}\/[1-9][0-9]{0,5}/g)||[])];
    if(sources.length){const links=actions(editor);for(const uri of sources.slice(0,10))links.append(button(T("Kaynak sayfasını aç"),async()=>{const r=await window.pywebview.api.okuma_kaynak_ac(uri);if(!r.ok)throw new Error(r.hata);},"ep-quiet","book"));}
  }
  async function load(preferred=null) {
    const sequence=++request,query=search.value.trim();
    const result=query?await call("note_search",{query,scope:mode,limit:30,offset}):await call("note_list",{limit:30,offset,...(mode==="deleted"?{include_deleted:true,deleted:true}:{archived:mode==="archived"})});
    if(sequence!==request||!list.isConnected)return;P.clear(list);P.clear(pager);
    if(!result.items.length){P.clear(editor);P.empty(editor,"fikir","Düşüncelerine yer aç.","Bir not yaz; sonra derslerinle ve projelerinle bağla.",["İlk notunu yaz",()=>P.quickNote()]);}
    for(const note of result.items){const b=button("",()=>select(note.id),"ep-note-choice");
      b.dataset.noteId=note.id;b.setAttribute("aria-pressed",String(note.id===state.noteId));b.replaceChildren();
      const heading=node("div","ep-note-choice-title");heading.append(P.icon("dosya"),node("strong","",note.title));b.append(heading,node("span","ep-note-preview",(state.drafts.get(note.id)?.body||note.body||T("Boş not")).slice(0,95)),node("small","ep-muted",P.datetime(note.updated_at)));
      if(state.drafts.has(note.id))b.append(node("small","ep-draft-dot",T("Taslak")));list.append(b);
    }
    const selected=preferred||state.noteId;
    if(result.items.some(n=>n.id===selected))await select(selected);else if(selected&&!query&&mode==="active"){try{await select(selected);}catch(e){if(result.items.length)await select(result.items[0].id);else P.error(e);}}
    else if(result.items.length)await select(result.items[0].id);
    if(offset)pager.append(button(T("Önceki"),()=>{offset-=30;return load();},"ep-quiet","geri"));
    if(offset+30<result.total)pager.append(button(T("Sonraki"),()=>{offset+=30;return load();},"ep-quiet","ok"));
  }
  let debounce;search.addEventListener("input",()=>{clearTimeout(debounce);offset=0;debounce=setTimeout(()=>load().catch(P.error),250);});
  await load();
};
