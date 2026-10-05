"use strict";
window.PluginViews.study = async function(host) {
  const P=window.LocalPlugins,T=P.T,{node,button,call,card,actions,muted,datetime,human,state}=P;
  const generation=state.generation;
  const tab=state.tab.study||"courses";
  P.tabs(host,[["focus",T("Odak")],["courses",T("Dersler")],["exams",T("Sınavlar")],["topics",T("Konular")],["plans",T("Planlar")],["history",T("Geçmiş")]],tab,key=>{state.tab.study=key;return P.refresh();});
  const courses=await P.options("course"),topics=await P.options("topic");
  const courseName=id=>courses.find(c=>c.id===id)?.name||T("Ders seçilmedi");
  const topicName=id=>topics.find(t=>t.id===id)?.name||"";
  const date=new Date(),today=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,10);
  async function focus(parent) {
    const c=card(parent,T("Odaklan")),info=node("p","ep-muted"),timer=node("div","ep-timer","00:00"),phase=node("p","ep-muted"),a=actions(c);
    c.classList.add("ep-focus-card");const clock=node("div","ep-focus-clock");clock.append(timer);timer.setAttribute("aria-live","off");c.prepend(info,clock,phase);
    muted(c,T("Sayaç uygulama kapalıyken de ilerler. Çalışmaya ara verirken duraklat; mola süreleri çalışma toplamına eklenmez."));
    let current=null,busy=false,signature="";
    async function poll(){if(busy||!c.isConnected||!document.getElementById("eklentiler-gorunum").classList.contains("acik"))return;busy=true;
      try{current=await call("focus_status");const active=["active","paused"].includes(current.status);let seconds=Math.max(0,Math.ceil(current.mode==="free"?current.work_seconds||0:current.remaining_seconds||0));timer.textContent=String(Math.floor(seconds/60)).padStart(2,"0")+":"+String(seconds%60).padStart(2,"0");
        info.textContent=current.status==="idle"?T("Yeni bir odak oturumu başlat"):courseName(current.course_id)+(current.topic_id?" · "+topicName(current.topic_id):"");
        phase.textContent=current.status==="idle"?T("Hazır"):current.status==="completed"?T("Tamamlandı · ")+Math.round((current.work_seconds||0)/60)+T(" dakika çalışma"):(current.status==="paused"?T("Duraklatıldı"):current.phase==="break"?T("Mola"):T("Çalışma"))+(current.mode==="pomodoro"?` · Tur ${current.round}/${current.rounds}`:"");
        const duration=(current.phase==="break"?current.break_minutes:current.work_minutes)*60;clock.style.setProperty("--ep-progress",current.status==="idle"?"0%":current.mode==="free"?"100%":(100*(1-Math.max(0,current.remaining_seconds||0)/(duration||1)))+"%");c.dataset.status=current.status;
        const next=current.status+current.id;if(signature!==next){signature=next;P.clear(a);
          if(!active)a.append(button(T("Odak başlat"),()=>P.form("focus_start",T("Odak oturumu"),{mode:"pomodoro",work_minutes:25,break_minutes:5,rounds:4}),"ep-primary"));
          else {a.append(button(current.status==="paused"?T("Devam et"):T("Duraklat"),async()=>{await call(current.status==="paused"?"focus_resume":"focus_pause",{id:current.id});await poll();}));a.append(button(T("Bitir"),async()=>{await call("focus_finish",{id:current.id});await P.refresh();}));}
        }
      }catch(e){phase.textContent=e.message;}finally{busy=false;}
    }
    await poll();if(c.isConnected&&generation===state.generation)state.timer=setInterval(poll,1000);
  }
  if(tab==="focus"){await focus(host);return;}
  if(tab==="courses")await P.listing(host,"course",T("Ders"),{},(line,row)=>muted(line,row.description||""));
  if(tab==="exams")await P.listing(host,"exam",T("Sınav"),{},(line,row)=>muted(line,courseName(row.course_id)+" · "+datetime(row.at)+" · "+human(row.status||"upcoming")),{status:"upcoming",priority:"normal"});
  if(tab==="topics")await P.listing(host,"topic",T("Konu"),{},(line,row)=>{muted(line,courseName(row.course_id)+" · %"+(row.progress||0)+T(" · Zorluk: ")+(row.difficulty||"—"));const progress=node("progress");progress.max=100;progress.value=row.progress||0;line.append(progress);},{progress:0,difficulty:3});
  if(tab==="plans")await P.listing(host,"study_plan",T("Çalışma planı"),{},(line,row)=>muted(line,courseName(row.course_id)+" · "+topicName(row.topic_id)+" · "+row.minutes+T(" dk · ")+human(row.status||"planned")),{date:today,status:"planned"});
  if(tab==="history"){
    actions(host).append(button(T("Geçmiş çalışma ekle"),()=>P.form("study_session_log",T("Çalışma kaydı"),{type:"study",completed:true})));
    const stats=await call("study_stats",{date:today,offset_minutes:-date.getTimezoneOffset()});muted(host,T("Bugün {a} dk · Bu hafta {b} dk",{a:Math.round(stats.daily_seconds/60),b:Math.round(stats.weekly_seconds/60)}));
    const c=card(host,T("Çalışma geçmişi")),pager=actions(host);let offset=0;
    async function load(){P.clear(c);P.clear(pager);const rows=await call("study_session_list",{limit:30,offset});if(!rows.items.length)muted(c,T("Henüz çalışma kaydı yok."));for(const r of rows.items){const line=node("div","ep-row");line.append(node("strong","",courseName(r.course_id)+" · "+Math.round(r.seconds/60)+T(" dk")));muted(line,datetime(r.start)+" → "+datetime(r.end));c.append(line);}if(offset)pager.append(button(T("Önceki"),()=>{offset-=30;return load();}));if(offset+30<rows.total)pager.append(button(T("Sonraki"),()=>{offset+=30;return load();}));}await load();
  }
};
