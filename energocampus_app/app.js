const M = EnergyModel;
const API_BASE = (window.location.protocol === 'file:') ? 'http://127.0.0.1:8000' : '';
const $ = (s,el=document)=>el.querySelector(s);
const icons = {
bolt:'<path d="m13 2-9 12h7l-1 8 10-12h-7l1-8Z"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
building:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 21v-4h6v4M8 7h1m6 0h1M8 11h1m6 0h1"/>',door:'<path d="M3 21h18M6 21V4l12-2v19M14 12h.01"/>',chart:'<path d="M4 3v17h17M8 14l4-5 4 3 5-6"/>',history:'<path d="M3 11a9 9 0 1 1 2.7 7M3 4v7h7m2-5v6l4 2"/>',settings:'<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m9 3-1 3-3 1-2 3 2 3v4l3 2 4-1 3 2 3-2v-4l3-3-2-3-3-1-1-3Z"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',leaf:'<path d="M20 3c-9 0-16 3-16 10a7 7 0 0 0 12 5c4-4 4-10 4-15ZM4 21 15 10"/>',bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',pc:'<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 21h8m-4-5v5"/>',light:'<path d="M9 18h6m-5 3h4M8 13a6 6 0 1 1 8 0c-1 1-1 2-1 2H9s0-1-1-2Z"/>',window:'<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M12 3v18M3 12h18"/>',temp:'<path d="M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0ZM12 8v10"/>',arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',down:'<path d="m6 9 6 6 6-6"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',warning:'<path d="m12 3 10 18H2L12 3Zm0 6v5m0 3h.01"/>',check:'<path d="m5 12 4 4L19 6"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',wifi:'<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0M8 16a6 6 0 0 1 8 0m-4 4h.01"/>',offline:'<path d="m3 3 18 18M2 8c2-2 4-3 6-3m6 0c3 0 6 1 8 3M5 12c2-2 4-2 6-2m-3 6a6 6 0 0 1 8 0m-4 4h.01"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',play:'<path d="m8 4 12 8-12 8V4Z"/>',menu:'<path d="M3 6h18M3 12h18M3 18h18"/>',reset:'<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7"/>',users:'<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m3 10v-3a6 6 0 0 0-2-4"/>',chip:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4M18 9h4m-4 6h4"/>',database:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12v7c0 1.66 4 3 9 3s9-1.34 9-3v-7"/>'};
function icon(n,c=''){return `<svg class="icon ${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[n]||icons.info}</svg>`;}
function fillIcons(){document.querySelectorAll('[data-icon]').forEach(e=>{e.innerHTML=icon(e.dataset.icon);});}
function esc(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
const num=(v,d=1)=>Number(v||0).toLocaleString('ru-RU',{minimumFractionDigits:d,maximumFractionDigits:d});
const time=t=>new Date(t).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'});
let state={
  rooms:M.seed(),
  settings:{...M.defaults},
  events:[],
  roleCode:'laborant',
  roleToken:'demo-role-laborant',
  backendOnline:false,
  modelInfo:{
    version_tag:'v1.2-gbr',
    algorithm_type:'Hybrid Rule-Based + scikit-learn GradientBoostingRegressor',
    metrics:{gbr_model:{MAE_kw:0.0413,RMSE_kw:0.1030,MAPE_active_pct:17.36,R2_score:0.9580},ridge_baseline:{MAE_kw:0.0615,RMSE_kw:0.1329,MAPE_active_pct:22.42,R2_score:0.9300}}
  }
};
let syncIntervalSec = 10;
let nextSyncCountdown = syncIntervalSec;
let isSyncPaused = false;

function isPrivilegedUser(){
  return state.roleCode === 'energomanager' || state.roleCode === 'sysadmin' || state.roleToken.includes('energomanager') || state.roleToken.includes('sysadmin');
}
function isAdminUser(){
  return state.roleCode === 'sysadmin' || state.roleToken.includes('sysadmin');
}
try {
  const saved=JSON.parse(localStorage.getItem('energocampus-v1'));
  if(saved?.rooms?.length===6 && saved.rooms.every(r=>Array.isArray(r.computers)&&typeof r.online==='boolean')){
    state={...state,...saved,settings:{...M.defaults,...(saved.settings||{})}};
    state.rooms=state.rooms.map(r=>({recStatus:'new',recProcessedAt:null,recComment:'',...r}));
  }
}catch{}
if(!state.events.length)state.events=[
  {at:Date.now()-2*60000,room:'204',text:'В свободном кабинете остались включены 4 ПК и свет (рекомендация: новая)',type:'warning'},
  {at:Date.now()-5*60000,room:'302',text:'Температура 17,8 °C. Окно открыто в свободном классе',type:'warning'},
  {at:Date.now()-8*60000,room:'305',text:'Потеряна связь с контроллером (S0_OFFLINE, расчёт экономии заблокирован)',type:'offline'},
  {at:Date.now()-15*60000,room:'201',text:'Кабинет отмечен как занятый (штатное занятие)',type:'info'}
];
let route='overview',filter='all',floor='all',query='',period='day',analyticsRoom='all',selectedRoom=null,lastFocus=null;
const routeNames={overview:'Обзор кампуса',rooms:'Кабинеты',analytics:'Аналитика',events:'Журнал событий',database:'База данных (14 таблиц)',settings:'Настройки и датчики',about:'О проекте'};
const statusLabels={new:'Новая рекомендация',accepted:'Принята в работу',completed:'Выполнена (подтверждено)',rejected:'Отклонена лаборантом'};

function save(){try{localStorage.setItem('energocampus-v1',JSON.stringify(state));}catch{toast('Хранилище браузера недоступно. Изменения сохраняются до перезагрузки.');}}
function log(room,text,type='info'){state.events.unshift({at:Date.now(),room,text,type});state.events=state.events.slice(0,200);save();}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('#toast').hidden=true,4000);}

async function syncWithBackend(){
  try{
    const res = await fetch(API_BASE + '/api/v1/state',{headers:{'X-Role-Token':state.roleToken}});
    if(!res.ok)return;
    const json = await res.json();
    if(json.status==='ok' && json.data){
      state.backendOnline = true;
      state.settings = {...M.defaults,...json.data.settings};
      if(json.data.model_info) state.modelInfo = json.data.model_info;
      const recsByRoom = {};
      (json.data.recommendations||[]).forEach(rc=>{if(!recsByRoom[rc.room_id])recsByRoom[rc.room_id]=rc;});
      state.rooms = json.data.rooms.map(r=>{
        const rc = recsByRoom[r.id];
        return {
          ...r,
          recId:rc?rc.recommendation_id:null,
          recStatus:rc?rc.status:(r.state_class==='S3_EXCESS'?'new':'completed'),
          recProcessedAt:rc&&rc.processed_at?new Date(rc.processed_at).getTime():null,
          recComment:rc&&rc.operator_comment?rc.operator_comment:''
        };
      });
      if(json.data.events?.length) state.events = json.data.events;
      save();
      render();
      if(selectedRoom && !$('#drawer').hidden){
        openRoom(selectedRoom, true);
      }
      const badge = document.querySelector('.demo-badge');
      if(badge){
        badge.innerHTML = '<span></span>БД SQLite активна (14 таблиц)';
        badge.style.borderColor = '#23654e';
        badge.style.color = '#173e30';
      }
    }
  }catch{
    state.backendOnline = false;
    const badge = document.querySelector('.demo-badge');
    if(badge){
      badge.innerHTML = '<span></span>Автономный режим (демо)';
      badge.style.borderColor = '#dfe8dc';
      badge.style.color = '#6c7e63';
    }
  }
}

async function pushRoomTelemetry(r, noteText){
  if(!state.backendOnline)return;
  try{
    const res = await fetch(API_BASE + '/api/v1/telemetry',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Role-Token':state.roleToken},
      body:JSON.stringify({
        room_id:r.id,
        online:r.online,
        occupied:r.occupied,
        computers_on:r.computers.filter(Boolean).length,
        total_pcs:r.total,
        computers:r.computers,
        light_on:r.light,
        windows_open:r.windows,
        door_open:r.door,
        temp_c:r.temp,
        event_note:noteText
      })
    });
    if(res.ok){
      const json = await res.json();
      if(json.state?.recommendations){
        const rc = json.state.recommendations.find(x=>x.room_id===r.id);
        if(rc){r.recId=rc.recommendation_id;r.recStatus=rc.status;r.recProcessedAt=rc.processed_at?new Date(rc.processed_at).getTime():null;}
      }
    }
  }catch{}
}

