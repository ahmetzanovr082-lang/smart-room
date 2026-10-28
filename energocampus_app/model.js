/* Pure demo & hybrid AI model. Supports both Python REST API and offline browser mode. */
(function(root){
  const defaults = {pcWatts:150,lightWatts:120,minTemp:18,maxTemp:26,tariffKzt:32.5};
  function seed(){return [
    {id:'201',floor:2,name:'Компьютерный класс',total:12,pcs:7,light:true,door:false,windows:0,temp:22.4,occupied:true,online:true,recStatus:'completed',recProcessedAt:Date.now()-25*60000,recComment:'Штатное расписание'},
    {id:'202',floor:2,name:'Лаборатория информатики',total:12,pcs:0,light:false,door:false,windows:0,temp:21.6,occupied:false,online:true,recStatus:'completed',recProcessedAt:Date.now()-40*60000,recComment:''},
    {id:'204',floor:2,name:'Компьютерный класс',total:12,pcs:4,light:true,door:true,windows:0,temp:23.1,occupied:false,online:true,recStatus:'new',recProcessedAt:null,recComment:''},
    {id:'301',floor:3,name:'Лаборатория программирования',total:16,pcs:8,light:true,door:false,windows:0,temp:24.2,occupied:true,online:true,recStatus:'completed',recProcessedAt:Date.now()-30*60000,recComment:''},
    {id:'302',floor:3,name:'Мультимедийный класс',total:8,pcs:2,light:false,door:false,windows:1,temp:17.8,occupied:false,online:true,recStatus:'new',recProcessedAt:null,recComment:''},
    {id:'305',floor:3,name:'Компьютерный класс',total:12,pcs:0,light:false,door:false,windows:0,temp:21.2,occupied:false,online:false,recStatus:'new',recProcessedAt:null,recComment:''}
  ].map(r=>({...r,computers:Array.from({length:r.total},(_,i)=>i<r.pcs),updatedAt:Date.now()-(r.online?0:8*60000)}));}
  function power(r,s=defaults){return r.online?(r.computers.filter(Boolean).length*s.pcWatts+(r.light?s.lightWatts:0))/1000:null;}
  function explainRoom(r,s=defaults){
    const tariff = Number(s.tariffKzt||defaults.tariffKzt);
    if(!r.online){
      return {
        stateClass:'S0_OFFLINE',
        stateLabel:'S0_OFFLINE · Нет связи',
        confidence:0,
        baselineKw:null,
        saving1h:0,
        saving4h:0,
        savingKzt4h:0,
        factors:[{label:'Связь с контроллером x7',value:'false (обрыв)',kw:0,pct:100}],
        action:'Проверить питание контроллера ESP32 и сетевое подключение кабинета '+r.id,
        formula:'x7 = 0 → S = S0_OFFLINE, E = 0,00 кВт·ч/ч (блокировка ложной экономии по NFR-2)'
      };
    }
    const n = r.computers.filter(Boolean).length;
    const pcKw = (n*s.pcWatts)/1000;
    const lightKw = (r.light?s.lightWatts:0)/1000;
    const kw = pcKw + lightKw;
    const baselineKw = r.occupied ? Number(((r.total*0.65*s.pcWatts + s.lightWatts)/1000).toFixed(2)) : 0;
    const mlExcess = r.occupied ? Math.max(0, kw - baselineKw) : 0;
    const saving1h = !r.occupied ? kw : mlExcess;
    const saving4h = saving1h * 4;
    const savingKzt4h = saving4h * tariff;
    const factors = [];
    if(!r.occupied && kw > 0){
      if(n > 0) factors.push({label:`Включённые ПК x1 (${n} шт.)`,value:`${pcKw.toFixed(2)} кВт`,kw:pcKw,pct:Math.round((pcKw/kw)*100)});
      if(r.light) factors.push({label:'Освещение x2',value:`${lightKw.toFixed(2)} кВт`,kw:lightKw,pct:Math.round((lightKw/kw)*100)});
    }
    if(r.temp < s.minTemp || r.temp > s.maxTemp){
      factors.push({label:'Температура воздуха x5',value:`${r.temp.toFixed(1)} °C`,kw:0,pct:r.windows?70:100});
      if(r.windows) factors.push({label:'Открытое окно x6',value:`${r.windows} шт.`,kw:0,pct:30});
    } else if(r.windows && !r.occupied){
      factors.push({label:'Окно в свободном классе x6',value:`${r.windows} шт.`,kw:0,pct:100});
    }
    const hasAnom = factors.length > 0;
    const stateClass = hasAnom ? 'S3_EXCESS' : (r.occupied ? 'S1_OCCUPIED' : 'S2_IDLE');
    const stateLabel = hasAnom ? 'S3_EXCESS · Нецелевой расход / отклонение' : (r.occupied ? 'S1_OCCUPIED · Штатное занятие' : 'S2_IDLE · Штатное ожидание');
    if(!factors.length){
      factors.push({label:r.occupied?'Учебная нагрузка по расписанию':'Дежурный режим ожидания',value:`${kw.toFixed(2)} кВт`,kw:kw,pct:100});
    }
    const action = !r.occupied && kw > 0
      ? `Выключить ${n} ПК${r.light?' и освещение':''} в свободном каб. ${r.id} (после подтверждения лаборантом)`
      : (r.temp < s.minTemp || r.temp > s.maxTemp)
      ? `Закрыть окно и проверить микроклимат в каб. ${r.id}`
      : 'Действий оператора не требуется';
    const formula = `E = (1 - ${r.occupied?1:0})·(${n}·${s.pcWatts} + ${r.light?1:0}·${s.lightWatts})/1000 = ${saving1h.toFixed(2)} кВт·ч/ч; ΔW(4ч) = ${saving4h.toFixed(2)} кВт·ч; ΔC(4ч) = ${savingKzt4h.toFixed(0)} тг`;
    return {stateClass,stateLabel,confidence:0.92,baselineKw,saving1h,saving4h,savingKzt4h,factors,action,formula};
  }
  function alerts(rooms,s=defaults){return rooms.flatMap(r=>{
    if(!r.online)return [{key:r.id+'-offline',room:r.id,type:'offline',title:'Нет связи с контроллером',description:'Состояние устройств неизвестно. Проверьте питание и сеть.',severity:'neutral'}];
    const a=[];
    if(!r.occupied && power(r,s)>0)a.push({key:r.id+'-energy',room:r.id,type:'energy',title:'Техника в свободном кабинете',description:[r.computers.filter(Boolean).length+' ПК',r.light?'свет включён':'свет выключен'].join(' · '),severity:'warning'});
    if(r.temp<s.minTemp || r.temp>s.maxTemp)a.push({key:r.id+'-temperature',room:r.id,type:'temperature',title:r.temp<s.minTemp?'Температура ниже нормы':'Температура выше нормы',description:r.temp.toFixed(1)+' °C'+(r.windows?' · окно открыто':''),severity:'warning'});
    if(r.windows && !r.occupied && !a.some(x=>x.type==='temperature'))a.push({key:r.id+'-window',room:r.id,type:'window',title:'Открыто окно',description:'Кабинет отмечен как свободный. Проверьте окно.',severity:'warning'});
    return a;
  });}
  function summary(rooms,s=defaults){
    const online=rooms.filter(r=>r.online);
    const tariff=Number(s.tariffKzt||defaults.tariffKzt);
    const idle=online.filter(r=>!r.occupied).reduce((n,r)=>n+power(r,s),0);
    return {
      kw:online.reduce((n,r)=>n+power(r,s),0),
      idle:idle,
      idleKzt1h:idle*tariff,
      idleKzt4h:idle*4*tariff,
      pcs:online.reduce((n,r)=>n+r.computers.filter(Boolean).length,0),
      total:rooms.reduce((n,r)=>n+r.total,0),
      online:online.length,
      unknown:rooms.filter(r=>!r.online).reduce((n,r)=>n+r.total,0),
      alerts:alerts(rooms,s)
    };
  }
  const api={defaults,seed,power,explainRoom,alerts,summary};root.EnergyModel=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
