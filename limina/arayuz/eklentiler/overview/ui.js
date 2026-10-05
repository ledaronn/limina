"use strict";
/* One start page and a real relationship map, built from the existing local records. */
window.PluginViews.today = async function(host) {
  const P=LocalPlugins,T=P.T,{node,button,call,card,actions,muted,icon}=P;
  const now=new Date(),date=new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,10);
  const read=async(name,args={})=>P.can(name)?call(name,args):null;
  const [stats,plans,exams,notes,projects,tasks]=await Promise.all([
    read("study_stats",{date,offset_minutes:-now.getTimezoneOffset()}),read("study_plan_list",{date,limit:10}),
    read("exam_list",{status:"upcoming",limit:100}),read("note_list",{archived:false,limit:4}),read("workspace_list",{limit:4}),read("task_list",{limit:100})
  ]);
  const hero=node("section","ep-hero");host.append(hero);
  const intro=node("div");intro.append(node("div","ep-eyebrow",now.toLocaleDateString(document.documentElement.lang||undefined,{weekday:"long",day:"numeric",month:"long"})),node("h1","",T("Bir düşünceyle başla.")),node("p","ep-muted",T("Notlarını bağla, bir adım seç, odağını koru.")));
  const a=actions(intro);a.append(button(T("Çalışmaya başla"),()=>P.can("focus_start")?P.form("focus_start",T("Odak oturumu"),{mode:"pomodoro",work_minutes:25,break_minutes:5,rounds:4}):P.navigate("study"),"ep-primary","play"),button(T("Bir fikir yakala"),()=>P.quickNote(),"ep-quiet","fikir"));hero.append(intro);
  const orbit=node("div","ep-orbit");orbit.setAttribute("aria-label",T("Çalışma bölümleri"));
  const center=node("div","ep-orbit-center");center.append(icon("brain",40),node("span","",T("Senin alanın")));orbit.append(center);
  for(const [key,label,i] of [["study",T("Öğren"),"book"],["notes",T("Hatırla"),"dosya"],["workspace",T("Üret"),"klasor"]])orbit.append(button(label,()=>P.navigate(key),"ep-orbit-node ep-orbit-"+key,i));hero.append(orbit);
  const metrics=node("div","ep-metrics");host.append(metrics);
  for(const [label,value,i] of [[T("Bugünkü odak"),stats?Math.round(stats.daily_seconds/60)+T(" dk"):"—","target"],[T("Bu hafta"),stats?Math.round(stats.weekly_seconds/60)+T(" dk"):"—","saat"],[T("Bugünkü adımlar"),plans?.total??"—","onay"]]){const m=node("div","ep-metric");m.append(icon(i,22),node("strong","",value),node("span","ep-muted",label));metrics.append(m);}
  const grid=node("div","ep-dashboard-grid");host.append(grid);
  const plan=card(grid,T("Sıradaki küçük adım"),"onay");
  const pending=(plans?.items||[]).filter(p=>p.status!=="completed"&&p.status!=="skipped");
  const pendingTasks=(tasks?.items||[]).filter(t=>t.status!=="completed").slice(0,3);
  const courses=P.can("course_list")?await P.options("course"):[];
  if(!pending.length&&!pendingTasks.length)P.empty(plan,"onay","Bugün için yer aç.","Bir konu veya görev ekleyerek başla.",["Plan ekle",()=>P.can("study_plan_create")?P.form("study_plan_create",T("Çalışma planı"),{date,status:"planned"}):P.navigate("study")]);
  for(const p of pending){const line=node("div","ep-row ep-task-line"),text=node("div");text.append(node("strong","",courses.find(c=>c.id===p.course_id)?.name||T("Çalışma")),node("span","ep-muted",p.minutes+T(" dk")));line.append(button(T("Tamamla"),async()=>{await call("study_plan_update",{id:p.id,expected_revision:p.revision,status:"completed"});await P.refresh();},"ep-check","onay"),text,button(T("Odaklan"),()=>P.form("focus_start",T("Odak oturumu"),{mode:"pomodoro",work_minutes:Math.min(p.minutes,240),break_minutes:5,rounds:1,course_id:p.course_id,...(p.topic_id?{topic_id:p.topic_id}:{})}),"ep-quiet","play"));plan.append(line);}
  for(const task of pendingTasks){const line=node("div","ep-row");line.append(button(task.title,()=>P.navigate("workspace","tasks",task.workspace_id),"ep-quiet","onay"));plan.append(line);}
  const project=card(grid,T("Kaldığın yerden"),"klasor");
  if(!projects?.items.length)P.empty(project,"klasor","Bir fikir, bir proje.","Dosyalarını, notlarını ve sonraki adımlarını bir arada tut.",["Proje oluştur",()=>P.navigate("workspace")]);
  for(const w of projects?.items||[]){const row=node("div","ep-row"),b=button(w.name,()=>P.navigate("workspace","tasks",w.id),"ep-project-link","klasor");row.append(b);muted(row,w.summary||w.description||T("Bir sonraki adımını belirle."));project.append(row);}
  const upcoming=card(grid,T("Ufuktaki sınavlar"),"calendar");
  const upcomingRows=(exams?.items||[]).filter(e=>e.remaining_seconds>=0).sort((a,b)=>new Date(a.at)-new Date(b.at)).slice(0,4);
  if(!upcomingRows.length)P.empty(upcoming,"calendar","Takvimin sakin.","Bir sınav eklediğinde burada görünecek.",["Sınav ekle",()=>P.can("exam_create")?P.form("exam_create",T("Sınav ekle"),{status:"upcoming",priority:"normal"}):P.navigate("study")]);
  for(const e of upcomingRows){const row=node("div","ep-row ep-exam-row"),days=node("div","ep-days");days.append(node("strong","",Math.ceil(e.remaining_seconds/86400)),node("small","",T("gün")));row.append(days,button(e.name,()=>P.edit("exam",e),"ep-quiet","calendar"));upcoming.append(row);}
  const recent=card(grid,T("Taze düşünceler"),"dosya");
  if(!notes?.items.length)P.empty(recent,"fikir","Aklındakini bırak.","Küçük bir not, sonra kuracağın bir bağlantı olabilir.",["İlk notunu yaz",()=>P.quickNote()]);
  for(const note of notes?.items||[]){const row=node("div","ep-row");row.append(button(note.title,()=>P.navigate("notes","active",note.id),"ep-quiet","dosya"));muted(row,(note.body||"").slice(0,110));recent.append(row);}
};