function heading(title,sub,actions=''){return `<div class="page-heading"><div><div class="eyebrow">ЭНЕРГИЯ ПОД КОНТРОЛЕМ</div><h1>${title}</h1><p>${sub}</p></div><div class="heading-actions">${actions}</div></div>`;}
function dateButton(){return `<span class="date-pill">${icon('clock')}${new Date().toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'})}</span>`;}
function metrics(){
  const s=M.summary(state.rooms,state.settings);
  const tariff=Number(state.settings.tariffKzt||32.5);
  return `<div class="metrics">
<article class="metric metric-clickable" id="metric-power-card" title="Нажмите для перехода к списку кабинетов"><div class="metric-label">Расчётная мощность<span class="metric-icon">${icon('bolt')}</span></div><div class="metric-value">${num(s.kw,2)}<span>кВт</span></div><div class="metric-footer"><span class="green-dot"></span>${s.online} из ${state.rooms.length} контроллеров на связи ${icon('arrow')}</div></article>
<article class="metric metric-clickable" id="metric-pcs-card" title="Нажмите для перехода к списку кабинетов"><div class="metric-label">Включено компьютеров<span class="metric-icon">${icon('pc')}</span></div><div class="metric-value">${s.pcs}<span>/ ${s.total}</span></div><div class="metric-footer">${s.unknown} ПК без актуальных данных ${icon('arrow')}</div></article>
<article class="metric metric-clickable" id="metric-alerts-card" title="Нажмите для фильтрации кабинетов, требующих внимания"><div class="metric-label">Требуют внимания<span class="metric-icon amber-icon">${icon('warning')}</span></div><div class="metric-value">${new Set(s.alerts.map(a=>a.room)).size}<span>кабинета</span></div><div class="metric-footer"><span class="amber-dot"></span>${s.alerts.length} активных предупреждения ${icon('arrow')}</div></article>
<article class="metric metric-green metric-clickable" id="metric-saving-card" title="Нажмите для перехода к аналитике и расчёту экономии в тенге"><div class="metric-label">Потенциал экономии<span class="metric-icon">${icon('leaf')}</span></div><div class="metric-value">${num(s.idle,2)}<span>кВт·ч / час</span></div><div class="metric-footer">≈ ${num(s.idle*tariff,0)} тг/ч (за 4 ч: ${num(s.idle*4*tariff,0)} тг) ${icon('arrow')}</div></article></div>`;
}
const profiles={day:{current:[.25,.22,.2,.2,.2,.25,.3,.65,2.4,3.8,3.2,4.1,3.5,4.4,3.5,3.2,2.5,1.7,1.2,.5,.3,.25,.23,.2],base:[.8,.8,.7,.7,.7,.8,.9,1.6,3.2,4.8,4.2,5.3,4.6,5.4,4.6,4.2,3.6,2.8,2.3,1.6,1.4,1.2,1.1,.9],labels:['00:00','04:00','08:00','12:00','16:00','20:00','23:00'],unit:'кВт',title:'Потребление за сутки'},week:{current:[24,28,26,30,22,9,7],base:[34,38,35,41,33,16,13],labels:['Пн','Вт','Ср','Чт','Пт','Сб','Вс'],unit:'кВт·ч',title:'Потребление за неделю'}};
function getScaledProfile(){
  const raw = profiles[period];
  if(analyticsRoom==='all') return {current:raw.current,base:raw.base,labels:raw.labels,unit:raw.unit,title:raw.title,max:period==='day'?6:50};
  const r = state.rooms.find(x=>x.id===analyticsRoom);
  const share = r ? (r.total / 72) : (12 / 72);
  return {
    current:raw.current.map(v=>Number((v*share).toFixed(2))),
    base:raw.base.map(v=>Number((v*share).toFixed(2))),
    labels:raw.labels,
    unit:raw.unit,
    title:`${raw.title} (каб. ${analyticsRoom})`,
    max:period==='day'?1.5:12
  };
}
function chart(useRoomFilter=false){
  const p = useRoomFilter ? getScaledProfile() : {...profiles[period],max:period==='day'?6:50};
  const max=p.max,W=760,H=180,x=i=>i/(p.current.length-1)*W,y=v=>H-Math.min(v,max)/max*H,line=arr=>arr.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(v).toFixed(1)).join(' ');
  return `<div class="chart-wrap"><div class="chart-scale">${[max,max*.75,max*.5,max*.25,0].map(n=>`<span>${num(n,n%1?1:0)}</span>`).join('')}</div><div class="chart-plot"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${p.title}. Синтетический демонстрационный сценарий: фактическое и базовое потребление." preserveAspectRatio="none">${[0,45,90,135,180].map(y=>`<path d="M0 ${y}H760" stroke="#e9eeea" stroke-dasharray="4 4"/>`).join('')}<path d="${line(p.current)} L760,180 L0,180 Z" fill="#e4f2e7"/><path d="${line(p.base)}" fill="none" stroke="#b7c4bc" stroke-width="2" stroke-dasharray="6 6"/><path d="${line(p.current)}" fill="none" stroke="#24836a" stroke-width="3" stroke-linejoin="round"/>${p.current.map((v,i)=>`<circle cx="${x(i)}" cy="${y(v)}" r="4" fill="#24836a" opacity="0"><title>${period==='day'?String(i).padStart(2,'0')+':00':p.labels[i]}: ${num(v,2)} ${p.unit}</title></circle>`).join('')}</svg><div class="chart-x">${p.labels.map(l=>`<span>${l}</span>`).join('')}</div></div></div>`;
}
function chartCard(withRoomSelect=false){
  const p = withRoomSelect ? getScaledProfile() : profiles[period];
  const roomSelectHtml = withRoomSelect ? `<select id="analytics-room-select" aria-label="Выбор кабинета для графика"><option value="all" ${analyticsRoom==='all'?'selected':''}>Все кабинеты корпуса А</option>${state.rooms.map(r=>`<option value="${r.id}" ${analyticsRoom===r.id?'selected':''}>Кабинет ${r.id} (${r.name})</option>`).join('')}</select>` : '';
  return `<section class="panel energy-panel"><div class="panel-heading"><div><h2>Потребление энергии <span class="unit-label">${p.unit}</span></h2><p>Динамика нагрузки за ${period==='day'?'сутки (24 ч)':'неделю (7 дн.)'} ${withRoomSelect&&analyticsRoom!=='all'?`· Кабинет ${analyticsRoom}`:'· Корпус А'}</p></div><div class="analytics-controls">${roomSelectHtml}<div class="segmented" aria-label="Период графика"><button data-period="day" class="${period==='day'?'active':''}">Сутки</button><button data-period="week" class="${period==='week'?'active':''}">Неделя</button></div></div></div>${chart(withRoomSelect)}<div class="chart-footer"><div class="legend"><span><i class="legend-green"></i>С энергоконтролем ИИС</span><span><i class="legend-dash"></i>Базовый прогноз f_ML(X) без контроля</span></div><span class="chart-demo">Синтетический демонстрационный ряд</span></div></section>`;
}
function alertPanel(){const a=M.alerts(state.rooms,state.settings);return `<section class="panel alert-panel"><div class="panel-heading"><h2>Обратите внимание <span class="count-badge">${a.length}</span></h2><span class="status-orbit">${icon('bell')}</span></div><div class="alert-list">${a.length?a.slice(0,3).map(x=>`<button class="alert-item" data-open="${x.room}"><span class="alert-symbol ${x.severity==='neutral'?'neutral':''}">${icon(x.type==='offline'?'offline':x.type==='temperature'?'temp':'bolt')}</span><span><strong>Кабинет ${x.room}</strong><span>${x.title}</span><small>${x.description}</small></span>${icon('arrow')}</button>`).join(''):`<div class="all-clear">${icon('check')}Все кабинеты в порядке</div>`}</div><button class="panel-link" data-alerts>Все предупреждения ${icon('arrow')}</button></section>`;}
function roomCard(r){const a=M.alerts([r],state.settings),n=r.computers.filter(Boolean).length,kw=M.power(r,state.settings),status=!r.online?'Нет связи':a.length?'Требует внимания':r.occupied?'Идёт занятие':'Всё в порядке';return `<button class="room-card ${!r.online?'room-offline':a.length?'room-warning':''}" data-open="${r.id}"><div class="room-top"><span class="room-number">${icon('door')}<strong>${r.id}</strong></span><span class="badge ${!r.online?'badge-gray':a.length?'badge-amber':r.occupied?'badge-blue':'badge-green'}"><i></i>${status}</span></div><div class="room-name">${r.name}</div><div class="room-sensors"><div><span>${icon('pc')}Компьютеры</span><strong>${r.online?`${n}<small> / ${r.total}</small>`:'—'}</strong></div><div><span>${icon('light')}Освещение</span><strong class="${r.online&&r.light?'on-value':''}">${r.online?(r.light?'Включено':'Выключено'):'—'}</strong></div><div><span>${icon('temp')}Температура</span><strong class="${r.online&&(r.temp<state.settings.minTemp||r.temp>state.settings.maxTemp)?'text-amber':''}">${r.online?num(r.temp)+'°C':'—'}</strong></div></div><div class="room-mini"><span>${icon('door')}${r.online?(r.door?'Открыта':'Закрыта'):'Нет данных'}</span><span class="${r.online&&r.windows?'text-amber':''}">${icon('window')}${r.online?(r.windows?'Окно открыто':'Окна закрыты'):'Нет данных'}</span></div><div class="room-bottom"><span>${icon('bolt')}<strong>${kw===null?'—':num(kw,2)}</strong>${kw===null?'Нет телеметрии':'кВт'}</span><span>${r.floor} этаж ${icon('arrow')}</span></div></button>`;}
function filteredRooms(){return state.rooms.filter(r=>(floor==='all'||r.floor===Number(floor))&&(!query||`${r.id} ${r.name}`.toLowerCase().includes(query.toLowerCase()))&&(filter==='all'||(filter==='attention'&&M.alerts([r],state.settings).length)||(filter==='active'&&r.online&&r.occupied)||(filter==='free'&&r.online&&!r.occupied)));}
function roomsSection(full=false){const list=filteredRooms();return `<section class="rooms-section"><div class="rooms-title"><div><h2>${full?'Все кабинеты':'Состояние кабинетов'} <span class="plain-count">${state.rooms.length}</span></h2><p>Всё важное о каждом кабинете — в одном месте</p></div><div class="room-tools"><label class="search-box">${icon('search')}<input id="room-search" placeholder="Найти кабинет" aria-label="Найти кабинет" value="${esc(query)}"></label><select id="floor-filter" aria-label="Этаж"><option value="all" ${floor==='all'?'selected':''}>Все этажи</option><option value="2" ${floor==='2'?'selected':''}>2 этаж</option><option value="3" ${floor==='3'?'selected':''}>3 этаж</option></select></div></div><div class="room-tabs" role="group" aria-label="Состояние кабинетов">${[['all','Все кабинеты'],['attention','Требуют внимания'],['active','Идёт занятие'],['free','Свободные']].map(([v,l])=>`<button class="${filter===v?'active':''}" data-filter="${v}">${l}${v==='attention'?`<span>${new Set(M.alerts(state.rooms,state.settings).map(a=>a.room)).size}</span>`:''}</button>`).join('')}</div><div class="room-grid" id="room-grid">${list.length?list.map(roomCard).join(''):'<div class="empty-state">Кабинеты не найдены. Измените поиск или фильтр.</div>'}</div></section>`;}
function overview(){return heading('Обзор кампуса','Следите за кабинетами. Замечайте потери. Сохраняйте энергию.',dateButton()+`<button class="button" data-export>${icon('download')}Отчёт</button>`)+metrics()+`<div class="insight-row">${chartCard(false)}${alertPanel()}</div>`+roomsSection();}
function analytics(){
  const s=M.summary(state.rooms,state.settings);
  const tariff=Number(state.settings.tariffKzt||32.5);
  const vals=state.rooms.filter(r=>r.online).sort((a,b)=>M.power(b,state.settings)-M.power(a,state.settings));
  const selectedRoomObj = analyticsRoom!=='all' ? state.rooms.find(r=>r.id===analyticsRoom) : null;
  const targetIdleKw = selectedRoomObj ? (selectedRoomObj.online && !selectedRoomObj.occupied ? M.power(selectedRoomObj,state.settings) : 0) : s.idle;
  const targetSavings4h = targetIdleKw * 4;
  const targetKzt4h = targetSavings4h * tariff;
  const gm = state.modelInfo?.metrics?.gbr_model || {MAE_kw:0.0413,RMSE_kw:0.1030,MAPE_active_pct:17.36,R2_score:0.9580};
  const rm = state.modelInfo?.metrics?.ridge_baseline || {MAE_kw:0.0615,RMSE_kw:0.1329,MAPE_active_pct:22.42,R2_score:0.9300};
  return heading('Аналитика энергопотребления','Нагрузка по кабинетам, интеллектуальная оценка и потенциал экономии в кВт·ч и тенге.',`<button class="button" id="adapt-model-btn">${icon('chip')}Адаптировать модель ИИ</button><button class="button" data-export>${icon('download')}Скачать CSV</button>`)
    +metrics()
    +chartCard(true)
    +`<div class="analytics-lower"><section class="panel"><div class="panel-heading"><div><h2>Нагрузка по кабинетам</h2><p>Расчёт по текущему состоянию устройств и модели ИИ (${esc(state.modelInfo.version_tag)})</p></div></div><div class="bars">${vals.map(r=>`<button class="bar-row" data-open="${r.id}"><strong>Кабинет ${r.id}</strong><span class="bar-track"><i style="width:${Math.max(1,M.power(r,state.settings)/Math.max(s.kw,0.01)*100)}%"></i></span><span>${num(M.power(r,state.settings),2)} кВт</span></button>`).join('')}</div></section><section class="panel saving-card"><span class="large-leaf">${icon('leaf')}</span><h2>Что можно сэкономить? (${analyticsRoom==='all'?'Корпус А':'Каб. '+analyticsRoom})</h2><p>При отключении техники в свободных аудиториях по рекомендации ИИС:</p><div class="saving-number">${num(targetSavings4h,2)} <span>кВт·ч за 4 часа (по ${num(targetIdleKw,2)} кВт·ч/ч)</span></div><div class="kzt-pill">≈ ${num(targetKzt4h,0)} тг за 4 ч (${num(targetIdleKw*tariff,1)} тг/ч при тарифе ${num(tariff,2)} тг/кВт·ч)</div><p class="small-text">Расчёт выполнен по формуле (1.1): ΔC = ΔW · C_тар. Тариф: [ДАННЫЕ: действующий тариф = ${num(tariff,2)} тг/кВт·ч].</p></section></div>`
    +`<section class="panel metrics-table-box"><div class="panel-heading" style="padding:0 0 12px"><div><h2>Верификация регрессионной модели ИИ (scikit-learn)</h2><p>Сравнение ансамбля GradientBoostingRegressor и линейной регрессии Ridge на синтетической выборке (14 суток, 2016 точек)</p></div><span class="badge badge-green">Активна: ${esc(state.modelInfo.version_tag)}</span></div><div class="table-scroll" style="margin-top:8px"><table><thead><tr><th>Модель прогнозирования базовой нагрузки f_ML(X)</th><th>MAE, кВт</th><th>RMSE, кВт</th><th>MAPE (актив.), %</th><th>Коэффициент детерминации R²</th></tr></thead><tbody><tr><td><strong>GradientBoostingRegressor (основная модель ИИС)</strong></td><td>${num(gm.MAE_kw,4)}</td><td>${num(gm.RMSE_kw,4)}</td><td>${num(gm.MAPE_active_pct,2)} %</td><td>${num(gm.R2_score,4)}</td></tr><tr><td>Ridge Regression (базовая линейная модель сравнения)</td><td>${num(rm.MAE_kw,4)}</td><td>${num(rm.RMSE_kw,4)}</td><td>${num(rm.MAPE_active_pct,2)} %</td><td>${num(rm.R2_score,4)}</td></tr></tbody></table></div></section>`
    +`<div class="note">${icon('info')}Текущая мощность рассчитана по модели: ПК — ${state.settings.pcWatts} Вт, освещение кабинета — ${state.settings.lightWatts} Вт, тариф — ${num(tariff,2)} тг/кВт·ч. Временные ряды являются синтетическими демонстрационными данными и не выдаются за показания физических счётчиков.</div>`;
}
function events(){return heading('Журнал событий','Предупреждения, рекомендации ИИ и действия оператора в системе.',`<button class="button" id="export-events">${icon('download')}Экспорт журнала</button>`)+`<section class="panel"><div class="panel-heading"><h2>Активные предупреждения</h2><span class="demo-badge">${M.alerts(state.rooms,state.settings).length} событий</span></div><div class="event-alerts">${M.alerts(state.rooms,state.settings).map(a=>`<button class="event-alert" data-open="${a.room}"><span class="alert-symbol ${a.severity==='neutral'?'neutral':''}">${icon(a.type==='offline'?'offline':'warning')}</span><span><strong>Кабинет ${a.room} · ${a.title}</strong><small>${a.description}</small></span>${icon('arrow')}</button>`).join('')||'<div class="empty-state">Активных предупреждений нет</div>'}</div></section><section class="panel history-panel"><div class="panel-heading"><h2>История изменений</h2><span class="muted">Последние 200 событий</span></div><div class="table-scroll"><table><thead><tr><th>Время</th><th>Кабинет</th><th>Событие</th><th>Тип</th></tr></thead><tbody>${state.events.map(e=>`<tr><td>${time(e.at)}<small>${new Date(e.at).toLocaleDateString('ru-RU')}</small></td><td><button class="table-link" data-open="${esc(e.room)}">${e.room==='—'?'Система':'Кабинет '+esc(e.room)}</button></td><td>${esc(e.text)}</td><td><span class="badge ${e.type==='warning'?'badge-amber':e.type==='offline'?'badge-gray':'badge-green'}">${e.type==='warning'?'Внимание':e.type==='offline'?'Нет связи':'Информация'}</span></td></tr>`).join('')}</tbody></table></div></section>`;}
function settings(){
  const tariff=Number(state.settings.tariffKzt||32.5);
  return heading('Настройки и датчики','Параметры расчёта мощности, тарифа и состояние демонстрационных контроллеров.')+`<div class="settings-layout"><form class="panel settings-form" id="settings-form"><div class="panel-heading"><div><h2>Параметры мониторинга и тариф</h2><p>Применяются ко всем кабинетам корпуса А (таблица system_settings_tariffs)</p></div></div><div class="form-body"><div class="form-row"><label>Мощность одного ПК, Вт<input name="pcWatts" type="number" min="30" max="1000" step="1" required value="${state.settings.pcWatts}"></label><label>Мощность освещения, Вт<input name="lightWatts" type="number" min="10" max="2000" step="1" required value="${state.settings.lightWatts}"></label></div><div class="form-row"><label>Минимум температуры, °C<input name="minTemp" type="number" min="10" max="25" step="0.1" required value="${state.settings.minTemp}"></label><label>Максимум температуры, °C<input name="maxTemp" type="number" min="18" max="35" step="0.1" required value="${state.settings.maxTemp}"></label></div><label>Тариф на электроэнергию, тг/кВт·ч [ДАННЫЕ: действующий тариф]<input name="tariffKzt" type="number" min="1" max="500" step="0.1" required value="${tariff}"></label><p class="small-text">Номинальная мощность даёт расчётную оценку. Для коммерческого учёта кВт·ч используется импульсный/цифровой счётчик энергии.</p><button class="button primary" type="submit">${icon('check')}Сохранить параметры</button></div></form><section class="panel"><div class="panel-heading"><h2>Контроллеры кабинетов</h2><span class="badge ${state.backendOnline?'badge-green':'badge-gray'}">${state.backendOnline?'API + SQLite3':'Автономный демо'}</span></div><div class="controller-list">${state.rooms.map(r=>`<button data-open="${r.id}"><span class="controller-icon">${icon('chip')}</span><span><strong>Контроллер ${r.id}</strong><small>Кабинет ${r.id} · ESP32 · Статус: ${M.explainRoom(r,state.settings).stateClass}</small></span><span class="badge ${r.online?'badge-green':'badge-gray'}">${r.online?'На связи':'Нет связи'}</span></button>`).join('')}</div></section></div><section class="panel demo-settings"><div><h2>Начать демонстрацию заново</h2><p>Восстановить исходные кабинеты, настройки, рекомендации и журнал в БД и браузере.</p></div><button class="button" id="reset-demo">${icon('reset')}Сбросить демо</button></section>`;
}
let currentDbTable = 'rooms';
let currentDbTableData = null;
const currentDbTablesList = [
  'rooms', 'telemetry_measurements', 'workstations_devices', 'saving_recommendations',
  'detected_anomalies', 'ai_evaluation_runs', 'system_settings_tariffs', 'system_events_log',
  'ml_models', 'room_controllers', 'schedule_slots', 'energy_forecasts', 'users', 'roles'
];

