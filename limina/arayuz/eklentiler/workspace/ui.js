"use strict";
window.PluginViews.workspace = async function(host) {
  const P=window.LocalPlugins,T=P.T,{node,button,call,card,actions,muted,state}=P;
  const projects=await P.options("workspace"),split=node("div","ep-split ep-project-split"),sidebar=node("aside","ep-list-pane"),detail=node("div","ep-project-detail");
  split.append(sidebar,detail);host.append(split);host=detail;
  actions(sidebar).append(button(T("+ Yeni proje"),()=>P.form("workspace_create",T("Yeni proje"),{next_steps:[]},{},async row=>{state.workspace=row.id;await P.refresh();}),"ep-primary","yeni"));
  const search=node("input","ep-search");search.placeholder=T("Projelerinde ara");search.setAttribute("aria-label",T("Projelerinde ara"));sidebar.append(search);
  const list=node("div","ep-project-list");sidebar.append(list);
  function drawProjects(){P.clear(list);for(const project of projects.filter(p=>p.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()))){const b=button(project.name,()=>{state.workspace=project.id;return P.refresh();},"ep-project-choice","klasor");b.setAttribute("aria-pressed",String(project.id===state.workspace));list.append(b);}}
  search.addEventListener("input",drawProjects);
  if(!projects.length){drawProjects();P.empty(host,"klasor","Bir fikir, bir proje.","Notlarını, dosyalarını ve sonraki adımlarını bir araya getir.");return;}
  if(!projects.some(p=>p.id===state.workspace))state.workspace=projects[0].id;drawProjects();
  let w;try{w=await call("workspace_get",{id:state.workspace});}catch(e){state.workspace=null;throw e;}
  const summary=card(host,null),heading=node("div","ep-head");
  heading.append(node("h2","",w.name));const menu=actions(heading);
  menu.append(button(T("Sohbette devam et"),()=>P.continueChat(w),"ep-primary","konusma"));
  menu.append(button(T("Ekipte çalış"),async()=>{const r=await window.pywebview.api.ekip_projeler();if(!r?.ok)throw new Error(r?.hata);const p=r.projeler.find(x=>x.workspace_id===w.id);if(!p||p.yazilabilir===false)throw new Error(T("Bu proje klasörü ekip için yazılabilir değil."));await Ekip.yenile();Ekip.D.proje=p.kimlik;gorunum("ekip");},"ep-quiet","ekip"));
  P.more(menu,[[T("Projeyi düzenle"),()=>P.edit("workspace",w),"edit"],[T("Sil"),()=>P.remove("workspace",w,async()=>{state.workspace=null;await P.refresh();}),"cop"]]);summary.append(heading);
  if(w.description)muted(summary,w.description);
  if(w.instructions){const instructions=node("details","ep-instructions");instructions.append(node("summary","",T("Amaç ve talimatlar")),node("p","ep-body",w.instructions));summary.append(instructions);}
  if(w.summary){summary.append(node("h3","",T("Kaldığın yer")),node("p","ep-body",w.summary));}
  if(w.next_steps?.length){const list=node("ul","ep-next-steps");for(const step of w.next_steps){const li=node("li");li.append(P.icon("ok",14),node("span","",step));list.append(li);}summary.append(list);}
  await P.references(summary,w.references,T("Projenin bağlantıları"));
  const tab=state.tab.workspace||"tasks";P.tabs(host,[["tasks",T("Görevler")],["files",T("Dosyalar / çıktılar")],["notes",T("Notlar")],["log",T("Çalışma günlüğü")]],tab,key=>{state.tab.workspace=key;return P.refresh();});
  if(tab==="tasks"){
    actions(host).append(button(T("+ Görev"),()=>P.form("task_create",T("Görev oluştur"),{status:"todo"},{workspace_id:w.id}),"ep-primary","yeni"));
    const box=card(host,T("Bir sonraki adım"),"onay"),pager=actions(host);let offset=0;
    async function load(){
      P.clear(box);P.clear(pager);const result=await call("task_list",{workspace_id:w.id,limit:20,offset});
      if(!result.items.length)P.empty(box,"onay","Büyük fikir, küçük adımlar.","İlk görevini ekle; ilerledikçe buradan tamamla.");
      for(const task of result.items){const row=node("div","ep-row ep-workspace-task");row.classList.toggle("completed",task.status==="completed");
        const check=button(task.status==="completed"?T("Yeniden aç"):T("Tamamla"),async()=>{await call("task_update",{id:task.id,expected_revision:task.revision,status:task.status==="completed"?"todo":"completed"});await load();},"ep-check","onay");check.setAttribute("aria-label",(task.status==="completed"?T("Yeniden aç"):T("Tamamla"))+": "+task.title);
        const text=node("div","ep-task-copy");text.append(node("strong","",task.title));if(task.description)muted(text,task.description);
        const status=node("select","ep-select ep-task-status");status.setAttribute("aria-label",T("Görev durumu")+": "+task.title);
        for(const value of ["todo","in_progress","completed","blocked"]){const o=node("option","",P.human(value));o.value=value;status.append(o);}status.value=task.status||"todo";status.addEventListener("change",async()=>{status.disabled=true;try{await call("task_update",{id:task.id,expected_revision:task.revision,status:status.value});await load();}catch(e){P.error(e);status.disabled=false;status.value=task.status||"todo";}});
        row.append(check,text,status);
        const items=[[T("Düzenle"),()=>P.edit("task",task,load,{workspace_id:w.id}),"edit"],[T("Sil"),()=>P.remove("task",task,load),"cop"]];
        if(P.can("focus_start"))items.unshift([T("Bu göreve odaklan"),()=>P.form("focus_start",T("Göreve odaklan"),{mode:"pomodoro",work_minutes:25,break_minutes:5,rounds:4,references:[{type:"workspace",id:w.id},{type:"task",id:task.id}]}),"target"]);
        P.more(row,items);box.append(row);
      }
      if(offset)pager.append(button(T("Önceki"),()=>{offset-=20;return load();}));if(offset+20<result.total)pager.append(button(T("Sonraki"),()=>{offset+=20;return load();}));
    }await load();
  }
  if(tab==="files"){
    actions(host).append(button(T("Dosya / çıktı bağla"),()=>P.form("workspace_attach",T("Dosya veya çıktı bağla"),{kind:"file"},{id:w.id,expected_revision:w.revision})));
    const c=card(host,T("Bağlı dosyalar"));muted(c,T("Dosyalar yerinde kalır. Dosya içeriğini okumak veya değiştirmek için asistan mevcut dosya araçlarını ve izinlerini kullanır."));if(!w.files?.length)muted(c,T("Henüz dosya yok."));
    for(const file of w.files||[]){const r=node("div","ep-row");r.append(node("strong","",file.label||file.path));muted(r,P.human(file.kind)+" · "+file.path);const a=actions(r);a.append(button(T("Yolu doğrula"),async()=>{const res=await call("workspace_resolve",{id:w.id,file_id:file.id,mode:"read"});muted(r,res.path+(res.exists?"":T(" · Dosya bulunamadı")));}),button(T("Bağlantıyı kaldır"),async()=>{await call("workspace_detach",{id:w.id,file_id:file.id,expected_revision:w.revision});await P.refresh();}));c.append(r);}
  }
  if(tab==="notes"){
    const a=actions(host);if(P.can("note_create")){a.append(button(T("Proje notu oluştur"),()=>P.form("note_create",T("Proje notu"),{references:[{type:"workspace",id:w.id}]},{},async note=>{const fresh=await call("workspace_get",{id:w.id});await call("workspace_note_link",{id:w.id,note_id:note.id,expected_revision:fresh.revision});await P.refresh();})),button(T("Mevcut not bağla"),()=>P.form("workspace_note_link",T("Not bağla"),{},{id:w.id,expected_revision:w.revision})));}else muted(host,T("Not içeriği için Smart Notes eklentisini etkinleştir. Mevcut bağlantılar korunuyor."));
    const c=card(host,T("Proje notları"));if(!w.note_ids?.length)muted(c,T("Henüz bağlı not yok."));for(const id of w.note_ids||[]){const r=node("div","ep-row");try{const note=await call("note_get",{id});r.append(node("strong","",note.title),node("p","ep-body",(note.body||"").slice(0,220)));actions(r).append(button(T("Notu aç"),()=>P.navigate("notes","active",note.id),"ep-quiet","ok"));}catch(e){muted(r,T("Bağlı nota erişilemiyor: ")+e.message);}actions(r).append(button(T("Bağlantıyı kaldır"),async()=>{await call("workspace_note_link",{id:w.id,note_id:id,remove:true,expected_revision:w.revision});await P.refresh();}));c.append(r);}
  }
  if(tab==="log"){
    actions(host).append(button(T("İlerleme kaydet"),()=>P.form("workspace_log",T("Çalışma günlüğü"),{category:"progress"},{id:w.id})));
    const c=card(host,T("Çalışma günlüğü")),nav=actions(host);let offset=0;
    async function load(){P.clear(c);P.clear(nav);const rows=await call("workspace_log_list",{id:w.id,limit:20,offset});if(!rows.items.length)muted(c,T("Henüz günlük kaydı yok."));for(const log of rows.items){const r=node("div","ep-row");r.append(node("strong","",P.human(log.category)+" · "+P.datetime(log.created_at)),node("p","ep-body",log.message));c.append(r);}if(offset)nav.append(button(T("Önceki"),()=>{offset-=20;return load();}));if(offset+20<rows.total)nav.append(button(T("Sonraki"),()=>{offset+=20;return load();}));}await load();
  }
};