window.PluginViews.connections = async function(host) {
  const P=LocalPlugins,T=P.T,{node,button,call,card,actions,muted}=P;
  muted(host,T("Bir düşünce seç. Gerçek bağlantılarının izini sür."));
  const records=new Map(),edges=[];
  const kinds=["course","exam","topic","workspace","task","note"];
  await Promise.all(kinds.map(async kind=>{if(!P.can(kind+"_list"))return;const r=await call(kind+"_list",{limit:100});for(const row of r.items)records.set(kind+":"+row.id,{kind,...row});}));
  for(const [key,r] of records){const refs=[...(r.references||[]),...(r.links||[]).map(id=>({type:"note",id})),...(r.note_ids||[]).map(id=>({type:"note",id}))];
    for(const kind of ["course","exam","topic","workspace"])if(r[kind+"_id"])refs.push({type:kind,id:r[kind+"_id"]});
    for(const ref of refs){const target=ref.type+":"+ref.id;if(records.has(target)&&key!==target&&!edges.some(e=>e.includes(key)&&e.includes(target)))edges.push([key,target]);}
  }
  if(!records.size){P.empty(host,"network","Bağlantılar burada büyür.","Bir not, ders veya proje oluştur; ilişkilerini eklediğinde haritan oluşur.",["Bir not yaz",()=>P.quickNote()]);return;}
  const toolbar=actions(host),select=node("select","ep-select");select.setAttribute("aria-label",T("Haritadaki düşünce"));
  for(const [key,r] of records){const option=node("option","",P.human(r.kind)+" · "+P.title(r));option.value=key;select.append(option);}toolbar.append(select);
  const plot=card(host,null),details=card(host,T("Bağlantının içeriği"),"link");plot.classList.add("ep-map-card");
  function draw(key){P.clear(plot);P.clear(details);select.value=key;const selected=records.get(key),neighbors=edges.filter(e=>e.includes(key)).map(e=>records.get(e.find(k=>k!==key)));
    const graph=node("div","ep-map");plot.append(graph);const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.setAttribute("viewBox","0 0 100 100");svg.setAttribute("preserveAspectRatio","none");svg.setAttribute("aria-hidden","true");graph.append(svg);
    const related=neighbors.slice(0,8);related.forEach((r,i)=>{const angle=(i/Math.max(related.length,1))*Math.PI*2-Math.PI/2,x=50+35*Math.cos(angle),y=50+35*Math.sin(angle);const line=document.createElementNS(svg.namespaceURI,"line");for(const [k,v] of Object.entries({x1:50,y1:50,x2:x,y2:y}))line.setAttribute(k,v);svg.append(line);const b=button(P.title(r),()=>draw(r.kind+":"+r.id),"ep-map-node ep-kind-"+r.kind,P.kindIcon[r.kind]);b.style.left=x+"%";b.style.top=y+"%";b.title=P.human(r.kind)+" · "+P.title(r);graph.append(b);});
    const center=button(P.title(selected),()=>P.openReference({type:selected.kind,id:selected.id}),"ep-map-node ep-map-center",P.kindIcon[selected.kind]);center.style.left="50%";center.style.top="50%";graph.append(center);
    details.append(node("h3","",P.title(selected)));muted(details,selected.body?.slice(0,500)||selected.description||selected.instructions||P.human(selected.kind));actions(details).append(button(T("Kaydı aç"),()=>P.openReference({type:selected.kind,id:selected.id}),"ep-primary","ok"));
    if(!neighbors.length)muted(details,T("Henüz bağlı kayıt yok. Düzenle bölümünden bir ilişki ekleyebilirsin."));else{muted(details,neighbors.length+" "+T("bağlantı"));const list=actions(details);for(const r of neighbors)list.append(button(P.title(r),()=>draw(r.kind+":"+r.id),"ep-chip",P.kindIcon[r.kind]));}
  }
  select.addEventListener("change",()=>draw(select.value));draw(records.keys().next().value);muted(host,T("Her bölümden en son 100 kayıt gösterilir. Çizgiler yalnızca eklediğin ilişkileri temsil eder."));
};