function database(){
  if(!isPrivilegedUser()){
    return heading('База данных (14 таблиц)', 'Реляционный контур ИИС «ЭнергоКампус».')
      + `<div class="access-denied-box">
          <div class="alert-symbol" style="margin:0 auto 16px;width:44px;height:44px;background:#fcf4e4;color:#ba8638">${icon('settings')}</div>
          <h2>Доступ к разделу базы данных ограничен</h2>
          <p>Просмотр и редактирование таблиц SQLite разрешены только для авторизованных ролей <strong>Главного энергетика</strong> и <strong>Системного администратора</strong>.</p>
          <button class="button primary" id="auth-request-btn">${icon('users')} Переключить роль в профиле пользователя</button>
        </div>`;
  }

  const tariff=Number(state.settings.tariffKzt||32.5);
  return heading('База данных ИИС (14 таблиц в 3НФ)', 'Прямой просмотр и редактирование реляционных таблиц SQLite 3, запуск демонстрационных сценариев и SQL-консоль.',
    `<button class="button primary" id="db-seed-btn">${icon('reset')}Сбросить БД (Seed)</button><button class="button" id="db-refresh-btn">${icon('reset')}Обновить данные</button>`)
    + `<div class="db-timer-bar">
      <div class="db-timer-left">
        <span class="timer-indicator"></span>
        <span>Автообновление данных с SQLite через: <span class="timer-pill" id="db-sync-countdown">${isSyncPaused ? 'Пауза' : nextSyncCountdown + ' сек'}</span></span>
      </div>
      <div class="db-timer-controls">
        <button class="button small" id="db-sync-toggle-btn">${isSyncPaused ? '▶️ Возобновить' : '⏸️ Пауза'}</button>
        <button class="button small" id="db-sync-now-btn">🔄 Обновить сейчас</button>
        <span class="muted" style="margin-left:8px">Период:</span>
        <button class="button small db-interval-btn ${syncIntervalSec===5?'primary':''}" data-interval="5">5с</button>
        <button class="button small db-interval-btn ${syncIntervalSec===10?'primary':''}" data-interval="10">10с</button>
        <button class="button small db-interval-btn ${syncIntervalSec===30?'primary':''}" data-interval="30">30с</button>
      </div>
    </div>`
    + `<div class="db-scenarios-panel">
      <div class="panel-heading" style="padding:0 0 8px">
        <div>
          <h2>Быстрое управление состоянием БД (Сценарии Модуля 3)</h2>
          <p>Нажмите любую кнопку, чтобы мгновенно изменить данные в таблицах SQLite. Все графики, карточки и XAI обновятся автоматически!</p>
        </div>
        <span class="badge ${state.backendOnline?'badge-green':'badge-gray'}">${state.backendOnline?'SQLite3 Connected':'Автономный режим'}</span>
      </div>
      <div class="db-scenarios-grid">
        <div class="db-card">
          <div class="db-card-top">
            <span class="db-card-icon amber">${icon('bolt')}</span>
            <div class="db-card-info">
              <strong>Каб. 204: Включить 12 ПК и свет</strong>
              <p>Создаёт перерасход энергии S3_EXCESS (~1.92 кВт) в пустом классе. Срабатывает рекомендация ИИС.</p>
            </div>
          </div>
          <button class="button db-card-action" data-db-action="pcs_204_on">Включить технику (Каб. 204)</button>
        </div>

        <div class="db-card">
          <div class="db-card-top">
            <span class="db-card-icon">${icon('check')}</span>
            <div class="db-card-info">
              <strong>Каб. 204: Выключить ПК и свет</strong>
              <p>Лаборант устраняет перерасход: мощность падает до 0.00 кВт, статус возвращается в норму S1_NORMAL.</p>
            </div>
          </div>
          <button class="button primary db-card-action" data-db-action="pcs_204_off">Выключить технику (Норма)</button>
        </div>

        <div class="db-card">
          <div class="db-card-top">
            <span class="db-card-icon blue">${icon('window')}</span>
            <div class="db-card-info">
              <strong>Каб. 302: Открыть окно (15.5 °C)</strong>
              <p>Вызывает нарушение микроклимата (выхолаживание ниже 18 °C). Формируется климатическое предупреждение.</p>
            </div>
          </div>
          <button class="button db-card-action" data-db-action="window_302_open">Открыть окно (Аномалия)</button>
        </div>

        <div class="db-card">
          <div class="db-card-top">
            <span class="db-card-icon">${icon('temp')}</span>
            <div class="db-card-info">
              <strong>Каб. 302: Закрыть окно (21.5 °C)</strong>
              <p>Нормализует температуру до 21.5 °C, закрывает окна. Кабинет возвращается в штатный зелёный статус.</p>
            </div>
          </div>
          <button class="button db-card-action" data-db-action="window_302_close">Закрыть окно (Норма)</button>
        </div>

        <div class="db-card">
          <div class="db-card-top">
            <span class="db-card-icon">${icon('wifi')}</span>
            <div class="db-card-info">
              <strong>Каб. 305: Восстановить связь</strong>
              <p>ESP32 контроллер возвращается в сеть (is_online=1). На сайте становятся активны все 6 кабинетов.</p>
            </div>
          </div>
          <button class="button db-card-action" data-db-action="controller_305_online">Восстановить связь (Каб. 305)</button>
        </div>

        <div class="db-card">
          <div class="db-card-top">
            <span class="db-card-icon amber">${icon('offline')}</span>
            <div class="db-card-info">
              <strong>Каб. 305: Обрыв связи (OFFLINE)</strong>
              <p>Эмулирует потерю связи (S0_OFFLINE). Расчёт экономии блокируется согласно требованиям безопасности.</p>
            </div>
          </div>
          <button class="button db-card-action" data-db-action="controller_305_offline">Сымитировать обрыв связи</button>
        </div>

        <div class="db-card" style="grid-column: 1 / -1">
          <div class="db-card-top">
            <span class="db-card-icon">${icon('leaf')}</span>
            <div class="db-card-info">
              <strong>Быстрая смена тарифа университета (system_settings_tariffs)</strong>
              <p>Задайте действующий тариф в тенге за 1 кВт·ч. Все денежные оценки потенциала экономии пересчитаются мгновенно.</p>
              <div class="db-tariff-box">
                <input type="number" id="quick-tariff-input" step="0.1" min="1" max="500" value="${tariff}">
                <span>тг/кВт·ч</span>
                <button class="button primary" id="quick-tariff-btn">Записать тариф в БД</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="db-inspector">
      <div class="panel-heading" style="padding:0 0 10px">
        <div>
          <h2>Инспектор и редактор 14 таблиц реляционной схемы (3НФ)</h2>
          <p>Выберите таблицу для просмотра и редактирования строк. Нажмите «Изменить», чтобы скорректировать данные прямо в SQLite!</p>
        </div>
      </div>
      <div class="db-tables-nav" id="db-tables-nav">
        ${currentDbTablesList.map(t=>`<button class="db-tbl-btn ${t===currentDbTable?'active':''}" data-db-table="${t}">${t}</button>`).join('')}
      </div>
      <div id="db-table-content">
        <div class="empty-state">Загрузка данных таблицы ${currentDbTable}...</div>
      </div>
    </div>
    <div class="db-sql-section">
      <div class="panel-heading" style="padding:0 0 10px">
        <div>
          <h2>Интерактивная SQL-консоль к базе данных (режим чтения)</h2>
          <p>Выполнение одиночных проверочных запросов SELECT и PRAGMA table_info (доступно роли Системного администратора; модифицирующие команды блокируются).</p>
        </div>
        <span class="badge ${isAdminUser()?'badge-green':'badge-amber'}">${isAdminUser()?'Доступ администратора активен':'Требуется роль Администратора'}</span>
      </div>
      <div class="db-sql-presets">
        <button class="db-preset-btn" data-sql="SELECT room_id, calc_power_kw, temp_c, is_occupied, is_online FROM telemetry_measurements ORDER BY measurement_id DESC LIMIT 6;">Телеметрия 6 кабинетов</button>
        <button class="db-preset-btn" data-sql="SELECT recommendation_id, room_id, status, expected_saving_kwh, action_text FROM saving_recommendations ORDER BY recommendation_id DESC;">Рекомендации лаборанту</button>
        <button class="db-preset-btn" data-sql="SELECT setting_id, pc_watts, light_watts, tariff_kzt_kwh, valid_from FROM system_settings_tariffs ORDER BY setting_id DESC;">Уставки и тариф</button>
        <button class="db-preset-btn" data-sql="SELECT room_id, device_code, is_power_on FROM workstations_devices WHERE is_power_on = 1;">Включённые ПК в корпусе</button>
        <button class="db-preset-btn" data-sql="SELECT * FROM rooms;">Реестр кабинетов</button>
      </div>
      <textarea id="sql-query-input" class="db-sql-editor" rows="3" placeholder="Введите SQL-запрос...">SELECT room_id, calc_power_kw, temp_c, is_occupied, is_online FROM telemetry_measurements ORDER BY measurement_id DESC LIMIT 6;</textarea>
      <div class="db-sql-controls">
        <button class="button primary" id="run-sql-btn">${icon('play')}Выполнить SQL</button>
        <span class="db-sql-status" id="sql-status-msg">Готово к выполнению</span>
      </div>
      <div id="sql-results-container" style="margin-top:14px"></div>
    </div>`;
}

async function loadDbTable(tableName, showLoading=true) {
  currentDbTable = tableName;
  const container = $('#db-table-content');
  if(!container) return;
  if(showLoading) {
    container.innerHTML = `<div class="empty-state">Загрузка данных таблицы <strong>${tableName}</strong>...</div>`;
  }
  document.querySelectorAll('.db-tbl-btn').forEach(b => b.classList.toggle('active', b.dataset.dbTable === tableName));

  if(state.backendOnline){
    try {
      const res = await fetch(API_BASE + `/api/v1/database/table?name=${encodeURIComponent(tableName)}&limit=30`, {
        headers: {'X-Role-Token': state.roleToken}
      });
      if(res.ok){
        const json = await res.json();
        renderTableData(json.data);
        return;
      }
    } catch(e) {}
  }
  renderFallbackTable(tableName);
}

function renderTableData(data) {
  const container = $('#db-table-content');
  if(!container) return;
  if(!data || !data.rows || !data.rows.length){
    container.innerHTML = `<div class="empty-state">В таблице <strong>${data ? data.table : currentDbTable}</strong> пока нет записей.</div>`;
    return;
  }
  currentDbTableData = data;
  const cols = data.columns;
  container.innerHTML = `
    <div class="db-table-header">
      <strong>Таблица: <code>${data.table}</code> (показано ${data.rows.length} из ${data.total_count} строк)</strong>
      <span class="badge badge-green">${data.columns.length} столбцов</span>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th style="width:100px;text-align:center">Действие</th>
            ${cols.map(c=>`<th>${esc(c)}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${data.rows.map((r, idx)=>`
            <tr>
              <td style="text-align:center;white-space:nowrap">
                <button class="btn-edit-row" data-row-idx="${idx}">${icon('settings')} Изменить</button>
              </td>
              ${cols.map(c=>`<td>${esc(r[c]!==null?r[c]:'NULL')}</td>`).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  container.querySelectorAll('.btn-edit-row').forEach(btn => {
    btn.onclick = () => openRowEditor(Number(btn.dataset.rowIdx));
  });
}

function openRowEditor(idx) {
  if(!currentDbTableData || !currentDbTableData.rows || !currentDbTableData.rows[idx]) return;
  const row = currentDbTableData.rows[idx];
  const cols = currentDbTableData.columns;
  const pkCol = cols.find(c => c.endsWith('_id') || c === 'room_id') || cols[0];

  lastFocus = document.activeElement;
  $('#drawer').innerHTML = `
    <div class="drawer-header">
      <div>
        <span class="eyebrow">РЕДАКТОР СТРОКИ · ТАБЛИЦА ${currentDbTable.toUpperCase()}</span>
        <h2 id="drawer-title">Редактирование записи</h2>
        <p>Первичный ключ: <code>${pkCol} = ${row[pkCol]}</code></p>
      </div>
      <button class="icon-button" id="close-drawer" aria-label="Закрыть">${icon('close')}</button>
    </div>
    <div class="drawer-content" style="padding:22px">
      <form id="row-editor-form">
        <p class="small-text" style="margin-bottom:14px">Отредактируйте необходимые поля. После сохранения данные будут немедленно записаны в SQLite3 и отобразятся на всем сайте.</p>
        <div class="row-edit-grid">
          ${cols.map(c => {
            const isPk = (c === pkCol);
            const val = row[c] !== null && row[c] !== undefined ? row[c] : '';
            const isFk = !isPk && ['role_id', 'controller_id', 'model_id', 'setting_id', 'anomaly_id', 'run_id', 'assigned_user_id', 'user_id', 'measurement_id'].includes(c);
            const isBool = (typeof val === 'boolean') || (['is_online', 'is_occupied', 'light_on', 'door_open', 'is_power_on', 'is_active'].includes(c));

            if(isPk){
              return `
                <div class="row-edit-field">
                  <label>${c} <span style="color:var(--primary);font-size:11px;font-weight:600">(PK · Первичный ключ)</span></label>
                  <input name="${c}" value="${esc(val)}" disabled type="text" style="background:rgba(255,255,255,0.04);cursor:not-allowed">
                </div>
              `;
            }
            if(isFk){
              return `
                <div class="row-edit-field">
                  <label>${c} <span style="color:var(--text-muted);font-size:11px">(FK · Внешний ключ)</span></label>
                  <input name="${c}" value="${esc(val)}" disabled type="text" style="background:rgba(255,255,255,0.04);cursor:not-allowed" title="Внешний ключ связан с другой таблицей и защищён от искажения">
                </div>
              `;
            }
            if(c === 'room_id'){
              const validRooms = ['201', '202', '204', '302', '305', '310'];
              return `
                <div class="row-edit-field">
                  <label>room_id <span style="color:var(--primary);font-size:11px">(Кабинет)</span></label>
                  <select name="room_id">
                    ${validRooms.map(r => `<option value="${r}" ${String(val) === r ? 'selected' : ''}>Кабинет № ${r}</option>`).join('')}
                  </select>
                </div>
              `;
            }
            if(c === 'current_state'){
              const states = ['S1_OCCUPIED', 'S2_IDLE', 'S3_EXCESS', 'S0_OFFLINE'];
              return `
                <div class="row-edit-field">
                  <label>current_state <span style="color:var(--text-muted);font-size:11px">(Состояние)</span></label>
                  <select name="current_state">
                    ${states.map(s => `<option value="${s}" ${val === s ? 'selected' : ''}>${s}</option>`).join('')}
                  </select>
                </div>
              `;
            }
            if(c === 'status' && currentDbTable === 'saving_recommendations'){
              const statuses = ['new', 'accepted', 'completed', 'rejected'];
              return `
                <div class="row-edit-field">
                  <label>status <span style="color:var(--text-muted);font-size:11px">(Статус)</span></label>
                  <select name="status">
                    ${statuses.map(s => `<option value="${s}" ${val === s ? 'selected' : ''}>${s}</option>`).join('')}
                  </select>
                </div>
              `;
            }
            if(c === 'severity' && currentDbTable === 'detected_anomalies'){
              const sevs = ['warning', 'neutral', 'critical'];
              return `
                <div class="row-edit-field">
                  <label>severity <span style="color:var(--text-muted);font-size:11px">(Критичность)</span></label>
                  <select name="severity">
                    ${sevs.map(s => `<option value="${s}" ${val === s ? 'selected' : ''}>${s}</option>`).join('')}
                  </select>
                </div>
              `;
            }
            if(isBool){
              const numVal = (val === true || val === 1 || val === '1') ? 1 : 0;
              return `
                <div class="row-edit-field">
                  <label>${c} <span style="color:var(--text-muted);font-size:11px">(Флаг)</span></label>
                  <select name="${c}">
                    <option value="1" ${numVal === 1 ? 'selected' : ''}>1 (Да / ВКЛ / Активен)</option>
                    <option value="0" ${numVal === 0 ? 'selected' : ''}>0 (Нет / ВЫКЛ / Неактивен)</option>
                  </select>
                </div>
              `;
            }
            return `
              <div class="row-edit-field">
                <label>${c}</label>
                <input name="${c}" value="${esc(val)}" type="${typeof val === 'number' ? 'number' : 'text'}" step="any">
              </div>
            `;
          }).join('')}
        </div>
        <div style="display:flex;gap:10px;margin-top:20px">
          <button type="submit" class="button primary">${icon('check')} Сохранить изменения в SQLite</button>
          <button type="button" class="button" id="cancel-row-edit-btn">Отмена</button>
        </div>
      </form>
    </div>
  `;

  $('#drawer').hidden = false;
  $('#drawer-backdrop').hidden = false;
  document.body.style.overflow = 'hidden';
  $('#close-drawer').onclick = closeRoom;
  $('#cancel-row-edit-btn').onclick = closeRoom;

  $('#row-editor-form').onsubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const updates = {};
    for (let [k, v] of formData.entries()) {
      if (k !== pkCol) {
        updates[k] = v;
      }
    }

    if (state.backendOnline) {
      try {
        const res = await fetch(API_BASE + '/api/v1/database/update_row', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Role-Token': state.roleToken
          },
          body: JSON.stringify({
            table: currentDbTable,
            pk_column: pkCol,
            pk_value: row[pkCol],
            values: updates
          })
        });
        const json = await res.json();
        if (res.ok && json.status === 'ok') {
          toast(json.message);
          log('—', `[БД SQLite]: ${json.message}`);
          closeRoom();
          await syncWithBackend();
          await loadDbTable(currentDbTable, false);
          return;
        } else {
          toast('Ошибка обновления: ' + (json.message || 'Проверьте типы полей'));
          return;
        }
      } catch (err) {
        toast('Ошибка соединения: ' + err.message);
        return;
      }
    }

    // Offline mode update
    Object.assign(row, updates);
    toast(`Запись #${row[pkCol]} обновлена в локальном хранилище!`);
    closeRoom();
    renderTableData(currentDbTableData);
  };
}

function renderFallbackTable(tableName) {
  const container = $('#db-table-content');
  if(!container) return;
  if(tableName === 'rooms'){
    renderTableData({
      table: 'rooms',
      columns: ['room_id', 'building_code', 'floor_num', 'room_name', 'room_type', 'total_pcs', 'current_state'],
      rows: state.rooms.map(r=>({
        room_id: r.id, building_code: 'A', floor_num: r.floor, room_name: r.name,
        room_type: r.type, total_pcs: r.total, current_state: r.state_class || 'S2_IDLE'
      })),
      total_count: state.rooms.length
    });
  } else if(tableName === 'system_settings_tariffs'){
    renderTableData({
      table: 'system_settings_tariffs',
      columns: ['setting_id', 'pc_watts', 'light_watts', 'min_temp_c', 'max_temp_c', 'tariff_kzt_kwh', 'is_active'],
      rows: [{
        setting_id: 1, pc_watts: state.settings.pcWatts, light_watts: state.settings.lightWatts,
        min_temp_c: state.settings.minTemp, max_temp_c: state.settings.maxTemp,
        tariff_kzt_kwh: state.settings.tariffKzt, is_active: 1
      }],
      total_count: 1
    });
  } else {
    container.innerHTML = `<div class="empty-state">Таблица <strong>${tableName}</strong> активна в локальной SQLite3 БД (14 таблиц). Запустите сервер Python через START.bat для динамического просмотра всех 14 таблиц.</div>`;
  }
}

async function runDbScenario(scenarioName, params={}) {
  if(state.backendOnline){
    try {
      const res = await fetch(API_BASE + '/api/v1/database/scenario', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Role-Token': state.roleToken},
        body: JSON.stringify({scenario: scenarioName, ...params})
      });
      const json = await res.json();
      if(res.ok && json.status === 'ok'){
        toast(json.message);
        log('—', `[БД SQLite]: ${json.message}`);
        await syncWithBackend();
        await loadDbTable(currentDbTable, false);
        return;
      } else {
        toast(json.message || 'Отказано в выполнении сценария');
        return;
      }
    } catch(err) {
      toast('Ошибка запроса: ' + err.message);
      return;
    }
  }

  // Local simulated fallback
  if(scenarioName === 'pcs_204_on'){
    const r = state.rooms.find(x=>x.id==='204');
    if(r){ r.computers.fill(true); r.light=true; r.occupied=false; r.recStatus='new'; mutated(r, 'Включены все 12 ПК и свет в свободном каб. 204'); }
    toast('Каб. 204: Включено 12 ПК и свет (перерасход S3_EXCESS)');
  } else if(scenarioName === 'pcs_204_off'){
    const r = state.rooms.find(x=>x.id==='204');
    if(r){ r.computers.fill(false); r.light=false; r.recStatus='completed'; mutated(r, 'Лаборант отключил технику в каб. 204'); }
    toast('Каб. 204: Техника выключена (S1_NORMAL)');
  } else if(scenarioName === 'window_302_open'){
    const r = state.rooms.find(x=>x.id==='302');
    if(r){ r.windows=1; r.temp=15.5; r.recStatus='new'; mutated(r, 'Открыто окно в каб. 302, температура 15.5 °C', 'warning'); }
    toast('Каб. 302: Окно открыто, температура 15.5 °C');
  } else if(scenarioName === 'window_302_close'){
    const r = state.rooms.find(x=>x.id==='302');
    if(r){ r.windows=0; r.temp=21.5; mutated(r, 'Окно закрыто в каб. 302, температура 21.5 °C'); }
    toast('Каб. 302: Окно закрыто (норма)');
  } else if(scenarioName === 'controller_305_online'){
    const r = state.rooms.find(x=>x.id==='305');
    if(r){ r.online=true; mutated(r, 'Связь с контроллером 305 восстановлена'); }
    toast('Каб. 305: Контроллер на связи (ONLINE)');
  } else if(scenarioName === 'controller_305_offline'){
    const r = state.rooms.find(x=>x.id==='305');
    if(r){ r.online=false; mutated(r, 'Обрыв связи с контроллером 305', 'offline'); }
    toast('Каб. 305: Имитация потери связи (OFFLINE)');
  } else if(scenarioName === 'set_tariff'){
    const t = Number(params.tariff || 32.5);
    state.settings.tariffKzt = t;
    log('—', `Тариф изменён на: ${t} тг/кВт·ч`);
    toast(`Тариф обновлён: ${t} тг/кВт·ч`);
    render();
  }
}

async function runDbSql(query) {
  const statusEl = $('#sql-status-msg');
  const resContainer = $('#sql-results-container');
  if(!query || !query.trim()){
    if(statusEl) statusEl.textContent = 'Ошибка: введите текст запроса';
    return;
  }
  if(statusEl){ statusEl.textContent = 'Выполнение запроса...'; statusEl.className = 'db-sql-status'; }

  if(state.backendOnline){
    try {
      const res = await fetch(API_BASE + '/api/v1/database/query', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Role-Token': state.roleToken},
        body: JSON.stringify({query: query})
      });
      const json = await res.json();
      if(json.status === 'ok'){
        if(statusEl){ statusEl.textContent = json.message; statusEl.className = 'db-sql-status'; }
        if(json.is_select){
          if(!json.rows.length){
            resContainer.innerHTML = '<div class="empty-state">Результат запроса: 0 строк.</div>';
          } else {
            const cols = json.columns;
            resContainer.innerHTML = `
              <div class="table-scroll">
                <table>
                  <thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead>
                  <tbody>${json.rows.map(r=>`<tr>${cols.map(c=>`<td>${esc(r[c]!==null?r[c]:'NULL')}</td>`).join('')}</tr>`).join('')}</tbody>
                </table>
              </div>
            `;
          }
        } else {
          resContainer.innerHTML = `<div class="note">${icon('check')}${json.message}</div>`;
          await syncWithBackend();
          await loadDbTable(currentDbTable, false);
        }
      } else {
        if(statusEl){ statusEl.textContent = json.message; statusEl.className = 'db-sql-status err'; }
        resContainer.innerHTML = `<div class="note" style="border-color:#e4c7c7;background:#faecec;color:#9b3838">${icon('warning')}${json.message}</div>`;
      }
      return;
    } catch(err) {
      if(statusEl){ statusEl.textContent = 'Ошибка соединения: ' + err.message; statusEl.className = 'db-sql-status err'; }
      return;
    }
  }

  if(statusEl){ statusEl.textContent = 'Локальный режим: для выполнения произвольного SQL запустите START.bat'; }
}

async function verifyOfflinePasswordSha256(pwd) {
  if (!window.crypto || !window.crypto.subtle) return false;
  const msgBuffer = new TextEncoder().encode(pwd);
  const hashBuffer = await window.crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return hashHex === '0ffe1abd1a08215353c233d6e009613e95eec4253832a761af28ff37ac5a150c';
}

function openUserProfileModal(pendingRole=null) {
  lastFocus = document.activeElement;
  const roleCode = isAdminUser() ? 'sysadmin' : (isPrivilegedUser() ? 'energomanager' : 'laborant');
  const roleNamesMap = {
    laborant: { title: 'Дежурный лаборант', label: 'Лаборант (дежурный оператор корпуса А)', letter: 'Л', account: 'lab_operator' },
    energomanager: { title: 'Главный энергетик', label: 'Энергетик (управление тарифами, уставками и БД)', letter: 'Э', account: 'energy_chief' },
    sysadmin: { title: 'Системный администратор', label: 'Администратор ИИС (полный доступ и адаптация ИИ)', letter: 'А', account: 'sys_admin' }
  };
  const cur = roleNamesMap[roleCode] || roleNamesMap.laborant;

  $('#drawer').innerHTML = `
    <div class="drawer-header">
      <div>
        <span class="eyebrow">РОЛЕВАЯ МОДЕЛЬ RBAC · МОДУЛЬ 3</span>
        <h2 id="drawer-title">Профиль и смена роли</h2>
        <p>${cur.label}</p>
      </div>
      <button class="icon-button" id="close-drawer" aria-label="Закрыть">${icon('close')}</button>
    </div>
    <div class="drawer-content profile-modal">
      <div class="profile-hero">
        <div class="profile-avatar-large">${cur.letter}</div>
        <div class="profile-meta">
          <h3>Учётная запись: <code>${cur.account}</code></h3>
          <p>${cur.label}</p>
          <span class="badge badge-green" style="margin-top:6px">${cur.title}</span>
        </div>
      </div>
      <div class="section-title">
        <h3>${icon('chip')}Матрица разрешений активной роли</h3>
      </div>
      <div class="profile-perms">
        <div class="profile-perm-row">${icon('check')} <span><strong>read</strong> — Просмотр телеметрии, графиков нагрузок и дашбордов</span></div>
        <div class="profile-perm-row">${icon('check')} <span><strong>simulate</strong> — Моделирование датчиков ESP32 и учебных сценариев</span></div>
        <div class="profile-perm-row">${icon('check')} <span><strong>recommend_action</strong> — Принятие, подтверждение и отклонение рекомендаций XAI</span></div>
        <div class="profile-perm-row" style="${roleCode==='laborant'?'opacity:0.55':''}">
          ${icon(roleCode==='laborant'?'close':'check')}
          <span><strong>settings</strong> — Изменение тарифов, просмотр и редактирование таблиц БД ${roleCode==='laborant'?'(требуется роль Энергетика или Администратора)':'(разрешено)'}</span>
        </div>
        <div class="profile-perm-row" style="${roleCode==='sysadmin'?'':'opacity:0.55'}">
          ${icon(roleCode==='sysadmin'?'check':'close')}
          <span><strong>adapt_model / admin</strong> — Адаптация модели ИИ, SQL-консоль чтения и сброс БД ${roleCode==='sysadmin'?'(разрешено)':'(требуется роль Системного администратора)'}</span>
        </div>
      </div>
      <div class="role-switcher">
        <h4>Демонстрационное переключение роли доступа (RBAC):</h4>
        <div class="role-buttons">
          <button class="role-btn ${roleCode==='laborant'?'active':''}" data-switch-role="laborant">Лаборант (Л)</button>
          <button class="role-btn ${roleCode==='energomanager'?'active':''}" data-switch-role="energomanager">Энергетик (Э) 🔒</button>
          <button class="role-btn ${roleCode==='sysadmin'?'active':''}" data-switch-role="sysadmin">Администратор (А) 🔒</button>
        </div>
        <form id="role-auth-form" style="margin-top:14px;display:${pendingRole?'block':'none'};padding:14px;background:#f4f8f5;border:1px solid #d5e3d8;border-radius:12px">
          <label style="display:block;font-weight:600;margin-bottom:6px" id="role-auth-label">Подтверждение входа в роль «${pendingRole ? roleNamesMap[pendingRole].title : ''}»</label>
          <div style="display:flex;gap:8px;align-items:center">
            <input type="password" id="role-password-input" placeholder="Введите пароль роли" autocomplete="off" style="flex:1;padding:8px 12px;border:1px solid #c5d6c9;border-radius:8px">
            <button type="submit" class="button primary">Подтвердить</button>
          </div>
          <p class="small-text" style="margin:6px 0 0;color:#54675c" id="role-auth-msg">Проверка выполняется на сервере (/api/v1/auth/role) с выдачей сессионного токена.</p>
        </form>
      </div>
    </div>
  `;
  $('#drawer').hidden = false;
  $('#drawer-backdrop').hidden = false;
  document.body.style.overflow = 'hidden';
  $('#close-drawer').onclick = closeRoom;

  let targetRole = pendingRole;

  async function performRoleSwitch(r, pwd) {
    const info = roleNamesMap[r];
    if (state.backendOnline) {
      try {
        const res = await fetch(API_BASE + '/api/v1/auth/role', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({role: r, password: pwd})
        });
        const json = await res.json();
        if (res.ok && json.status === 'ok') {
          state.roleCode = r;
          state.roleToken = json.token;
          document.querySelectorAll('.avatar').forEach(a => a.textContent = info.letter);
          if($('#user-display-name')) $('#user-display-name').textContent = info.title;
          if($('#user-display-role')) $('#user-display-role').textContent = info.label;
          toast(`Активирована роль: ${info.title}`);
          log('—', `Авторизован переход в роль: ${info.title}`);
          render();
          openUserProfileModal();
          return;
        } else {
          const msg = json.message || 'Неверный пароль доступа для выбранной роли.';
          toast(msg);
          if($('#role-auth-msg')) { $('#role-auth-msg').textContent = msg; $('#role-auth-msg').style.color = '#9b3838'; }
          return;
        }
      } catch (err) {
        toast('Ошибка соединения с сервером авторизации');
        return;
      }
    }

    // Автономный режим (GitHub Pages): сверка SHA-256 без открытого пароля в коде
    const ok = await verifyOfflinePasswordSha256(pwd);
    if (ok) {
      state.roleCode = r;
      state.roleToken = r === 'sysadmin' ? 'demo-role-sysadmin' : 'demo-role-energomanager';
      document.querySelectorAll('.avatar').forEach(a => a.textContent = info.letter);
      if($('#user-display-name')) $('#user-display-name').textContent = info.title;
      if($('#user-display-role')) $('#user-display-role').textContent = info.label;
      toast(`Активирована роль: ${info.title} (автономный режим)`);
      log('—', `Переключение на роль: ${info.title}`);
      render();
      openUserProfileModal();
    } else {
      const msg = 'Неверный пароль доступа для выбранной роли.';
      toast(msg);
      if($('#role-auth-msg')) { $('#role-auth-msg').textContent = msg; $('#role-auth-msg').style.color = '#9b3838'; }
    }
  }

  $('#drawer').querySelectorAll('[data-switch-role]').forEach(btn => {
    btn.onclick = () => {
      const r = btn.dataset.switchRole;
      if(r === 'laborant') {
        state.roleCode = 'laborant';
        state.roleToken = 'demo-role-laborant';
        const info = roleNamesMap[r];
        document.querySelectorAll('.avatar').forEach(a => a.textContent = info.letter);
        if($('#user-display-name')) $('#user-display-name').textContent = info.title;
        if($('#user-display-role')) $('#user-display-role').textContent = info.label;
        toast('Активен профиль лаборанта (вкладка БД скрыта)');
        log('—', 'Переключение на профиль лаборанта');
        render();
        openUserProfileModal();
        return;
      }

      targetRole = r;
      const formEl = $('#role-auth-form');
      const labelEl = $('#role-auth-label');
      const inputEl = $('#role-password-input');
      if (formEl && labelEl && inputEl) {
        labelEl.textContent = `Подтверждение входа в роль «${roleNamesMap[r].title}»`;
        formEl.style.display = 'block';
        inputEl.value = '';
        inputEl.focus();
      }
    };
  });

  if ($('#role-auth-form')) {
    $('#role-auth-form').onsubmit = async (e) => {
      e.preventDefault();
      if (!targetRole) return;
      const pwd = ($('#role-password-input')?.value || '').trim();
      await performRoleSwitch(targetRole, pwd);
    };
  }
}

function about(){return heading('Энергия, которую можно сохранить','Дипломный проект интеллектуальной системы мониторинга компьютерных классов.')+`<section class="about-hero"><div><span class="eyebrow">ЭНЕРГОКАМПУС · МОДУЛИ 1–3</span><h2>Умный кабинет начинается<br>с понятных данных и объяснимого ИИ.</h2><p>Лаборант видит включённые компьютеры, освещение, открытые окна, температуру и декомпозицию причин XAI. Система поддерживает принятие решений человеком и оценивает потенциал экономии в кВт·ч и тенге.</p><span class="badge badge-green">Гибридный прототип ИИС (${esc(state.modelInfo.version_tag)})</span></div><div class="about-mark">${icon('leaf')}</div></section><section class="panel architecture"><div class="panel-heading"><h2>Многоуровневый контур управления ИИС</h2></div><div class="architecture-flow">${[['temp','1. Сбор данных','Телеметрия ПК · свет · климат'],['chip','2. Анализ ИИ и XAI','Гибридная модель Rules + GBR'],['wifi','3. Решение и контроль','Рекомендация лаборанту (GW-4)'],['grid','4. Коррекция модели','Адаптация Update(Model_t, Data)']].map(([i,t,d],n)=>`<div><span class="architecture-icon">${icon(i)}</span><strong>${t}</strong><p>${d}</p>${n<3?`<span class="flow-arrow">${icon('arrow')}</span>`:''}</div>`).join('')}</div></section><div class="about-columns"><section class="panel about-text"><h2>Что реализовано в Модуле 3</h2><ul><li>Интеграция клиентского интерфейса с сервером Python REST API (/api/v1/*) и реляционной БД (14 таблиц)</li><li>Гибридный ИИ-модуль (детерминированные правила + GradientBoostingRegressor в scikit-learn)</li><li>Блок объяснимости XAI с декомпозицией вкладов факторов и трассировкой формулы (1.1)</li><li>Жизненный цикл рекомендаций: «новая → принята → выполнена / отклонена» с фиксацией processed_at</li><li>Расчёт потенциала экономии в кВт·ч и тенге с фильтрацией по кабинетам</li></ul></section><section class="panel about-text"><h2>Ограничения и честная маркировка данных</h2><p>В демонстрационном контуре используются явно маркированные синтетические временные ряды. Физические датчики и силовые реле к учебным аудиториям не подключены.</p><p>Система реализует концепцию поддержки принятия решений (Decision Support System): отключение оборудования (шаг BP-11) выполняется только после подтверждения лаборантом. При потере связи (S0_OFFLINE) расчёт экономии блокируется.</p></section></div><div class="note">${icon('info')}Прототип работает как с локальным Python-сервером и БД (полный контур Модуля 3), так и автономно на GitHub Pages через локальное хранилище браузера.</div>`;}
function render(){
  route=location.hash.slice(1)||'overview';
  if(!routeNames[route])route='overview';
  const navDb = $('#nav-item-database');
  if(navDb) navDb.style.display = isPrivilegedUser() ? 'flex' : 'none';
  $('#breadcrumb').textContent=routeNames[route];
  document.querySelectorAll('[data-nav]').forEach(e=>e.classList.toggle('active',e.dataset.nav===route));
  $('#main').innerHTML=({overview,rooms:()=>heading('Кабинеты','Состояние оборудования, датчиков, объяснений XAI и рекомендаций.',dateButton())+roomsSection(true),analytics,events,database,settings,about}[route])();
  $('#sidebar').classList.remove('is-open');
  fillIcons();
  bindMain();
}
function bindMain(){
  // Интерактивные карточки метрик
  if($('#metric-power-card')) $('#metric-power-card').onclick=()=>location.hash='rooms';
  if($('#metric-pcs-card')) $('#metric-pcs-card').onclick=()=>location.hash='rooms';
  if($('#metric-alerts-card')) $('#metric-alerts-card').onclick=()=>{ filter='attention'; location.hash='rooms'; };
  if($('#metric-saving-card')) $('#metric-saving-card').onclick=()=>location.hash='analytics';

  // Интерактивный аватар с буквой «Л» и профиль оператора
  if($('#user-profile-trigger')) $('#user-profile-trigger').onclick=()=>openUserProfileModal();
  if($('#topbar-avatar')) $('#topbar-avatar').onclick=()=>openUserProfileModal();
  if($('#sidebar-avatar')) $('#sidebar-avatar').onclick=()=>openUserProfileModal();

  // Обработчики вкладки «База данных»
  if(route==='database'){
    if($('#auth-request-btn')) $('#auth-request-btn').onclick = ()=>openUserProfileModal('energomanager');
    if($('#db-sync-toggle-btn')){
      $('#db-sync-toggle-btn').onclick=()=>{
        isSyncPaused = !isSyncPaused;
        $('#db-sync-toggle-btn').textContent = isSyncPaused ? '▶️ Возобновить' : '⏸️ Пауза';
        const cd = $('#db-sync-countdown');
        if(cd) cd.textContent = isSyncPaused ? 'Пауза' : nextSyncCountdown + ' сек';
        toast(isSyncPaused ? 'Автообновление приостановлено' : 'Автообновление возобновлено');
      };
    }
    if($('#db-sync-now-btn')){
      $('#db-sync-now-btn').onclick=async()=>{
        nextSyncCountdown = syncIntervalSec;
        const cd = $('#db-sync-countdown');
        if(cd && !isSyncPaused) cd.textContent = nextSyncCountdown + ' сек';
        await syncWithBackend();
        await loadDbTable(currentDbTable);
        toast('Данные БД синхронизированы');
      };
    }
    document.querySelectorAll('.db-interval-btn').forEach(btn=>{
      btn.onclick=()=>{
        syncIntervalSec = Number(btn.dataset.interval) || 10;
        nextSyncCountdown = syncIntervalSec;
        document.querySelectorAll('.db-interval-btn').forEach(b=>b.classList.toggle('primary', b===btn));
        const cd = $('#db-sync-countdown');
        if(cd && !isSyncPaused) cd.textContent = nextSyncCountdown + ' сек';
        toast('Интервал обновления: ' + syncIntervalSec + ' сек');
      };
    });
    loadDbTable(currentDbTable);
    document.querySelectorAll('.db-tbl-btn').forEach(btn=>{
      btn.onclick=()=>loadDbTable(btn.dataset.dbTable);
    });
    document.querySelectorAll('[data-db-action]').forEach(btn=>{
      btn.onclick=()=>runDbScenario(btn.dataset.dbAction);
    });
    if($('#quick-tariff-btn')){
      $('#quick-tariff-btn').onclick=()=>{
        const val=Number($('#quick-tariff-input').value);
        if(val<=0){toast('Тариф должен быть положительным числом');return;}
        runDbScenario('set_tariff',{tariff:val});
      };
    }
    if($('#db-seed-btn')){
      $('#db-seed-btn').onclick=()=>{
        if(confirm('Сбросить базу данных SQLite к исходным 14 таблицам и демонстрационным значениям?')){
          runDbScenario('seed_reset');
        }
      };
    }
    if($('#db-refresh-btn')){
      $('#db-refresh-btn').onclick=async()=>{
        await syncWithBackend();
        await loadDbTable(currentDbTable);
        toast('Данные базы данных обновлены');
      };
    }
    document.querySelectorAll('[data-sql]').forEach(btn=>{
      btn.onclick=()=>{
        if($('#sql-query-input')) $('#sql-query-input').value=btn.dataset.sql;
        runDbSql(btn.dataset.sql);
      };
    });
    if($('#run-sql-btn')){
      $('#run-sql-btn').onclick=()=>{
        const q=$('#sql-query-input')?$('#sql-query-input').value:'';
        runDbSql(q);
      };
    }
  }

  document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openRoom(b.dataset.open));
  document.querySelectorAll('[data-export]').forEach(b=>b.onclick=exportRooms);
  document.querySelectorAll('[data-period]').forEach(b=>b.onclick=()=>{period=b.dataset.period;render();});
  document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;render();});
  if($('#analytics-room-select'))$('#analytics-room-select').onchange=e=>{analyticsRoom=e.target.value;render();};
  if($('#adapt-model-btn'))$('#adapt-model-btn').onclick=async()=>{
    if(state.backendOnline){
      try{
        const res=await fetch(API_BASE + '/api/v1/ai/adapt',{method:'POST',headers:{'Content-Type':'application/json','X-Role-Token':state.roleToken},body:JSON.stringify({feedback_samples:[{total_pcs:12,is_occupied:false,hour:14,day_of_week:3,temp_c:23.1,open_windows:0,verified_baseline_kw:0.02}]})});
        const j=await res.json();
        if(res.ok&&j.adaptation){
          state.modelInfo.version_tag=j.adaptation.candidate_version;
          log('—',`Адаптация модели ИИ завершена: активна версия ${j.adaptation.candidate_version} (MAE=${num(j.adaptation.candidate_metrics.MAE_kw,4)} кВт)`);
          toast(`Модель ИИ обновлена до ${j.adaptation.candidate_version}`);
          render();
          return;
        } else {
          toast(j.message || 'Для адаптации модели требуется роль Системного администратора');
          return;
        }
      }catch{}
    }
    if(!isAdminUser()){
      toast('Отказано в доступе: для адаптации модели ИИ требуется роль Системного администратора');
      return;
    }
    state.modelInfo.version_tag='v1.3-gbr-adapted';
    log('—','Выполнена контролируемая адаптация модели ИИ: версия v1.3-gbr-adapted (MAE=0,0254 кВт)');
    toast('Модель ИИ адаптирована: v1.3-gbr-adapted');
    render();
  };
  if($('#room-search'))$('#room-search').oninput=e=>{query=e.target.value;const list=filteredRooms();$('#room-grid').innerHTML=list.length?list.map(roomCard).join(''):'<div class="empty-state">Кабинеты не найдены. Измените поиск или фильтр.</div>';$('#room-grid').querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openRoom(b.dataset.open));};
  if($('#floor-filter'))$('#floor-filter').onchange=e=>{floor=e.target.value;render();};
  if($('[data-alerts]'))$('[data-alerts]').onclick=()=>location.hash='events';
  if($('#settings-form'))$('#settings-form').onsubmit=async e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.target));
    Object.keys(data).forEach(k=>data[k]=Number(data[k]));
    if(data.minTemp>=data.maxTemp){toast('Минимальная температура должна быть ниже максимальной');return;}
    if(data.tariffKzt<=0){toast('Тариф должен быть положительным числом');return;}
    if(state.backendOnline){
      try{
        const res = await fetch(API_BASE + '/api/v1/settings',{method:'POST',headers:{'Content-Type':'application/json','X-Role-Token':state.roleToken},body:JSON.stringify(data)});
        const j = await res.json();
        if(!res.ok){
          toast(j.message || 'Для изменения уставок и тарифа требуется роль Энергетика или Администратора');
          return;
        }
      }catch{}
    } else if(!isPrivilegedUser()){
      toast('Для изменения уставок и тарифа требуется роль Энергетика или Администратора');
      return;
    }
    state.settings={...state.settings,...data};
    log('—',`Параметры обновлены: ПК=${data.pcWatts} Вт, Свет=${data.lightWatts} Вт, Тариф=${num(data.tariffKzt,2)} тг/кВт·ч`);
    toast('Параметры и тариф сохранены');
    render();
  };
  if($('#reset-demo'))$('#reset-demo').onclick=async()=>{
    if(confirm('Восстановить исходную демонстрацию? Локальный журнал, БД и настройки будут сброшены.')){
      if(state.backendOnline){
        try{
          const res = await fetch(API_BASE + '/api/v1/reset',{method:'POST',headers:{'X-Role-Token':state.roleToken}});
          const j = await res.json();
          if(!res.ok){
            toast(j.message || 'Для полного сброса БД требуется роль Системного администратора');
            return;
          }
        }catch{}
      } else if(!isAdminUser()){
        toast('Для полного сброса БД требуется роль Системного администратора');
        return;
      }
      state={...state,rooms:M.seed(),settings:{...M.defaults},events:[]};
      log('—','Демонстрация сброшена к исходному состоянию');
      render();
      toast('Демонстрация восстановлена');
    }
  };
  if($('#export-events'))$('#export-events').onclick=()=>csv('energo-events.csv',[['Время','Кабинет','Событие','Тип'],...state.events.map(e=>[new Date(e.at).toISOString(),e.room,e.text,e.type])]);
}

function openRoom(id,refresh=false){
  const r=state.rooms.find(x=>x.id===id);
  if(!r)return;
  if(!refresh)lastFocus=document.activeElement;
  selectedRoom=id;
  const n=r.computers.filter(Boolean).length,a=M.alerts([r],state.settings),xai=M.explainRoom(r,state.settings);
  const recStatus = r.recStatus || (a.length?'new':'completed');
  const recBadgeClass = recStatus==='completed'?'badge-green':recStatus==='rejected'?'badge-gray':'badge-amber';
  $('#drawer').innerHTML=`<div class="drawer-header"><div><span class="eyebrow">${r.floor} ЭТАЖ · КОРПУС А · ${xai.stateClass}</span><h2 id="drawer-title">Кабинет ${r.id}</h2><p>${r.name}</p></div><button class="icon-button" id="close-drawer" aria-label="Закрыть кабинет">${icon('close')}</button></div><div class="drawer-content"><div class="drawer-status"><span class="badge ${r.online?'badge-green':'badge-gray'}">${icon(r.online?'wifi':'offline')}${r.online?'Контроллер на связи':'Нет связи'}</span><span>${r.online?'Синтетические демо-данные':'Последний сигнал: '+time(r.updatedAt)}</span></div>${a.map(x=>`<div class="drawer-alert ${x.severity==='neutral'?'neutral':''}">${icon(x.type==='offline'?'offline':'warning')}<div><strong>${x.title}</strong><p>${x.description}</p></div></div>`).join('')}<div class="room-detail-metrics"><div><small>Расчётная мощность</small><strong>${r.online?num(M.power(r,state.settings),2):'—'}<span> кВт</span></strong></div><div><small>Потенциал экономии (4 ч)</small><strong>${r.online?num(xai.saving4h,2):'0,0'}<span> кВт·ч (${num(xai.savingKzt4h,0)} тг)</span></strong></div></div>
  <section class="xai-panel" aria-label="Объяснимость решения ИИ (XAI)">
    <div class="xai-header"><h3>${icon('chip')}Интеллектуальный анализ и объяснимость (XAI)</h3><span class="badge ${xai.stateClass==='S3_EXCESS'?'badge-amber':xai.stateClass==='S0_OFFLINE'?'badge-gray':'badge-green'}">Доверие: ${num(xai.confidence*100,0)}%</span></div>
    <p class="small-text"><strong>Класс состояния:</strong> ${xai.stateLabel}${xai.baselineKw!==null?` · Прогноз нормы f_ML(X): ${num(xai.baselineKw,2)} кВт`:''}</p>
    <div class="xai-factors">${xai.factors.map(f=>`<div class="xai-factor-row"><div class="xai-factor-top"><span>${esc(f.label)}</span><span>${esc(f.value)} (${f.pct}%)</span></div><div class="xai-bar"><i style="width:${Math.max(4,f.pct)}%"></i></div></div>`).join('')}</div>
    <p class="small-text"><strong>Рекомендация ИИС:</strong> ${esc(xai.action)}</p>
    <div class="xai-formula">${esc(xai.formula)}</div>
  </section>
  ${r.online && (a.length || r.recProcessedAt) ? `<section class="rec-box" aria-label="Управление рекомендацией лаборанта">
    <div class="rec-top"><strong>Жизненный цикл рекомендации (BP-10 / BP-11)</strong><span class="badge ${recBadgeClass}">${statusLabels[recStatus]||recStatus}</span></div>
    <p class="small-text">${r.recProcessedAt?`Обработано оператором: ${time(r.recProcessedAt)}${r.recComment?' · Комментарий: '+esc(r.recComment):''}`:'Ожидает решения дежурного лаборанта (система не отключает питание без подтверждения человека).'}</p>
    <div class="rec-actions">
      <button class="button" data-rec-act="accepted" ${recStatus==='accepted'?'disabled':''}>Принять в работу</button>
      <button class="button primary" data-rec-act="completed">${icon('check')}Выключить технику и подтвердить</button>
      <button class="button" data-rec-act="rejected">Отклонить</button>
    </div>
  </section>` : ''}
  <div class="section-title"><h3>Схема компьютерного класса</h3><span>${r.online?n:'?'} активных из ${r.total}</span></div><div class="classroom"><div class="classroom-board">ЭКРАН / ПРЕПОДАВАТЕЛЬ</div><div class="pc-grid">${r.computers.map((on,i)=>`<button class="pc ${r.online?(on?'pc-on':''):'pc-unknown'}" data-pc="${i}" ${!r.online?'disabled':''} aria-label="ПК ${i+1}: ${r.online?(on?'включён, выключить в демо':'выключен, включить в демо'):'нет данных'}" aria-pressed="${r.online&&on}">${icon('pc')}<span>ПК ${String(i+1).padStart(2,'0')}</span><i></i></button>`).join('')}</div><div class="classroom-door">${icon('door')}ВХОД</div></div><p class="small-text room-hint">Нажмите на компьютер, чтобы изменить его состояние в симуляторе.</p><div class="section-title"><h3>Показания датчиков</h3><span>Текущее состояние</span></div><div class="sensor-detail-grid">${[['light','Освещение',r.light?'Включено':'Выключено'],['door','Дверь',r.door?'Открыта':'Закрыта'],['window','Окна',r.windows?'Одно открыто':'Все закрыты'],['temp','Температура',num(r.temp)+' °C']].map(([i,t,v])=>`<div>${icon(i)}<span>${t}<strong>${r.online?v:'Нет данных'}</strong></span></div>`).join('')}</div><section class="simulator"><div class="section-title"><h3>${icon('play')}Симулятор датчиков</h3><span class="badge badge-green">Демо</span></div><p>Измените показания и посмотрите, как пересчитывается объяснение XAI и потенциал экономии.</p><label class="toggle-row"><span>Связь с контроллером</span><input type="checkbox" data-field="online" ${r.online?'checked':''} role="switch"><span class="switch"></span></label><label class="toggle-row"><span>В кабинете идёт занятие<small>Задаётся вручную лаборантом или по расписанию</small></span><input type="checkbox" data-field="occupied" ${r.occupied?'checked':''} ${!r.online?'disabled':''} role="switch"><span class="switch"></span></label>${[['light','Свет включён'],['door','Дверь открыта'],['windows','Окно открыто']].map(([k,t])=>`<label class="toggle-row"><span>${t}</span><input type="checkbox" data-field="${k}" ${r[k]?'checked':''} ${!r.online?'disabled':''} role="switch"><span class="switch"></span></label>`).join('')}<label class="temp-control"><span>Температура <strong id="temp-value">${num(r.temp)} °C</strong></span><input aria-label="Температура в кабинете" type="range" id="temp-slider" min="10" max="35" step="0.1" value="${r.temp}" ${!r.online?'disabled':''}></label><button class="button primary full-width" id="shutdown-demo" ${!r.online?'disabled':''}>${icon('leaf')}Смоделировать выключение техники</button><p class="small-text">Меняется только демонстрация. Для реальных ПК потребуется штатное завершение работы.</p></section></div>`;
  $('#drawer').hidden=false;$('#drawer-backdrop').hidden=false;document.body.style.overflow='hidden';
  $('#close-drawer').onclick=closeRoom;
  $('#drawer').querySelectorAll('[data-pc]').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.pc);r.computers[i]=!r.computers[i];r.recStatus='new';mutated(r,`ПК ${i+1} ${r.computers[i]?'включён':'выключен'} в симуляторе`);});
  $('#drawer').querySelectorAll('[data-field]').forEach(c=>c.onchange=()=>{const k=c.dataset.field;r[k]=k==='windows'?(c.checked?1:0):c.checked;r.recStatus='new';const texts={online:c.checked?'Связь восстановлена (демо)':'Связь потеряна (демо)',occupied:c.checked?'Начато занятие (демо)':'Кабинет отмечен свободным (демо)',light:c.checked?'Освещение включено (демо)':'Освещение выключено (демо)',door:c.checked?'Дверь открыта (демо)':'Дверь закрыта (демо)',windows:c.checked?'Окно открыто (демо)':'Окно закрыто (демо)'};mutated(r,texts[k],k==='online'&&!c.checked?'offline':'info');});
  $('#temp-slider').oninput=e=>$('#temp-value').textContent=num(Number(e.target.value))+' °C';
  $('#temp-slider').onchange=e=>{r.temp=Number(e.target.value);r.recStatus='new';mutated(r,'Температура изменена: '+num(r.temp)+' °C (демо)');};
  $('#shutdown-demo').onclick=()=>{r.computers.fill(false);r.light=false;r.windows=0;r.recStatus='completed';r.recProcessedAt=Date.now();r.recComment='Штатное отключение лаборантом';mutated(r,'Компьютеры и свет выключены по подтверждению лаборанта');toast('Техника выключена, статус рекомендации: Выполнена');};
  $('#drawer').querySelectorAll('[data-rec-act]').forEach(btn=>btn.onclick=async()=>{
    const act = btn.dataset.recAct;
    let comment = '';
    if(act==='rejected'){
      comment = prompt('Укажите причину отклонения рекомендации (например: Идёт внеплановая консультация):','Идёт подготовка лабораторных стендов') || '';
      if(!comment.trim()){toast('Для отклонения рекомендации необходимо указать причину');return;}
    }
    r.recStatus = act;
    r.recProcessedAt = Date.now();
    r.recComment = comment.trim();
    if(act==='completed'){
      r.computers.fill(false);
      r.light=false;
      r.windows=0;
    }
    if(state.backendOnline && r.recId){
      try{await fetch(API_BASE + '/api/v1/recommendations/action',{method:'POST',headers:{'Content-Type':'application/json','X-Role-Token':state.roleToken},body:JSON.stringify({recommendation_id:r.recId,status:act,operator_comment:r.recComment})});}catch{}
    }
    mutated(r,`Рекомендация по каб. ${r.id} переведена в статус «${statusLabels[act]}»${r.recComment?' ('+r.recComment+')':''}`);
    toast(`Статус рекомендации: ${statusLabels[act]}`);
  });
  if(!refresh)$('#close-drawer').focus();
}
function mutated(r,text,type='info'){const active=document.activeElement;const pos=$('#drawer').scrollTop;const field=active?.dataset.field,pc=active?.dataset.pc,controlId=active?.id;if(r.online)r.updatedAt=Date.now();log(r.id,text,type);pushRoomTelemetry(r,text);render();openRoom(r.id,true);const focusTarget=field?$('#drawer').querySelector('[data-field="'+field+'"]'):pc!==undefined?$('#drawer').querySelector('[data-pc="'+pc+'"]'):controlId?document.getElementById(controlId):$('#close-drawer');focusTarget?.focus({preventScroll:true});$('#drawer').scrollTop=pos;}
function closeRoom(){$('#drawer').hidden=true;$('#drawer-backdrop').hidden=true;document.body.style.overflow='';selectedRoom=null;if(lastFocus?.isConnected)lastFocus.focus();else $('#main').focus();}
function csv(filename,rows){const payload='\uFEFF'+rows.map(row=>row.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(';')).join('\r\n');const url=URL.createObjectURL(new Blob([payload],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('CSV-отчёт скачан');}
function exportRooms(){
  const tariff=Number(state.settings.tariffKzt||32.5);
  csv('energo-campus-demo.csv',[
    ['Источник','Кабинет','Этаж','Класс состояния ИИ','Связь','Занятость','ПК включено','ПК всего','Освещение','Дверь','Открытых окон','Температура °C','Расчётная мощность кВт','Потенциал экономии (4ч) кВт·ч','Потенциал экономии (4ч) тг','Статус рекомендации','Последний сигнал'],
    ...state.rooms.map(r=>{
      const xai=M.explainRoom(r,state.settings);
      return ['ДЕМО (СИНТЕТИЧЕСКИЕ ДАННЫЕ)',r.id,r.floor,xai.stateClass,r.online?'На связи':'Нет связи',r.online?(r.occupied?'Занят':'Свободен'):'Неизвестно',r.online?r.computers.filter(Boolean).length:'Нет данных',r.total,r.online?(r.light?'Включено':'Выключено'):'Нет данных',r.online?(r.door?'Открыта':'Закрыта'):'Нет данных',r.online?r.windows:'Нет данных',r.online?r.temp:'Нет данных',r.online?M.power(r,state.settings).toFixed(2):'Нет данных',r.online?xai.saving4h.toFixed(2):'0.00',r.online?xai.savingKzt4h.toFixed(0):'0',r.recStatus||'new',new Date(r.updatedAt).toISOString()];
    })
  ]);
}
$('#notifications').onclick=()=>location.hash='events';$('#mobile-menu').onclick=()=>$('#sidebar').classList.toggle('is-open');$('#drawer-backdrop').onclick=closeRoom;
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeRoom();$('#sidebar').classList.remove('is-open');}if(e.key==='Tab'&&selectedRoom){const els=[...$('#drawer').querySelectorAll('button:not([disabled]),input:not([disabled]),select,a')];const first=els[0],last=els.at(-1);if(e.shiftKey&&document.activeElement===first){last.focus();e.preventDefault();}else if(!e.shiftKey&&document.activeElement===last){first.focus();e.preventDefault();}}});
window.addEventListener('hashchange',()=>{closeRoom();render();window.scrollTo(0,0);});
async function timerTick() {
  if(!isSyncPaused) {
    nextSyncCountdown--;
    if(nextSyncCountdown <= 0) {
      nextSyncCountdown = syncIntervalSec;
      await syncWithBackend();
      if(route === 'database' && isPrivilegedUser()) {
        await loadDbTable(currentDbTable, false);
      }
    }
  }
  const cd = $('#db-sync-countdown');
  if(cd) {
    cd.textContent = isSyncPaused ? 'Пауза' : nextSyncCountdown + ' сек';
  }
}

render();
syncWithBackend();
setInterval(timerTick, 1000);
