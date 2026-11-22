/* مركز أبو زبيدة للتتبع والرصد — منطق الواجهة */
const $=s=>document.querySelector(s);
const CAT={};let META=null;let CENTERS=[];let CENTER_SET=new Set();
const ITEMS=new Map();
const S={cat:'dash',hours:0,source:'',tag:'',q:'',page:1,per:30,total:0,ids:new Set(),compact:false,openId:null,center:''};
const CF={q:'',region:'',cat:''};
const TITLE_DEFAULT='مركز أبو زبيدة للتتبع والرصد';
const DESC={
 net:'حالة الاتصال بالإنترنت في دول المنطقة لحظياً. انقطاع الإنترنت كثيراً ما يسبق عملية عسكرية أو يرافقها. المصدر: مرصد IODA في معهد جورجيا للتقنية.',
 settings:'التحديث التلقائي، والفتح من الجوال، ووضع الشاشة الكبيرة.',
 ask:'اسأل سؤالاً عادياً، فيجيبك المركز من الأخبار والدراسات التي رصدها، مع أرقام مصادر كل معلومة.',
 research:'نتائج البحث في دراسات ومقالات كل مراكز البحث ومكافحة الإرهاب والأمن فقط، دون الأخبار.',
 sanctions:'كل المصنَّفين إرهابياً على قائمة العقوبات الأمريكية (OFAC) وقائمة مجلس الأمن الدولي، مرتبين حسب الجماعة: داعش والقاعدة والنصرة وحزب الله والحرس الثوري وطالبان والشباب وغيرها، مع أحدث الإدراجات وبحث في القوائم كاملة.',
 cases:'اجمع الأخبار والدراسات المتعلقة بقضية تتابعها في ملف واحد، مع ملاحظاتك، وصدّرها تقريراً. كل مادة تُضاف تُؤرشف تلقائياً.',
 archive:'نسخ محفوظة من نصوص المقالات لحظة رصدها، تبقى حتى لو حُذفت من موقعها أو عُدّلت. وسجل بكل عنوان غيّرته صحيفته بعد النشر.',
 official:'بيانات وزارات الدفاع والخارجية والعدل والقيادات العسكرية والأمم المتحدة والناتو، وهي المصدر الأول قبل أن تعيد الصحف صياغتها.',
 map:'كل خبر نوعي على الخريطة في موقعه: المدينة إن ذُكرت، أو الدولة. اضغط أي نقطة لتقرأ الخبر.',
 alerts:'ينبّهك المركز حين يقفز الحديث عن دولة أو موضوع فجأة فوق معدله المعتاد، أو حين تتوالى الأحداث النوعية في مكان واحد.',
 bot:'يرسل البوت إلى قناتك أو مجموعتك في تيليغرام ملخص مقالة أو دراسة أو خبر عالمي مترجم مع رابطه، كل دقيقة.',
 writer:'اكتب مقالاً أو دراسة أو تقدير موقف عن أي موضوع، يُكتب كاملاً تلقائياً مستنداً إلى ما رصده المركز. يعمل مجاناً فوراً دون مفتاح، أو عبر Gemini أو Ollama أو Claude.',
 qual:'الأحداث الميدانية المهمة تُلتقط تلقائياً من كل الأخبار وقنوات تيليغرام: غارات، مسيّرات، انفجارات، اشتباكات، اعتقالات، توغلات، اغتيالات.',
 dash:'نظرة واحدة على كل الأقسام: آخر ما رصده المركز في كل قسم، ومؤشر التوتر الأمني، وآخر منشورات تيليغرام.',
 all:'كل ما رصده المركز من جميع الأقسام، الأحدث أولاً.',
 world:'وكالات الأنباء والصحف الدولية الكبرى.',
 arab:'الصحف والقنوات والمواقع الإخبارية العربية.',
 think_global:'دراسات وتحليلات وتقديرات موقف من مراكز بحث غربية ودولية، خلال الشهر الأخير.',
 think_arab:'أوراق ودراسات من مراكز الأبحاث العربية، خلال الشهر الأخير.',
 terror:'مراكز رصد الإرهاب والتطرف وتحليلات الجماعات المسلحة، خلال الشهر الأخير.',
 war:'تقارير ميدانية وتحليلات عسكرية ودفاعية وبيانات النزاعات.',
 economy:'الأسواق والنفط والعملات والسياسات المالية من مصادر عالمية وعربية.',
 tweets:'آخر 3 منشورات من كل قناة تيليغرام وحساب Bluesky، تتحدّث تلقائياً كل دقيقتين.',
 keywords:'أضف كلمات تهمك، ويبحث عنها المركز في أخبار Google بالعربية والإنجليزية في كل دورة.',
 centers:'تصفّح مراكز الأبحاث ومكافحة الإرهاب والدراسات العسكرية واحداً واحداً، مع أبرز مواضيع كل مركز.',
 saved:'العناصر التي حفظتها على هذا الجهاز.',
 intel:'دراسات ومقالات وأخبار الأمن والاستخبارات والتجسس والأمن السيبراني، خلال الشهر الأخير.',
 countries:'كل مادة مربوطة تلقائياً بالدول التي تتحدث عنها. اختر دولة لتتصفح كل ما يخصها خلال الشهر الأخير.',
 books:'كتب صدرت خلال آخر سنتين عن الإرهاب والحروب والسياسة والأمن والاستخبارات، مع غلافها وملخصها المترجم ورابطها.',
 health:'حالة كل مصدر في آخر دورة جلب. المصادر التي لا يعمل رابطها تُجلب عبر بحث أخبار Google لنفس الموقع.'
};
const CODES={research:'SEARCH / CENTERS',net:'SIGINT / INTERNET',settings:'SYSTEM / SETTINGS',ask:'QUERY / ASK',sanctions:'DESIGNATIONS / SANCTIONS',cases:'CASE FILES',archive:'EVIDENCE / ARCHIVE',official:'SEC-11 / OFFICIAL',map:'GEO / LIVE-MAP',alerts:'EARLY WARNING / ALERTS',bot:'RELAY / TELEGRAM-BOT',writer:'STUDIO / WRITER',qual:'CRITICAL / EVENTS',dash:'COMMAND / OVERVIEW',all:'ALL-SOURCES',world:'SEC-01 / GLOBAL',arab:'SEC-02 / ARAB',think_global:'SEC-03 / THINK-TANKS',think_arab:'SEC-04 / ARAB-RESEARCH',terror:'SEC-05 / COUNTER-TERRORISM',war:'SEC-06 / CONFLICT',economy:'SEC-07 / ECONOMY',tweets:'SEC-08 / TELEGRAM',keywords:'SEC-09 / WATCHLIST',intel:'SEC-10 / SECURITY-INTEL',countries:'GEO / COUNTRIES',books:'LIBRARY / BOOKS',centers:'DIRECTORY / CENTERS',saved:'ARCHIVE / SAVED',health:'SYSTEM / SOURCES'};
const EXTRA={research:'البحث في مواد المراكز',net:'رصد انقطاع الإنترنت',settings:'الإعدادات',ask:'اسأل المركز',sanctions:'العقوبات والتصنيفات',cases:'ملفات القضايا',archive:'الأرشيف والعناوين المعدّلة',map:'الخريطة التفاعلية',alerts:'الإنذار المبكر',bot:'بوت تيليغرام',writer:'كاتب المقالات والدراسات',qual:'أخبار نوعية',dash:'لوحة القيادة',all:'كل الأخبار',countries:'الدول',books:'مكتبة الكتب',centers:'دليل المراكز',saved:'المحفوظات',health:'صحة المصادر والترجمة'};
const P={
 radar:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l6.4-6.4"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
 news:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h6M7 13h10M7 16h7"/>',
 columns:'<path d="M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18"/>',
 building:'<path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6"/>',
 shield:'<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
 target:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
 chart:'<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
 send:'<path d="M21 4L3 11l6 2 2 6 3-4 5 4z"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
 centers:'<rect x="4" y="3" width="10" height="18" rx="1.5"/><path d="M14 9h5a1 1 0 0 1 1 1v11h-6M8 7h2M8 11h2M8 15h2"/>',
 lock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4M12 15v2"/>',
 flag:'<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
 bolt:'<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
 wifi:'<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
 screen:'<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
 cmd:'<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',
 bell:'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 0 0 4 0"/>',
 pen:'<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
 book:'<path d="M4 19V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zm0 0a2 2 0 0 0 2 2h13"/><path d="M9 7h6"/>',
 bookmark:'<path d="M6 3h12v18l-6-4-6 4z"/>',
 pulse:'<path d="M3 12h4l3-7 4 14 3-7h4"/>',
 open:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 link:'<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
 copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
 arrow:'<path d="M9 6l6 6-6 6"/>',
 lang:'<path d="M4 5h8M8 3v2M6 5c0 4 3 7 6 8M10 5c0 3-2 6-6 8M13 21l4-9 4 9M14.5 18h5"/>',
 word:'<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M8.5 12l1.2 5 1.8-4 1.8 4 1.2-5"/>',
 pdf:'<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M9 13h6M9 16h4"/>',
 swap:'<path d="M7 7h12l-3-3M17 17H5l3 3"/>'
};
const CICON={research:'centers',net:'wifi',settings:'gear',ask:'search',sanctions:'shield',cases:'centers',archive:'bookmark',official:'columns',map:'globe',alerts:'bell',bot:'send',writer:'pen',qual:'bolt',dash:'radar',all:'grid',world:'globe',arab:'news',think_global:'columns',think_arab:'building',terror:'shield',war:'target',economy:'chart',tweets:'send',keywords:'search',intel:'lock',countries:'flag',country:'flag',books:'book',centers:'centers',saved:'bookmark',health:'pulse'};
const ico=(n)=>`<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${P[n]||''}</svg>`;

function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function ago(ts){const d=Math.max(0,Date.now()/1000-ts);if(d<60)return'الآن';if(d<3600)return'قبل '+Math.floor(d/60)+' دقيقة';if(d<86400)return'قبل '+Math.floor(d/3600)+' ساعة';return'قبل '+Math.floor(d/86400)+' يوم'}
function hm(ts){return new Date(ts*1000).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})}
function dm(ts){const d=new Date(ts*1000);return d.toLocaleDateString('ar',{day:'numeric',month:'short'})}
function fmt(ts){return ts?new Date(ts*1000).toLocaleString('ar',{dateStyle:'medium',timeStyle:'short'}):'—'}
async function api(u,o){const r=await fetch(u,o);const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.status);return j}
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('show');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('show'),2300)}
function lsGet(k,d){try{return localStorage.getItem(k)??d}catch(e){return d}}
function lsSet(k,v){try{localStorage.setItem(k,v)}catch(e){}}
function savedList(){try{return JSON.parse(lsGet('rased_saved','[]'))}catch(e){return[]}}
function setSaved(l){lsSet('rased_saved',JSON.stringify(l))}
function isSaved(id){return savedList().some(i=>i.id===id)}
const STOP=new Set(['مركز','المركز','معهد','المعهد','مؤسسة','المجلس','مجلس','برنامج','الشبكة','مشروع','مرصد','الجمعية','نادي','وكالة','كلية','دراسات','للدراسات','لدراسة','لدراسات','و','-','–']);
function mono(name){const m=name.match(/\b[A-Z][A-Za-z-]{1,6}\b/);if(m&&m[0].length<=6)return m[0].toUpperCase();
 const w=name.replace(/\(.*?\)/g,'').split(/\s+/).filter(x=>x&&!STOP.has(x));return w.slice(0,2).map(x=>x.replace(/^ال/,'')[0]||'').join(' ')||name[0]}
const T=it=>it.title_ar||it.title;
let VIS=new Set();try{VIS=new Set(JSON.parse(lsGet('rased_visited','[]')))}catch(e){}
const seen=id=>VIS.has(id);
function markVisited(id){
 if(!id||VIS.has(id))return;VIS.add(id);
 const arr=[...VIS];lsSet('rased_visited',JSON.stringify(arr.slice(-6000)));
 document.querySelectorAll(`#feed [data-id="${id}"]`).forEach(el=>{const it=ITEMS.get(id);if(it)el.outerHTML=card(it,el.classList.contains('lead'))});
 document.querySelectorAll(`.bt[data-open="${id}"],.tgp[data-open="${id}"],.twl button[data-open="${id}"]`).forEach(b=>b.classList.add('seen'))}

/* الساعات */
const ZONES=[['UTC','UTC'],['إسطنبول','Europe/Istanbul'],['القاهرة','Africa/Cairo'],['واشنطن','America/New_York'],['موسكو','Europe/Moscow'],['بكين','Asia/Shanghai']];
function clocks(){const n=new Date();$('#utcnow').textContent=n.toISOString().slice(0,19).replace('T',' ')+' UTC';
 if(n.getSeconds()%20===0||!$('#clocks').innerHTML)$('#clocks').innerHTML=ZONES.map(([nm,z])=>`<span class="clock"><b>${new Intl.DateTimeFormat('en-GB',{timeZone:z,hour:'2-digit',minute:'2-digit'}).format(n)}</b>${nm}</span>`).join('')}

/* عناصر الأخبار */
function tagsHtml(tags,max=99){return (tags||'').split('|').filter(Boolean).slice(0,max).map(t=>t.startsWith('★')?`<button class="tag kw" data-tag="${esc(t)}">${esc(t.slice(1))}</button>`:`<button class="tag" data-tag="${esc(t)}">${esc(t)}</button>`).join('')}
const VCATS=['world','arab','war','terror','intel','tweets','keywords','economy'];
function dupHtml(it){return it.dup>1?`<button class="vf dupb" data-cluster="${esc(it.cluster)}" title="أخبار أخرى عن الحدث نفسه دُمجت هنا">+${it.dup-1} ${it.dup-1>2?'أخبار مشابهة':(it.dup-1===2?'خبران مشابهان':'خبر مشابه')}</button>`:''}
function vfHtml(it){if(!it.cluster||!VCATS.includes(it.cat))return dupHtml(it);const n=it.nsrc||1;
 const d=dupHtml(it);if(d)return (n>=3?`<span class="vf v3" title="نقلته ${n} مصادر مستقلة">✓ مؤكد</span>`:'')+d;
 if(n>=3)return `<button class="vf v3" data-cluster="${esc(it.cluster)}" title="نقلته ${n} مصادر مستقلة">✓ مؤكد، ${n} مصادر</button>`;
 if(n===2)return `<button class="vf v2" data-cluster="${esc(it.cluster)}" title="نقله مصدران">مصدران</button>`;
 return (it.events?`<span class="vf v1" title="لم ينقله حتى الآن إلا مصدر واحد">مصدر واحد، غير مؤكد</span>`:'')}
function evHtml(e){return (e||'').split('|').filter(Boolean).map(n=>`<span class="ev" style="--e:${EVC[n]||'var(--red)'}">${esc(n)}</span>`).join('')}
function ctyHtml(c,max=6){return (c||'').split('|').filter(Boolean).slice(0,max).map(n=>`<button class="tag cty" data-country="${esc(n)}" title="كل ما يخص ${esc(n)}">${esc(n)}</button>`).join('')}
function state(it){if(it.translated===1)return'';if(it.translated<=-3)return'<span class="badge fail">تعذّرت الترجمة</span>';return'<span class="badge pend">قيد الترجمة</span>'}
function mlHtml(it){const m=META?.media||{};const l=m[(it.source_ar||'').toLowerCase()]||m[(it.source||'').replace('t.me/','').toLowerCase()];
 return l?`<span class="ml${l.startsWith('حكومي')?' gov':''}" title="ملكية أو تمويل وسيلة الإعلام">${esc(l)}</span>`:''}
function edHtml(it){return it.edits?`<button class="ed" data-edits="${it.id}" title="غيّرت الصحيفة عنوان هذا الخبر بعد نشره">✎ عُدِّل العنوان${it.edits>1?' '+it.edits+' مرات':''}</button>`:''}
function iconKey(src,link){src=(src||'').toLowerCase();
 if(src.startsWith('t.me/'))return 'tg/'+src.slice(5);
 if(src.startsWith('bsky/'))return 'bs/'+src.slice(5);
 if(/^[a-z0-9.-]+\.[a-z]{2,}/.test(src)&&!src.startsWith('news.google'))return src.split('/')[0];
 try{const h=new URL(link).hostname.replace(/^www\./,'');if(h&&!h.includes('news.google'))return h}catch(e){}return ''}
function favImg(key){return key?`<img class="fav" src="/icon/${esc(key)}" alt="" loading="lazy" onerror="this.remove()">`:''}
function srcHtml(it){const fv=favImg(iconKey(it.source,it.link));return mlHtml(it)+(CENTER_SET.has(it.source_ar)?`<button class="src" data-center="${esc(it.source_ar)}" title="تصفّح هذا المركز">${fv}${esc(it.source_ar)}</button>`:`<span class="src">${fv}${esc(it.source_ar)}</span>`)}
function card(it,lead){
 const c=CAT[it.cat]||{color:'var(--acc)',name:''};
 const fresh=Date.now()/1000-it.published<3600;
 const showOrig=it.translated===1&&it.lang!=='ar'&&it.title&&it.title!==T(it);
 const sv=isSaved(it.id);
 const recent=Date.now()/1000-it.published<86400;
 return `<article class="item${lead?' lead':''}${seen(it.id)?' seen':''}" data-id="${it.id}" style="--c:${c.color}">
  <div class="when"><b>${recent?hm(it.published):dm(it.published)}</b>${recent?'اليوم':''}</div>
  <div>
   <div class="meta">${evHtml(it.events)}${vfHtml(it)}${edHtml(it)}${it.kind==='video'?'<span class="badge vid">▶ فيديو</span>':''}${srcHtml(it)}${['all','center','saved','qual','country'].includes(S.cat)?`<span>${esc(c.name)}</span>`:''}<time title="${esc(fmt(it.published))}">${ago(it.published)}</time>${fresh&&!seen(it.id)?'<span class="badge new">جديد</span>':''}${seen(it.id)?'<span class="badge seen">✓ تمت زيارتها</span>':''}${state(it)}<span class="ref">REF-${it.id.slice(0,6).toUpperCase()}</span></div>
   <h3><button class="ttl" data-open="${it.id}">${esc(T(it))}</button></h3>
   ${showOrig&&lead?`<span class="orig">${esc(it.title)}</span>`:''}
   ${it.summary_ar?`<p>${esc(it.summary_ar)}</p>`:''}
   <div class="foot">${ctyHtml(it.countries,3)}${tagsHtml(it.tags,4)}<span class="acts">
    <button data-open="${it.id}" title="قراءة مترجمة" aria-label="قراءة مترجمة">${ico('open')}</button>
    ${it.link?`<a href="/go/${it.id}" target="_blank" rel="noopener" title="فتح في الموقع الأصلي" aria-label="فتح في الموقع الأصلي">${ico('link')}</a>`:''}
    <button data-save="${it.id}" class="${sv?'saved':''}" title="${sv?'محفوظ':'حفظ'}" aria-label="حفظ">${ico('bookmark')}</button>
    <button data-copy="${it.id}" title="نسخ" aria-label="نسخ">${ico('copy')}</button></span></div>
  </div>
 </article>`}
function emptyHtml(){
 if(META&&META.categories.every(c=>!c.total))return'<div class="empty"><b>يجري الجلب الأول من المصادر</b>ستظهر العناصر هنا خلال دقائق، وتُترجم تباعاً.</div>';
 if(S.cat==='keywords'&&!META?.keywords.length)return'<div class="empty"><b>لا توجد كلمات مراقَبة بعد</b>أضف كلمة في الحقل أعلاه ليبدأ المركز برصدها.</div>';
 if(S.cat==='center')return'<div class="empty"><b>لا توجد مواد لهذا المركز حالياً</b>قد لا يكون نشر شيئاً خلال الشهر الأخير، أو أن مصدره متعطل. راجع «صحة المصادر».</div>';
 return'<div class="empty"><b>لا توجد نتائج لهذه المرشحات</b>وسّع المدة الزمنية، أو اختر كل المصادر، أو امسح البحث.</div>'}

/* البيانات الوصفية */
async function loadMeta(){
 META=await api('/api/meta');
 META.categories.forEach(c=>CAT[c.key]=c);
 renderNav();renderTags();renderStatus();renderPanels();renderSources();
 $('#live').innerHTML=`<i></i>مباشر <b>${META.hour}</b> خبراً في آخر ساعة`;
 updBanner();
 $('#sbSources').textContent=`SOURCES ${META.health.ok}/${META.health.ok+META.health.fail}`;
 $('#sbTr').textContent=`TRANSLATION QUEUE ${META.pending}`;
 if(S.cat==='dash')renderKpis();
}
async function loadCenters(){const d=await api('/api/centers');CENTERS=d.items;CENTER_SET=new Set(CENTERS.map(c=>c.name))}
function navi(key,name,color,count,ratio){return `<button class="navi${S.cat===key||(key==='centers'&&S.cat==='center')?' on':''}" data-cat="${key}" style="--c:${color}">${ico(CICON[key])}<span class="nm">${esc(name)}</span>${count!==''&&count!=null?`<span class="ct" title="خلال آخر 24 ساعة">${esc(count)}</span>`:''}${ratio!=null?`<span class="bar"><i style="width:${Math.max(3,Math.round(ratio*100))}%"></i></span>`:''}</button>`}
function renderNav(){
 const sum=META.categories.reduce((a,c)=>a+c.day,0);
 const max=Math.max(1,...META.categories.map(c=>c.day));
 let h='<div class="navgrp">COMMAND</div>'+navi('dash','لوحة القيادة','var(--acc)','')+navi('qual','أخبار نوعية','var(--red)',QSTATS?QSTATS.total:'')+navi('alerts','الإنذار المبكر','#F59E0B',ALN||'')+navi('map','الخريطة التفاعلية','var(--acc)','')+navi('net','انقطاع الإنترنت','#A78BFA',NETBAD||'')+navi('ask','اسأل المركز','var(--acc)','')+navi('all','كل الأخبار','var(--acc)',sum);
 h+='<div class="navgrp">SECTIONS / الأقسام</div>';
 META.categories.forEach(c=>h+=navi(c.key,c.name,c.color,c.day,c.key==='tweets'||c.key==='keywords'?null:c.day/max));
 h+='<div class="navgrp">TOOLS / الأدوات</div>'+navi('centers','دليل المراكز','var(--acc)',CENTERS.length||'')+navi('countries','الدول','var(--acc)',CTY.length||'')+navi('books','مكتبة الكتب','var(--gold)',BOOKS_N||'')+navi('writer','كاتب المقالات','var(--acc)','')+navi('bot','بوت تيليغرام','#38BDF8',BOTON?'يعمل':'')+navi('sanctions','العقوبات والتصنيفات','#E11D48',META.sanc_new||'')+navi('cases','ملفات القضايا','var(--gold)','')+navi('archive','الأرشيف','var(--acc)','')+navi('saved','المحفوظات','var(--gold)',savedList().length||'')+navi('settings','الإعدادات','var(--muted)','')+navi('health','صحة المصادر والترجمة',META.health.fail||META.tr_stats.down?'var(--red)':'var(--green)',META.health.fail?META.health.fail+' متعطل':'');
 $('#nav').innerHTML=h;
 $('#sidefoot').innerHTML=`SOURCES <b>${META.health.ok}/${META.health.ok+META.health.fail}</b><br>TRANSLATION QUEUE <b>${META.pending}</b><br>LAST CYCLE <b>${META.state.last_cycle?ago(META.state.last_cycle):'…'}</b>`}
function renderTags(){const h=META.tags.length?META.tags.map(t=>`<button class="tag${S.tag===t.tag?' on':''}" data-tag="${esc(t.tag)}">${esc(t.tag)} <em>${t.count}</em></button>`).join(''):'<span class="count">تظهر بعد ترجمة العناصر.</span>';$('#tags').innerHTML=h;$('#dashTags').innerHTML=h}
function renderSources(){
 const uniq=[...new Set(META.sources.filter(s=>S.cat==='all'||s.cat===S.cat).map(s=>s.name))];
 $('#source').innerHTML='<option value="">كل المصادر</option>'+uniq.map(n=>`<option${n===S.source?' selected':''}>${esc(n)}</option>`).join('')}
function renderStatus(){
 const st=META.state;
 $('#status').innerHTML=
  `آخر دورة: <b>${st.last_cycle?ago(st.last_cycle):'جارية الآن'}</b><br>`+
  `الدورة القادمة: <b>${st.running?'جارية الآن':(st.next_cycle?ago(2*META.now-st.next_cycle).replace('قبل','بعد'):'—')}</b><br>`+
  `بانتظار الترجمة: <b>${META.pending}</b><br>`+
  `مصادر تعمل: <b class="ok">${META.health.ok}</b>، متعطلة: <b class="${META.health.fail?'bad':''}">${META.health.fail}</b><br>`+
  (META.tr_stats.down?`<span class="warn">الترجمة متوقفة مؤقتاً: ${esc(META.tr_stats.last_error)}</span>`:'');
 $('#refresh').classList.toggle('spin',!!st.running)}
function threatColor(l){return['#34D399','#A3E635','#FACC15','#FB923C','#F43F5E'][l-1]}
function renderKpis(){
 const t=META.threat;
 const k=$('#kThreat');k.style.setProperty('--tl',threatColor(t.level));
 k.innerHTML=`<div class="k">THREAT INDEX / مؤشر التوتر الأمني</div><div class="v"><b>${esc(t.label)}</b><span class="mt">LEVEL ${t.level}/5</span></div><div class="segs">${[1,2,3,4,5].map(i=>`<i class="${i<=t.level?'on':''}"></i>`).join('')}</div><p>${t.w6} خبراً عن الحروب والإرهاب في آخر 6 ساعات، مقابل متوسط ${t.avg} في الأسبوع.</p>`;
 $('#kHour').innerHTML=`<div class="k">LAST HOUR / آخر ساعة</div><div class="v"><b>${META.hour}</b><span>خبراً جديداً</span></div><p>${META.categories.reduce((a,c)=>a+c.day,0)} خبراً خلال 24 ساعة</p>`;
 $('#kSrc').innerHTML=`<div class="k">SOURCES / المصادر</div><div class="v"><b class="ok">${META.health.ok}</b><span>تعمل</span></div><p>${META.health.fail?`<button class="lnk" data-cat="health" style="all:unset;cursor:pointer;color:var(--red)">${META.health.fail} مصدراً متعطلاً، اعرضها</button>`:'كل المصادر تعمل'}</p>`;
 $('#kTr').innerHTML=`<div class="k">TRANSLATION / الترجمة</div><div class="v"><b>${META.pending}</b><span>بانتظار الترجمة</span></div><p>${META.tr_stats.down?'<button data-cat="health" style="all:unset;cursor:pointer;color:var(--red)">كل مزودي الترجمة متوقفون مؤقتاً، اعرض التفاصيل</button>':(META.tr_stats.providers||[]).filter(p=>p.ready).length+' مزودي ترجمة يعملون'}</p>`}
function renderPanels(){
 $('#kwpanel').hidden=S.cat!=='keywords';
 if(!META)return;
 $('#kwchips').innerHTML=META.keywords.map(w=>`<span class="chip" style="--cc:var(--gold)"><button data-tag="★${esc(w)}">${esc(w)}</button><button class="x" data-kwdel="${esc(w)}" aria-label="حذف ${esc(w)}">×</button></span>`).join('')}

/* التنقل */
function setView(cat){
 if(!QSETTING){QALL=false;if(S.q||$('#q').value){S.q='';$('#q').value='';Object.values(QLOCAL).forEach(sel=>{const el=$(sel);if(el&&el.value){el.value='';el.dispatchEvent(new Event('input'))}})}}
 S.cat=cat;S.source='';S.tag='';S.page=1;if(cat!=='center')S.center='';if(cat!=='country')S.country='';
 $('#title').textContent=EXTRA[cat]||CAT[cat]?.name||'';
 $('#desc').textContent=DESC[cat]||'';$('#pcode').textContent=CODES[cat]||'';
 const feedViews=!['dash','tweets','centers','countries','books','writer','bot','map','alerts','ask','sanctions','cases','archive','net','settings'].includes(cat);
 $('#mapview').hidden=cat!=='map';$('#alertsview').hidden=cat!=='alerts';
 $('#netview').hidden=cat!=='net';$('#setview').hidden=cat!=='settings';
 $('#askview').hidden=cat!=='ask';$('#sancview').hidden=cat!=='sanctions';$('#casesview').hidden=cat!=='cases';$('#archview').hidden=cat!=='archive';
 $('#writerview').hidden=cat!=='writer';
 $('#botview').hidden=cat!=='bot';
 $('#pagehead').hidden=cat==='center'||cat==='country';
 $('#centerhead').hidden=cat!=='center';
 $('#countryhead').hidden=cat!=='country';
 $('#countriesdir').hidden=cat!=='countries';
 $('#booksview').hidden=cat!=='books';
 $('#dash').hidden=cat!=='dash';
 $('#tgview').hidden=cat!=='tweets';
 $('#centersdir').hidden=cat!=='centers';
 $('#secview').hidden=!feedViews;
 $('#filters').hidden=cat==='health';
 $('#source').hidden=cat==='center'||cat==='country';
 $('#qualfilter').hidden=cat!=='qual';if(cat!=='qual')S.event='';
 $('#newpill').hidden=true;document.title=TITLE_DEFAULT;
 if(META){renderNav();renderSources();renderPanels();renderTags()}
 renderActiveTag();updScope();window.scrollTo({top:0});
 if(cat==='research')$('#source').hidden=true;
 if(cat==='dash')return loadDash();
 if(cat==='tweets')return loadTgBoard();
 if(cat==='health')return renderHealth();
 if(cat==='saved')return renderSaved();
 if(cat==='centers')return renderCenters();
 if(cat==='countries')return renderCountries();
 if(cat==='books')return loadBooks();
 if(cat==='writer')return loadWriter();
 if(cat==='bot')return loadBot();
 if(cat==='map')return loadMap();
 if(cat==='ask')return initAsk();
 if(cat==='sanctions')return loadSanc();
 if(cat==='cases')return loadCases();
 if(cat==='archive')return loadArch();
 if(cat==='net')return loadNet();
 if(cat==='settings')return loadSettings();
 if(cat==='alerts')return loadAlerts();
 if(cat==='center')renderCenterHead();
 if(cat==='country')renderCountryHead();
 if(cat==='qual')renderQualFilter();
 if(cat==='research')$('#desc').innerHTML=esc(DESC.research)+' <button class="lnk" data-cat="centers" style="all:unset;cursor:pointer;color:var(--acc2)">العودة لدليل المراكز</button>';
 load(true)}
function renderActiveTag(){$('#activetag').innerHTML=S.tag&&!['center','country'].includes(S.cat)?`<button class="activetag" id="cleartag" aria-label="إلغاء تصفية الموضوع">${esc(S.tag.replace('★',''))} ×</button>`:''}
let DEDUPE=lsGet('rased_dedupe','1')==='1';
function params(page,per){const c=S.cat==='center',k=S.cat==='country',ql=S.cat==='qual';return new URLSearchParams({dedupe:DEDUPE&&!c?'1':'',cat:(c||k||ql)?'all':S.cat,hours:S.hours,source:c?S.center:S.source,tag:S.tag,q:S.q,country:k?S.country:'',qual:ql?'1':'',event:ql?(S.event||''):'',page,per})}
async function load(reset){
 const feed=$('#feed');feed.className='feed list'+(S.compact?' compact':'');
 if(reset){S.page=1;feed.innerHTML='<div class="loading spinner">جارٍ التحميل…</div>'}
 try{
  const d=await api('/api/items?'+params(S.page,S.per));
  S.total=d.total;d.items.forEach(i=>ITEMS.set(i.id,i));
  const shown=S.hideSeen?d.items.filter(i=>!seen(i.id)):d.items;
  const h=shown.map((it,k)=>card(it,reset&&k===0&&!S.compact)).join('');
  if(reset){feed.innerHTML=h||emptyHtml();S.ids=new Set(d.items.map(i=>i.id))}
  else{feed.insertAdjacentHTML('beforeend',h);d.items.forEach(i=>S.ids.add(i.id))}
  $('#more').hidden=S.page*S.per>=S.total;
  $('#count').textContent=S.total+' عنصر';
 }catch(e){feed.innerHTML='<div class="empty"><b>تعذّر الاتصال بالخادم</b>تأكد أن البرنامج ما زال يعمل ثم حدّث الصفحة.</div>'}}
function renderSaved(){
 const feed=$('#feed');feed.className='feed list'+(S.compact?' compact':'');
 let l=savedList();
 if(S.q)l=l.filter(i=>((i.title_ar||'')+(i.summary_ar||'')+i.title+i.source_ar).includes(S.q));
 l.forEach(i=>ITEMS.has(i.id)||ITEMS.set(i.id,i));
 if(S.hideSeen)l=l.filter(i=>!seen(i.id));
 feed.innerHTML=l.length?l.map(i=>card(i,false)).join(''):'<div class="empty"><b>لا توجد عناصر محفوظة</b>اضغط زر الحفظ على أي خبر أو دراسة لتجده هنا لاحقاً.</div>';
 $('#more').hidden=true;$('#count').textContent=l.length+' عنصر'}
function trHtml(){
 const pv=META?.tr_stats?.providers||[];
 const rd=META?.reader||{};
 return `<div class="box trbox"><div class="boxh"><svg class="i" viewBox="0 0 24 24">${P.lang}</svg>مزودو الترجمة<span class="sp"></span><button class="ibtn" id="trtest">اختبار الترجمة الآن</button></div>
  <div id="trrows">${pv.map(p=>`<div class="trrow"><span>${esc(p.name)}</span><span class="${p.ready?'ok':'bad'}">${p.ready?'يعمل':'متوقف مؤقتاً'}</span><span class="o">نجح ${p.ok}، فشل ${p.fail}${p.err?'، آخر خطأ: '+esc(p.err):''}</span></div>`).join('')}</div>
  <div class="trrow"><span>قارئ المقالات</span><span class="${rd.curl_cffi?'ok':'warn'}">${rd.curl_cffi?'محسّن':'أساسي'}</span><span class="o">${rd.curl_cffi?'curl_cffi مثبت':'لتحسين فتح المواقع المحمية: pip install curl_cffi'}${rd.trafilatura?'، trafilatura مثبت':'، ولاستخراج أدق: pip install trafilatura'}</span></div></div>`}
async function trTest(){
 $('#trrows').innerHTML='<div class="trrow"><span class="spinner">جارٍ الاختبار…</span></div>';
 try{const d=await api('/api/translate-test');
  $('#trrows').innerHTML=d.results.map(r=>`<div class="trrow"><span>${esc(r.name)}</span><span class="${r.ok?'ok':'bad'}">${r.ok?'يعمل':'لا يعمل'}${r.ms?` <span class="mt" style="color:var(--faint)">${r.ms}ms</span>`:''}</span><span class="o" dir="auto">${esc(r.out)}</span></div>`).join('')}
 catch(e){$('#trrows').innerHTML='<div class="trrow"><span class="bad">تعذّر الاختبار</span></div>'}}
let HEALTH=[],HONLY=false;
function hostOf(u){try{return new URL(u).hostname.replace(/^www\./,'')}catch(e){return ''}}
let LANS=null;
function lanHtml(){const l=LANS;if(!l)return'';
 return `<div class="box lanbox"><b style="font:700 14px var(--fd)">الفتح من الجوال وتثبيته كتطبيق</b>
  <div class="row"><label class="opt"><input type="checkbox" id="lanon"${l.lan?' checked':''}>السماح بفتح المركز من الأجهزة على نفس شبكة الإنترنت المنزلية</label></div>
  <div class="row"><span>رمز دخول للأجهزة الأخرى (4 أرقام أو أكثر):</span><input type="password" id="lanpin" placeholder="${l.pin?'محفوظ':'مثلاً 2580'}" inputmode="numeric"><button class="ibtn primary" id="lansave">حفظ</button></div>
  <span class="hint" style="font-size:12.5px;color:var(--muted);line-height:1.9">${l.running_lan?`مفعّل الآن. افتح على جوالك: <code>http://${esc(l.ip)}:${l.port}</code> ثم من قائمة المتصفح اختر «إضافة إلى الشاشة الرئيسية»، فتظهر أيقونة المركز كتطبيق.`:(l.lan?'سيُفعَّل بعد إعادة تشغيل البرنامج.':'بعد التفعيل وإعادة التشغيل يظهر هنا الرابط الذي تفتحه من جوالك.')}
  <br>ضع رمز دخول دائماً، فبدونه يستطيع أي جهاز على الشبكة نفسها فتح المركز. وقد يطلب ويندوز السماح للبرنامج في الجدار الناري عند أول تشغيل، فاختر «السماح».</span></div>`}
async function renderHealth(){
 const feed=$('#feed');feed.className='feed list';$('#more').hidden=true;
 try{LANS=await api('/api/settings')}catch(e){}
 const d=await api('/api/sources');HEALTH=d.items;
 if(!d.items.length){feed.innerHTML=trHtml()+'<div class="empty"><b>لم تكتمل أول دورة جلب بعد</b>انتظر قليلاً ثم عُد إلى هذه الصفحة.</div>';return}
 drawHealth()}
function drawHealth(){
 const bad=HEALTH.filter(s=>!s.ok);const rows=HONLY?bad:HEALTH;
 $('#feed').innerHTML=trHtml()+`<div class="htools"><div class="seg"><button id="hall" class="${HONLY?'':'on'}">كل المصادر (${HEALTH.length})</button><button id="hbad" class="${HONLY?'on':''}">المتعطلة فقط (${bad.length})</button></div><span class="sp" style="flex:1"></span>${bad.length?'<button class="ibtn" id="hcopy">'+ico('copy')+'نسخ روابط المتعطلة</button>':''}</div>
 <div class="tablewrap box"><table><thead><tr><th>المصدر</th><th>القسم</th><th>الحالة</th><th>الموقع والرابط</th><th>طريقة الجلب</th><th>العناصر</th><th>آخر نجاح</th><th>ملاحظة</th></tr></thead><tbody>${
  rows.map(s=>`<tr class="${s.ok?'':'broken'}"><td>${esc(s.name)}</td><td>${esc(CAT[s.cat]?.name||(s.cat==='books'?'مكتبة الكتب':s.cat))}</td><td class="${s.ok?'ok':'bad'}">${s.ok?'يعمل':'متعطل'}</td>
   <td class="lnk">${s.site?`<a href="${esc(s.site)}" target="_blank" rel="noopener">${ico('link')}${esc(hostOf(s.site))}</a>`:''}${s.feed?`<a href="${esc(s.feed)}" target="_blank" rel="noopener" title="${esc(s.feed)}">${ico('pulse')}رابط الخلاصة</a><span class="u">${esc(s.feed)}</span>`:''}${!s.site&&!s.feed?'—':''}</td>
   <td>${esc(s.via)}</td><td class="mt">${s.count}</td><td>${s.last_ok?ago(s.last_ok):'—'}</td><td class="err">${esc(s.error||'')}</td></tr>`).join('')}</tbody></table></div>`}
function copyBroken(){
 const t=HEALTH.filter(s=>!s.ok).map(s=>`${s.name}\n  الموقع: ${s.site||'—'}\n  الخلاصة: ${s.feed||'—'}\n  الخطأ: ${s.error||'—'}`).join('\n\n');
 navigator.clipboard.writeText(t).then(()=>toast('نُسخت روابط المصادر المتعطلة'),()=>toast('تعذّر النسخ'))}

/* لوحة القيادة */
async function loadDash(){
 if(META)renderKpis();
 try{
  const d=await api('/api/boards');
  $('#boards').innerHTML=d.boards.map(b=>{b.items.forEach(i=>ITEMS.set(i.id,i));
   return `<section class="box board" style="--c:${b.color}"><div class="boxh" style="--c:${b.color}">${ico(CICON[b.key])}${esc(b.name)}<span class="sp"></span><button class="lnk" data-cat="${b.key}">عرض الكل</button></div>
   ${b.items.length?`<ol>${b.items.map(i=>`<li><button class="bt${seen(i.id)?' seen':''}" data-open="${i.id}"><time>${Date.now()/1000-i.published<86400?hm(i.published):dm(i.published)}</time><span><span class="t${i.translated===1?'':' pend'}">${esc(T(i))}</span><span class="s">${esc(i.source_ar)}</span></span></button></li>`).join('')}</ol>`:'<div class="empty-s">لا مواد بعد.</div>'}</section>`}).join('');
 }catch(e){$('#boards').innerHTML='<div class="empty"><b>تعذّر الاتصال بالخادم</b>تأكد أن البرنامج ما زال يعمل.</div>'}
 loadTweets();loadCty().then(renderDashCty).catch(()=>{});loadQualBox()}

/* الأخبار النوعية */
let QSTATS=null;const EVC={};let QF='';
async function loadQStats(){QSTATS=await api('/api/qual/stats?hours=24');QSTATS.types.forEach(t=>EVC[t.name]=t.color);return QSTATS}
function qtypesHtml(cur,attr){return `<button class="qt${!cur?' on':''}" ${attr}="" style="--e:var(--red)">الكل <b>${QSTATS.total}</b></button>`+QSTATS.types.filter(t=>t.count||t.name===cur).map(t=>`<button class="qt${cur===t.name?' on':''}" ${attr}="${esc(t.name)}" style="--e:${t.color}"><i></i>${esc(t.name)} <b>${t.count}</b></button>`).join('')}
let QITEMS=[],QIDX=0,QTIMER=null;
async function loadQualBox(){
 try{await loadQStats();$('#qtypes').innerHTML=qtypesHtml(QF,'data-qf');
  let d=await api('/api/items?'+new URLSearchParams({cat:'all',qual:'1',event:QF,hours:24,per:20}));
  if(!d.items.length)d=await api('/api/items?'+new URLSearchParams({cat:'all',qual:'1',event:QF,hours:72,per:20}));
  d.items.forEach(i=>ITEMS.set(i.id,i));
  const cur=QITEMS[QIDX]?.id;QITEMS=d.items;
  const k=QITEMS.findIndex(i=>i.id===cur);QIDX=k>=0?k:0;
  showQ(QIDX,k<0);
 }catch(e){}}
function showQ(i,animate=true){
 const box=$('#qslide');if(!box)return;
 if(!QITEMS.length){box.style.removeProperty('--e');box.innerHTML='<div class="qempty" style="grid-column:1/-1">لا توجد أحداث نوعية من هذا النوع حالياً.</div>';$('#qdots').innerHTML='';$('#qpos').textContent='';$('#qprog').className='';clearTimeout(QTIMER);return}
 QIDX=(i+QITEMS.length)%QITEMS.length;const it=QITEMS[QIDX];
 const e1=(it.events||'').split('|').filter(Boolean)[0];const col=EVC[e1]||'var(--red)';
 $('#qcar').style.setProperty('--e',col);
 box.dataset.open=it.id;box.setAttribute('role','button');box.tabIndex=0;
 box.innerHTML=`<div class="clock2"><b>${hm(it.published)}</b><small>${ago(it.published)}</small></div>
  <div><div class="meta">${evHtml(it.events)}${vfHtml(it)}${(it.countries||'').split('|').filter(Boolean).slice(0,3).map(c=>`<span class="tag cty">${esc(c)}</span>`).join('')}${seen(it.id)?'<span class="badge seen">✓ تمت زيارتها</span>':''}</div>
   <h3>${esc(T(it))}</h3>${it.summary_ar?`<p>${esc(it.summary_ar)}</p>`:''}<div class="src2">${esc(it.source_ar)}، ${esc(CAT[it.cat]?.name||'')}</div></div>
  <span class="ibtn read">${ico('open')}اقرأ</span>`;
 if(animate){box.classList.remove('anim');void box.offsetWidth;box.classList.add('anim')}
 const n=Math.min(QITEMS.length,20);
 $('#qdots').innerHTML=QITEMS.slice(0,n).map((_,j)=>`<button data-qgo="${j}" class="${j===QIDX?'on':''}" aria-label="الخبر ${j+1}"></button>`).join('');
 $('#qpos').textContent=`${QIDX+1}/${QITEMS.length}`;
 const bar=$('#qprog');bar.className='';void bar.offsetWidth;bar.className='run';
 clearTimeout(QTIMER);QTIMER=null}
$('#qprog').addEventListener('animationend',()=>{if(S.cat==='dash')showQ(QIDX+1)});
$('#qprev').onclick=()=>showQ(QIDX-1);$('#qnext').onclick=()=>showQ(QIDX+1);
async function renderQualFilter(){try{await loadQStats();$('#qualfilter').innerHTML=qtypesHtml(S.event||'','data-qev')}catch(e){}}

/* الدول */
let CTY=[];const CTYF={q:'',region:''};let BOOKS_N=0;
async function loadCty(){const d=await api('/api/countries');CTY=d.items;return CTY}
function renderDashCty(){
 const top=CTY.slice().sort((a,b)=>b.day-a.day||b.count-a.count).slice(0,10);const max=Math.max(1,...top.map(c=>c.day||c.count));
 $('#dashCty').innerHTML=top.length?top.map(c=>`<li><button data-country="${esc(c.name)}"><span class="iso">${esc(c.iso)}</span><span>${esc(c.name)}</span><span class="n">${c.day}</span><span class="cbar"><i style="width:${Math.round((c.day||c.count)/max*100)}%"></i></span></button></li>`).join(''):'<li class="count" style="padding:12px 14px">تظهر بعد ترجمة المواد.</li>'}
async function renderCountries(){
 $('#ctygrid').innerHTML='<div class="loading spinner">جارٍ تحميل الدول…</div>';
 try{await loadCty()}catch(e){$('#ctygrid').innerHTML='<div class="empty"><b>تعذّر التحميل</b></div>';return}
 const regs=['',...new Set(CTY.map(c=>c.region).filter(Boolean))];
 $('#ctyregion').innerHTML=regs.map(r=>`<button data-ctyregion="${esc(r)}" class="${CTYF.region===r?'on':''}">${esc(r||'كل المناطق')}</button>`).join('');
 renderCtyGrid()}
function ctyCard(c,max){return `<button class="ctycard" data-country="${esc(c.name)}"><span class="top2"><span class="iso">${esc(c.iso)}</span><b>${esc(c.name)}</b></span><span class="nums"><span><em>${c.count}</em>مادة في الشهر</span><span><em>${c.day}</em>اليوم</span></span><span class="cbar"><i style="width:${Math.round(c.count/max*100)}%"></i></span></button>`}
function renderCtyGrid(){
 const l=CTY.filter(c=>(!CTYF.region||c.region===CTYF.region)&&(!CTYF.q||c.name.includes(CTYF.q)||c.iso.toLowerCase()===CTYF.q.toLowerCase()));
 $('#ctycount').textContent=l.length+' دولة';
 if(!l.length){$('#ctygrid').innerHTML='<div class="empty"><b>لا توجد دول مطابقة</b>ستظهر الدول بعد ربط المواد بها، وهذا يحدث تلقائياً مع وصول الأخبار وترجمتها.</div>';return}
 const max=Math.max(...l.map(c=>c.count));
 if(CTYF.region||CTYF.q){$('#ctygrid').innerHTML='<div class="cgrid2">'+l.map(c=>ctyCard(c,max)).join('')+'</div>';return}
 const groups={};l.forEach(c=>(groups[c.region||'أخرى']=groups[c.region||'أخرى']||[]).push(c));
 $('#ctygrid').innerHTML=Object.entries(groups).map(([r,cs])=>`<div class="regionh">${esc(r)}</div><div class="cgrid2">${cs.map(c=>ctyCard(c,max)).join('')}</div>`).join('')}
function openCountry(name){S.country=name;setView('country')}
async function renderCountryHead(){
 const name=S.country;document.title=name+' | '+TITLE_DEFAULT;
 $('#countryhead').innerHTML=`<button class="back" data-cat="countries">${ico('arrow')}كل الدول</button><div class="box chero"><span class="spinner">…</span></div>`;
 try{const d=await api('/api/country/'+encodeURIComponent(name));if(S.country!==name)return;
  $('#countryhead').innerHTML=`<button class="back" data-cat="countries">${ico('arrow')}كل الدول</button>
  <div class="box chero" style="--c:var(--acc)"><span class="iso big">${esc(d.iso||'—')}</span>
   <div class="grow"><h1>${esc(name)}</h1><div class="cmeta">${d.region?`<span class="pill">${esc(d.region)}</span>`:''}${d.cats.slice(0,4).map(c=>`<span>${esc(CAT[c.cat]?.name||c.cat)}: ${c.count}</span>`).join('')}</div></div>
   <div class="num"><b>${d.count}</b><span>مادة خلال الشهر</span></div></div>
  ${d.tags.length?`<div class="box ctopics"><div class="tags" style="padding:0"><span class="clbl">مواضيع مرتبطة:</span>
   <button class="tag${!S.tag?' on':''}" data-ctag="">كل المواضيع</button>
   ${d.tags.map(t=>`<button class="tag${S.tag===t.tag?' on':''}" data-ctag="${esc(t.tag)}">${esc(t.tag)} <em>${t.count}</em></button>`).join('')}</div></div>`:''}`}catch(e){}}

/* التحقق: فتح أول خبر من العنقود مع قائمة البقية */
async function openCluster(cid){try{const d=await api('/api/cluster/'+encodeURIComponent(cid));d.items.forEach(x=>ITEMS.set(x.id,x));if(d.items.length)openItem(d.items[0].id)}catch(e){}}

/* الإنذار المبكر */
let ALN=0,ALH=48,ALSEEN=+lsGet('rased_alseen','0');
const LVC={3:'#F43F5E',2:'#F59E0B',1:'#38BDF8'};
function alertHtml(a,now_){const tl=a.kind==='field'?'تصاعد ميداني':(a.kind==='country'?'ارتفاع مفاجئ':'موضوع صاعد');
 const btn=a.kind==='topic'?`<button class="ibtn" data-altopic="${esc(a.key)}">عرض الأخبار</button>`:`<button class="ibtn" data-alcountry="${esc(a.key)}">عرض ${esc(a.key)}</button>`;
 return `<div class="al" style="--lc:${LVC[a.level]||LVC[2]}"><span class="lv">${a.level>=3?'إنذار عالٍ':'إنذار'}</span><div><b>${esc(a.msg)}</b><small>${tl} · ${ago(a.created)}</small></div><div class="acts2">${btn}${a.kind!=='topic'?`<button class="ibtn" data-cat="map">الخريطة</button>`:''}</div></div>`}
async function loadAlertCount(){try{const d=await api('/api/alerts?hours=24');const fresh=d.items.filter(a=>a.created>ALSEEN);ALN=fresh.length;
 const b=$('#belln');b.hidden=!ALN;b.textContent=ALN;$('#bell').classList.toggle('hot',fresh.some(a=>a.level>=3));
 const act=d.items.filter(a=>d.now-a.created<6*3600).slice(0,3);
 $('#dashAlerts').innerHTML=act.map(a=>alertHtml(a,d.now)).join('');return d}catch(e){}}
async function loadAlerts(){
 try{const d=await api('/api/alerts?hours='+ALH);
  $('#alcount').textContent=d.items.length+' إنذار';
  $('#allist').innerHTML=d.items.length?d.items.map(a=>alertHtml(a,d.now)).join(''):'<div class="empty"><b>لا توجد إنذارات في هذه المدة</b>يفحص المركز كل 5 دقائق: إذا قفز الحديث عن دولة أو موضوع إلى 3 أضعاف معدله المعتاد أو أكثر، أو توالت 3 أحداث نوعية في دولة خلال ساعتين، يظهر الإنذار هنا وفي الجرس أعلى الصفحة، ويُرسل إلى بوت تيليغرام إن كان مفعّلاً.</div>';
  ALSEEN=d.now;lsSet('rased_alseen',ALSEEN);ALN=0;$('#belln').hidden=true;$('#bell').classList.remove('hot');
 }catch(e){}}

/* الخريطة التفاعلية */
let MAP=null,MLAYER=null,DLAYER=null,MAPH=24,MAPOFF=new Set(),LEAF=null;
function loadLeaflet(){if(LEAF)return LEAF;LEAF=new Promise((ok,no)=>{const l=document.createElement('link');l.rel='stylesheet';l.href='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';document.head.appendChild(l);
 const sc=document.createElement('script');sc.src='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';sc.onload=ok;sc.onerror=()=>{LEAF=null;no()};document.head.appendChild(sc)});return LEAF}
const TILES=[
 {url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',attr:'&copy; OpenStreetMap',dark:'invert'},
 {url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',attr:'&copy; Esri',dark:'native',light:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'},
 {url:'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',attr:'&copy; OpenStreetMap France',dark:'invert'}];
let TIDX=0,TERR=0,TOK=0;
function tileUrl(){const t=TILES[TIDX];const light=document.documentElement.dataset.theme==='light';return (light&&t.light)?t.light:t.url}
function tileFilter(){const t=TILES[TIDX];const light=document.documentElement.dataset.theme==='light';
 $('#map').classList.toggle('mapdark',!light&&t.dark==='invert')}
function nextTiles(){if(TIDX>=TILES.length-1)return;TIDX++;TERR=0;TOK=0;TILE.setUrl(tileUrl());TILE.options.attribution=TILES[TIDX].attr;tileFilter()}
let TILE=null;
async function loadMap(refresh){
 try{await loadLeaflet()}catch(e){$('#map').innerHTML='<div class="mapnote">تعذّر تحميل مكتبة الخرائط. تأكد من اتصال الإنترنت ثم أعد فتح الصفحة.</div>';return}
 if(!MAP){MAP=L.map('map',{zoomControl:true,worldCopyJump:true,attributionControl:true}).setView([30,38],4);
  TILE=L.tileLayer(tileUrl(),{maxZoom:18,attribution:TILES[TIDX].attr,crossOrigin:true}).addTo(MAP);
  TILE.on('tileload',()=>{TOK++});
  TILE.on('tileerror',()=>{TERR++;if(TERR>=6&&TOK<3)nextTiles()});
  MLAYER=L.layerGroup().addTo(MAP);DLAYER=L.layerGroup().addTo(MAP);}
 TILE.setUrl(tileUrl());tileFilter();setTimeout(()=>MAP.invalidateSize(),60);
 let d;try{d=await api('/api/map?hours='+MAPH)}catch(e){return}
 MLAYER.clearLayers();DLAYER.clearLayers();
 (d.net||[]).forEach(n=>{const col=n.level==='critical'?'#A855F7':'#C4B5FD';
  L.circleMarker([n.lat,n.lon],{radius:16,color:col,weight:2,dashArray:'4 4',fill:true,fillColor:col,fillOpacity:.12}).bindTooltip(`انقطاع إنترنت ${n.level==='critical'?'حرج':'جزئي'}: ${n.name}`,{direction:'top'}).addTo(MLAYER)});
 if($('#mapdens').checked){const mx=Math.max(1,...d.density.map(x=>x.count));
  d.density.forEach(c=>L.circle([c.lat,c.lon],{radius:60000+340000*Math.sqrt(c.count/mx),color:'#38BDF8',weight:1,opacity:.5,fillOpacity:.12,interactive:true}).bindTooltip(`${c.name}: ${c.count} خبراً`,{direction:'top'}).addTo(DLAYER))}
 const counts={};
 d.points.forEach(p=>{const e1=p.events[0];counts[e1]=(counts[e1]||0)+1;if(MAPOFF.has(e1))return;
  const m=L.circleMarker([p.lat,p.lon],{radius:p.exact?8:6,color:'#fff',weight:p.exact?1.5:1,fillColor:p.color,fillOpacity:.9});
  m.bindPopup(`<div><span class="meta">${evHtml(p.events.join('|'))}</span><div class="pt">${esc(p.title)}</div><div style="color:#888;font-size:12px">${esc(p.place)}${p.exact?'':' (موقع تقريبي)'} · ${esc(p.source)} · ${ago(p.published)}${p.nsrc>=3?' · ✓ مؤكد':''}</div><button class="ibtn primary" data-open="${p.id}">اقرأ الخبر</button></div>`);
  m.addTo(MLAYER)});
 $('#maplegend').innerHTML=(QSTATS?QSTATS.types:[]).filter(t=>counts[t.name]).map(t=>`<label><input type="checkbox" data-mev="${esc(t.name)}"${MAPOFF.has(t.name)?'':' checked'}><i style="--e:${t.color}"></i>${esc(t.name)}<em>${counts[t.name]}</em></label>`).join('')||'<span class="mapcount">لا أحداث نوعية في هذه المدة.</span>';
 $('#mapcount').textContent=d.points.length+' حدثاً على الخريطة'}
document.addEventListener('change',e=>{if(e.target.id==='mapdens')return loadMap();if(e.target.dataset.mev){e.target.checked?MAPOFF.delete(e.target.dataset.mev):MAPOFF.add(e.target.dataset.mev);loadMap()}});

/* اسأل المركز */
let ASKTXT='',ASKREFS=[];
const ASKEX=['ماذا جرى في سوريا خلال آخر يومين؟','ما آخر ما نُشر عن تنظيم داعش في البادية؟','ما أبرز الأحداث في السودان هذا الأسبوع؟','ما موقف الولايات المتحدة من التصعيد في لبنان؟'];
function initAsk(){if(!$('#askex').innerHTML)$('#askex').innerHTML='<span class="hint" style="font-size:12px;color:var(--faint)">أمثلة:</span>'+ASKEX.map(x=>`<button data-askex="${esc(x)}">${esc(x)}</button>`).join('');setTimeout(()=>$('#askq').focus(),50)}
async function askGo(){
 const qq=$('#askq').value.trim();if(!qq)return;ASKTXT='';$('#askcopy').disabled=true;
 $('#askout').innerHTML='<div class="spinner">جارٍ البحث في المواد المرصودة…</div>';$('#askrefs').innerHTML='';
 let d;try{d=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:qq,days:$('#askdays').value})})}catch(e){$('#askout').innerHTML=`<div class="wempty">${esc(e.message)}</div>`;return}
 ASKREFS=d.refs;$('#askn').textContent=d.refs.length+' مادة';
 d.refs.forEach(r=>ITEMS.has(r.id)||ITEMS.set(r.id,r));
 $('#askrefs').innerHTML=d.refs.map((r,i)=>`<li><button data-open="${r.id}"><span class="k">${i+1}</span><span><span class="meta"><span class="src" style="--c:${CAT[r.cat]?.color||'var(--acc)'}">${esc(r.source_ar)}</span><span>${ago(r.published)}</span></span>${esc(r.title_ar||r.title)}</span></button></li>`).join('')||'<li class="count" style="padding:12px 14px">لم يُعثر على مواد.</li>';
 $('#askout').innerHTML='<div class="spinner">جارٍ كتابة الإجابة…</div>';
 try{const r=await fetch('/api/ask/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:qq,ids:d.refs.map(x=>x.id)})});
  const rd=r.body.getReader();const dec=new TextDecoder();
  while(true){const {done,value}=await rd.read();if(done)break;ASKTXT+=dec.decode(value,{stream:true});ASKTXT=ASKTXT.split('[[WAIT]]').join('').split('[[END]]').join('');
   const k=ASKTXT.indexOf('[[ERROR]]');if(k>=0){const err=ASKTXT.slice(k+9);ASKTXT=ASKTXT.slice(0,k);toast(err.slice(0,140));if(!ASKTXT.trim()){$('#askout').innerHTML=`<div class="wempty">${esc(err)}</div>`;break}}
   askRender()}
 }catch(e){toast('انقطع الاتصال')}
 askRender(true)}
function askRender(done){const h=md(ASKTXT).replace(/\[(\d+(?:\s*[،,]\s*\d+)*)\]/g,(m,g)=>'<sup>'+g.split(/\s*[،,]\s*/).map(n=>{const r=ASKREFS[+n-1];return r?`<a href="#" data-open="${r.id}" title="${esc(r.source_ar)}">[${n}]</a>`:`[${n}]`}).join('')+'</sup>');
 $('#askout').innerHTML=h+(done?'':'<span class="cursor"></span>');$('#askstat').textContent=ASKTXT.trim()?ASKTXT.trim().split(/\s+/).length+' كلمة':'';$('#askcopy').disabled=!ASKTXT.trim()}
$('#askq').addEventListener('keydown',e=>{if(e.key==='Enter')askGo()});

/* العقوبات والتصنيفات */
let SANCMODE='terror',SANCGROUP='',SANCPAGE=1,sqt;
async function loadSanc(){
 $('#sancterrorlbl').hidden=SANCMODE==='terror';$('#sancgroups').hidden=SANCMODE!=='terror';
 try{const d=await api('/api/sanctions?'+new URLSearchParams({mode:SANCMODE,group:SANCGROUP,page:SANCPAGE,q:$('#sancq').value.trim(),terror:$('#sancterror').checked?'1':''}));
  const st=d.state;
  $('#sanclists').innerHTML=d.lists.map(l=>`<div class="box sl"><b>${esc(l.name)}</b><span><span class="n">${l.count||0}</span> اسماً</span>
   <span class="wstat">${l.ok===1?'<span class="ok">● تعمل</span>':(l.ok===0?'<span class="bad">● متعطلة</span>':'● لم تُنزَّل بعد')}${l.last_ok?' · آخر نجاح '+ago(l.last_ok):''}</span>
   ${l.ok===0&&l.error?`<span class="e">${esc(l.error)}</span>`:''}</div>`).join('')+`<div class="box sl"><b>المصنَّفون إرهابياً في القائمتين</b><span><span class="n">${d.terror_total||0}</span> فرداً وكياناً</span><span class="wstat">داعش والقاعدة والنصرة وحزب الله والحرس الثوري وغيرها</span></div>`;
  $('#sanccount').textContent=st.running?'جارٍ تنزيل القوائم…':`${d.total} نتيجة`+(d.last?' · آخر تحديث '+ago(d.last):'');
  $('#sancref').disabled=!!st.running;
  if(st.running)setTimeout(()=>S.cat==='sanctions'&&loadSanc(),8000);
  $('#sancgroups').innerHTML=`<button class="qt${!SANCGROUP?' on':''}" data-sgroup="" style="--e:var(--red)">كل الجماعات <b>${d.terror_total||0}</b></button>`+d.groups.map(g=>`<button class="qt${SANCGROUP===g.name?' on':''}" data-sgroup="${esc(g.name)}" style="--e:#E11D48"><i></i>${esc(g.name)} <b>${g.count}</b></button>`).join('');
  if(!d.lists.some(l=>l.count)){$('#sanclist').innerHTML=`<div class="empty"><b>${st.running?'يجري تنزيل القوائم الآن، انتظر دقيقة':'لم تُنزَّل القوائم بعد'}</b>${st.running?'':'اضغط «تحديث القوائم».'}</div>`;$('#sancpager').innerHTML='';return}
  const typ=t=>t==='individual'?'فرد':(t==='vessel'?'سفينة':(t==='aircraft'?'طائرة':'كيان'));
  $('#sanclist').innerHTML=d.items.length?`<table class="tbl"><thead><tr><th>الاسم</th><th>النوع</th><th>الجماعة</th><th>القائمة والبرنامج</th><th>تفاصيل</th><th>تاريخ الإدراج</th></tr></thead><tbody>${d.items.map(r=>`<tr><td><span class="sname">${esc(r.name)}</span>${r.is_new?' <span class="newdot">جديد</span>':''}</td><td>${typ(r.type)}</td><td>${(r.groups||'').split('|').filter(Boolean).map(g=>`<span class="pg t">${esc(g)}</span>`).join('')||'—'}</td><td>${esc(r.list)}<span class="sub">${(r.program_ar||'').split('، ').filter(Boolean).slice(0,4).map(p=>`<span class="pg">${esc(p)}</span>`).join('')}</span></td><td style="max-width:380px"><span class="sub" dir="auto" style="margin:0">${esc((r.remarks||'').slice(0,240))}</span></td><td class="mt" style="white-space:nowrap">${r.listed?esc(r.listed):(r.is_new?'رُصد '+fmt(r.first_seen):'—')}</td></tr>`).join('')}</tbody></table>`
   :'<div class="empty"><b>لا نتائج</b>جرّب اسماً آخر أو جماعة أخرى.</div>';
  $('#sancpager').innerHTML=d.pages>1?`<button class="ibtn" data-spg="${d.page-1}" ${d.page<=1?'disabled':''}>السابق</button><span class="mt">صفحة ${d.page} من ${d.pages}</span><button class="ibtn" data-spg="${d.page+1}" ${d.page>=d.pages?'disabled':''}>التالي</button>`:'';
 }catch(e){$('#sanclist').innerHTML='<div class="empty"><b>تعذّر الاتصال بالبرنامج</b></div>'}}
$('#sancq').oninput=()=>{clearTimeout(sqt);sqt=setTimeout(()=>{SANCPAGE=1;loadSanc()},400)};$('#sancterror').onchange=()=>{SANCPAGE=1;loadSanc()};

/* ملفات القضايا */
let CASE=null,PICKITEM=null,CASES=[];
async function loadCases(){try{const d=await api('/api/cases');CASES=d.items;
 $('#caselist').innerHTML=d.items.length?d.items.map(c=>`<li><button data-case="${c.id}" class="${c.id===CASE?'on':''}"><b>${esc(c.title)}</b><small>${c.n} مادة · ${ago(c.updated)}</small></button></li>`).join(''):'<li class="count" style="padding:12px 14px">لا توجد قضايا بعد.</li>';
 if(CASE)openCase(CASE)}catch(e){}}
async function openCase(cid){CASE=cid;document.querySelectorAll('[data-case]').forEach(b=>b.classList.toggle('on',b.dataset.case===cid));
 try{const d=await api('/api/cases/'+cid);const c=d.case;
  d.items.forEach(i=>ITEMS.has(i.id)||ITEMS.set(i.id,i));
  $('#casedetail').innerHTML=`<div class="boxh"><input id="ctitle" value="${esc(c.title)}" style="flex:1;font:700 15px var(--fd);background:none;border:0;color:var(--text)"><a class="ibtn" href="/print/case/${cid}" target="_blank" rel="noopener">${ico('pdf')}تقرير PDF</a><button class="ibtn" id="casesave">حفظ</button><button class="ibtn" id="casedel" style="color:var(--red)">حذف</button></div>
   <div style="padding:10px 16px"><textarea id="cdescr" placeholder="وصف القضية أو فرضيتها…" style="width:100%;min-height:50px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:8px 10px;color:var(--text);font:14px 'IBM Plex Sans Arabic'">${esc(c.descr||'')}</textarea></div>
   ${d.items.length?d.items.map(i=>`<div class="citem"><div class="meta"><span class="src" style="--c:${CAT[i.cat]?.color||'var(--acc)'}">${esc(i.source_ar)}</span><span>${fmt(i.published)}</span>${i.archived?'<span class="badge seen">مؤرشف</span>':''}</div><h4><button class="ttl" data-open="${i.id}">${esc(i.title_ar||i.title)}</button></h4>
    <textarea data-noteof="${i.id}" placeholder="ملاحظتك على هذه المادة…">${esc(i.note||'')}</textarea>
    <div class="row"><button class="ibtn" data-cnote="${i.id}" style="height:30px">حفظ الملاحظة</button>${i.link?`<a class="ibtn" href="${esc(i.link)}" target="_blank" rel="noopener" style="height:30px">المصدر</a>`:''}<button class="ibtn" data-archopen="${i.id}" style="height:30px">النسخة المؤرشفة</button><button class="ibtn" data-cidel="${i.id}" style="height:30px;color:var(--red)">إزالة</button></div></div>`).join(''):'<div class="wempty">لا مواد في هذه القضية بعد. افتح أي خبر واضغط «ملف قضية».</div>'}`}catch(e){}}
async function pickCase(iid){PICKITEM=iid;let cs=[];try{cs=(await api('/api/cases')).items}catch(e){}
 const el=document.createElement('div');el.className='casepick';el.id='casepick';
 el.innerHTML=`<div class="box"><b style="font:700 15px var(--fd)">أضف المادة إلى ملف قضية</b>${cs.length?`<div class="opts">${cs.map(c=>`<button data-pickcase="${c.id}">${esc(c.title)} <span class="wstat">(${c.n})</span></button>`).join('')}</div><span class="hint" style="font-size:12px;color:var(--faint)">أو أنشئ قضية جديدة:</span>`:''}<input id="picktitle" placeholder="عنوان قضية جديدة"><div style="display:flex;gap:8px"><button class="ibtn primary" id="picknew">إنشاء وإضافة</button><button class="ibtn" id="pickclose">إلغاء</button></div></div>`;
 ($('#dlg').open?$('#dlg'):document.body).appendChild(el)}
function addToCase(cid,iid){api('/api/cases/'+cid,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:iid})}).then(()=>{$('#casepick')?.remove();toast('أُضيفت المادة إلى القضية وتُؤرشف الآن')})}

/* الأرشيف والعناوين المعدّلة */
let ATAB='arch',aqt,AH=24,APAGE=1;
function pagerHtml(p,pages){return pages>1?`<button class="ibtn" data-apg="${p-1}" ${p<=1?'disabled':''}>السابق</button><span class="mt">صفحة ${p} من ${pages}</span><button class="ibtn" data-apg="${p+1}" ${p>=pages?'disabled':''}>التالي</button>`:''}
async function loadArch(){
 const qq=$('#archq').value.trim();
 const prm=new URLSearchParams({q:qq,hours:AH,page:APAGE});
 $('#archclear').hidden=ATAB!=='arch';
 $('#archq').placeholder=ATAB==='arch'?'ابحث في الأرشيف كله…':'ابحث في كل العناوين المعدّلة…';
 if(ATAB==='edits'){try{const d=await api('/api/edits?'+prm);
  $('#archcount').textContent=(qq?'نتائج البحث: ':'')+d.count+' تعديل';
  $('#archlist').innerHTML=d.items.length?`<table class="tbl"><thead><tr><th>المصدر</th><th>العنوان السابق ← الجديد</th><th>وقت التعديل</th><th></th></tr></thead><tbody>${d.items.map(c=>`<tr><td style="white-space:nowrap">${esc(c.source_ar||'')}</td><td><del dir="auto" style="color:var(--red)">${esc(c.old_title)}</del><br><ins dir="auto" style="color:var(--green);text-decoration:none">${esc(c.new_title)}</ins>${c.new_ar?`<span class="sub">${esc(c.new_ar)}</span>`:''}<br><button data-open="${c.item_id}" style="all:unset;cursor:pointer;color:var(--acc2);font-size:12.5px">فتح الخبر</button></td><td class="mt" style="white-space:nowrap">${fmt(c.changed)}</td><td><button class="del" data-edel="${c.rid}" title="حذف من السجل" aria-label="حذف">×</button></td></tr>`).join('')}</tbody></table>`
   :`<div class="empty"><b>${qq?'لا نتائج':'لا تعديلات في هذه المدة'}</b>${qq?'جرّب كلمة أخرى.':'حين تغيّر صحيفة عنوان خبر بعد نشره يُسجَّل هنا. جرّب مدة أطول من الأزرار أعلاه.'}</div>`;
  $('#archpager').innerHTML=pagerHtml(d.page,d.pages)}catch(e){}return}
 try{const d=await api('/api/archive?'+prm);
  $('#archcount').textContent=(qq?`نتائج البحث في كل الأرشيف: ${d.count}`:`${d.count} مادة في هذه المدة`)+` · الأرشيف كله ${d.total}`;
  $('#archlist').innerHTML=d.items.length?`<table class="tbl"><thead><tr><th>المادة</th><th>سبب الأرشفة</th><th>وقت الأرشفة</th><th></th></tr></thead><tbody>${d.items.map(a=>`<tr><td><b dir="auto">${esc(a.title_ar||a.title)}</b><span class="sub">${esc(a.source||'')}، نُشر ${fmt(a.published)}</span></td><td style="white-space:nowrap">${esc(a.reason||'')}${a.wayback?'<span class="sub">+ أرشيف الإنترنت</span>':''}</td><td class="mt" style="white-space:nowrap">${fmt(a.captured)}</td><td style="white-space:nowrap"><button class="ibtn" data-archopen="${a.item_id}" style="height:30px">عرض</button>${a.wayback?` <a class="ibtn" href="${esc(a.wayback)}" target="_blank" rel="noopener" style="height:30px">Wayback</a>`:''} <button class="del" data-adel="${a.item_id}" title="حذف من الأرشيف" aria-label="حذف">×</button></td></tr>`).join('')}</tbody></table>`
   :`<div class="empty"><b>${qq?'لا نتائج في الأرشيف':'لا مواد مؤرشفة في آخر '+(AH==24?'24 ساعة':'مدة')}</b>${qq?'جرّب كلمة أخرى.':'تُؤرشف تلقائياً الأخبار النوعية وكل مقال تفتحه أو تحفظه أو تضيفه لقضية. اختر «الكل» لرؤية الأرشيف الأقدم.'}</div>`;
  $('#archpager').innerHTML=pagerHtml(d.page,d.pages)}catch(e){}}
$('#archq').oninput=()=>{clearTimeout(aqt);aqt=setTimeout(()=>{APAGE=1;loadArch()},400)};
$('#wlogq').oninput=renderWLog;
async function openArchived(iid){try{const d=await api('/api/archive/'+iid);const a=d.item;
 S.openId=null;CUR={id:null,full:null,showOrig:false};
 $('#dlgMeta').innerHTML=`<span class="src">${esc(a.source||'')}</span><span>نسخة محفوظة في ${esc(fmt(a.captured))}</span>`;
 $('#dlgBody').innerHTML=`<div class="dossier">ARCHIVED COPY / ${esc(a.reason||'')}</div><h2 dir="auto">${esc(a.title_ar||a.title)}</h2>
  <div class="dlgacts">${a.link?`<a class="ibtn" href="${esc(a.link)}" target="_blank" rel="noopener">${ico('link')}الرابط الأصلي</a>`:''}${a.wayback?`<a class="ibtn" href="${esc(a.wayback)}" target="_blank" rel="noopener">نسخة أرشيف الإنترنت</a>`:''}</div>
  ${a.paras_ar.length?'<h4>الترجمة</h4>'+a.paras_ar.map(p=>`<p dir="auto">${esc(p)}</p>`).join(''):''}
  <h4>النص الأصلي كما حُفظ</h4><div class="arcsnap">${a.paras.map(p=>`<p dir="auto">${esc(p)}</p>`).join('')||'<p class="note">لا يوجد نص.</p>'}</div>
  <p class="note">مصدر النص: ${esc(a.via||'')}</p>`;
 if(!$('#dlg').open)$('#dlg').showModal()}catch(e){toast('لا توجد نسخة مؤرشفة لهذه المادة بعد')}}

/* انقطاع الإنترنت */
let NETBAD=0;const NLV={critical:['#A855F7','انقطاع حرج'],warning:['#F59E0B','اضطراب جزئي'],normal:['#2BF0B4','طبيعي']};
async function loadNet(){try{const d=await api('/api/net');NETBAD=d.countries.filter(c=>c.level!=='normal').length;
 $('#netgrid').innerHTML=d.countries.map(c=>`<div class="box netc" style="--nc:${NLV[c.level][0]}"><b>${esc(c.name)}</b><span class="st">${NLV[c.level][1]}</span>${c.sources.length?`<small>${esc(c.sources.join('، '))}</small>`:''}<small>${c.last?'آخر تنبيه '+ago(c.last):'لا تنبيهات خلال 48 ساعة'}</small><a href="${esc(c.link)}" target="_blank" rel="noopener">المنحنى التفصيلي في IODA</a></div>`).join('');
 $('#netlast').textContent=d.error?'تعذّر التحديث: '+d.error:(d.last?'آخر تحديث '+ago(d.last):'أول تحديث بعد دقيقة من التشغيل');
 $('#netrecent').innerHTML=d.recent.length?`<table class="tbl"><thead><tr><th>الدولة</th><th>المستوى</th><th>المؤشر</th><th>الانخفاض</th><th>الوقت</th></tr></thead><tbody>${d.recent.map(r=>`<tr><td>${esc(r.name)}</td><td style="color:${NLV[r.level][0]};font-weight:700">${NLV[r.level][1]}</td><td>${esc(r.source_ar)}</td><td class="mt">${r.value!=null&&r.hist?Math.max(0,Math.round((1-r.value/r.hist)*100))+'%':'—'}</td><td class="mt" style="white-space:nowrap">${fmt(r.ts)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty"><b>لا انقطاعات مرصودة خلال 48 ساعة</b>يفحص المركز كل 10 دقائق. أي انقطاع حرج يظهر هنا وعلى الخريطة، ويُطلق إنذاراً مبكراً وإشعاراً.</div>'}catch(e){}}

/* الإعدادات */
async function loadSettings(){
 try{LANS=await api('/api/settings');$('#setlan').innerHTML=lanHtml()}catch(e){}
 loadUpdBox()}
async function loadUpdBox(){try{const d=await api('/api/update');const c=d.cfg,st=d.state;
 $('#updbox').innerHTML=`<b style="font:700 14px var(--fd)">التحديث التلقائي من GitHub</b>
  <span style="font-size:13px">الإصدار الحالي: <b class="mt">${esc(d.version)}</b>${st.remote_version?` · على GitHub: <b class="mt">${esc(st.remote_version)}</b>`:''}${st.last?` · آخر فحص ${ago(st.last)}`:''}</span>
  ${st.state?`<span style="font-size:13px" class="${st.ready?'ok':''}">${esc(st.state)}</span>`:''}${st.error?`<span class="warn" style="font-size:12.5px">${esc(st.error)}</span>`:''}
  <div class="row"><span style="font-size:13px">المستودع:</span><input id="updrepo" value="${esc(c.repo)}" dir="ltr" style="flex:1;min-width:220px;height:34px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 10px;color:var(--text)"><input id="updbranch" value="${esc(c.branch)}" dir="ltr" style="width:90px;height:34px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 10px;color:var(--text)"><button class="ibtn" id="updsave">حفظ</button></div>
  <label class="opt"><input type="checkbox" id="updauto"${c.auto?' checked':''}>فحص التحديثات تلقائياً كل 3 ساعات وعند التشغيل</label>
  <div class="row"><button class="ibtn primary" id="updcheck">تحقق من التحديث الآن</button>${st.ready?'<button class="ibtn" id="updgo2">إعادة التشغيل لتطبيقه</button>':''}</div>`}catch(e){}}
function updBanner(){const u=META?.update;if(u&&u.ready&&!sessionStorage.getItem('upd_later')){$('#updtxt').textContent=`🔄 نُزِّل تحديث جديد للمركز${u.version?' (الإصدار '+u.version+')':''}. أعد التشغيل لتطبيقه.`;$('#updbar').hidden=false}else $('#updbar').hidden=true}
document.addEventListener('change',e=>{if(e.target.id==='updauto')api('/api/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({auto:e.target.checked})}).then(()=>toast('حُفظ'))});

/* وضع الشاشة الكبيرة */
let WALL={i:0,map:null,layer:null},WSLIDES=['الخريطة الحية','الأحداث النوعية','الإنذارات وحالة الإنترنت','الدول الأكثر حضوراً'];
async function wallStart(){$('#wall').hidden=false;try{await document.documentElement.requestFullscreen()}catch(e){}WALL.i=0;wallClock();WALL.ct=setInterval(wallClock,1000);wallTicker();wallShow()}
function wallStop(){$('#wall').hidden=true;clearInterval(WALL.ct);clearTimeout(WALL.to);if(document.fullscreenElement)document.exitFullscreen().catch(()=>{})}
function wallClock(){const n=new Date();$('#wclock').textContent=n.toLocaleTimeString('en-GB')}
async function wallTicker(){try{const d=await api('/api/items?'+new URLSearchParams({cat:'all',per:25}));$('#wtick').innerHTML=d.items.map(i=>`<span>${esc(i.title_ar||i.title)} — ${esc(i.source_ar)}</span>`).join('');$('#wtick').style.animationDuration=Math.max(120,d.items.length*9)+'s'}catch(e){}}
async function wallShow(){
 if($('#wall').hidden)return;
 const k=WALL.i%WSLIDES.length;$('#wslidename').textContent=WSLIDES[k];
 const bar=$('#wprog');bar.className='';void bar.offsetWidth;bar.className='run';
 $('#wmap').style.visibility=k===0?'visible':'hidden';$('#wpanel').style.display=k===0?'none':'block';
 try{
  if(k===0){await loadLeaflet();if(!WALL.map){WALL.map=L.map('wmap',{zoomControl:false,attributionControl:false}).setView([31,40],5);WALL.tile=L.tileLayer(tileUrl(),{maxZoom:18,crossOrigin:true}).addTo(WALL.map);WALL.layer=L.layerGroup().addTo(WALL.map)}
   $('#wmap').classList.toggle('mapdark',document.documentElement.dataset.theme!=='light'&&TILES[TIDX].dark==='invert');setTimeout(()=>WALL.map.invalidateSize(),80);
   const d=await api('/api/map?hours=24');WALL.layer.clearLayers();
   d.points.forEach(p=>L.circleMarker([p.lat,p.lon],{radius:p.exact?11:8,color:'#fff',weight:1.5,fillColor:p.color,fillOpacity:.9}).bindTooltip(`${p.events[0]}: ${p.title}`,{permanent:false}).addTo(WALL.layer));
   (d.net||[]).forEach(n=>L.circleMarker([n.lat,n.lon],{radius:22,color:'#A855F7',weight:2,dashArray:'5 5',fillOpacity:.1}).addTo(WALL.layer))}
  if(k===1){const d=await api('/api/items?'+new URLSearchParams({cat:'all',qual:'1',hours:24,per:6}));
   $('#wpanel').innerHTML=`<div class="wgrid2">${d.items.map(i=>{const e1=(i.events||'').split('|').filter(Boolean)[0];return `<div class="wcard" style="--e:${EVC[e1]||'var(--red)'}"><div class="meta">${evHtml(i.events)}${vfHtml(i)}<span>${hm(i.published)}</span></div><h3>${esc(i.title_ar||i.title)}</h3><div class="meta"><span>${esc(i.source_ar)}</span>${(i.countries||'').split('|').filter(Boolean).slice(0,2).map(c=>`<span>${esc(c)}</span>`).join('')}</div></div>`}).join('')||'<div class="wbig">لا أحداث نوعية خلال 24 ساعة</div>'}</div>`}
  if(k===2){const [al,nt]=await Promise.all([api('/api/alerts?hours=24'),api('/api/net')]);
   $('#wpanel').innerHTML=`<div class="wcols"><div class="wlist"><div class="wbig">الإنذارات المبكرة</div>${al.items.slice(0,6).map(a=>alertHtml(a,al.now)).join('')||'<div class="meta">لا إنذارات خلال 24 ساعة</div>'}</div><div><div class="wbig">حالة الإنترنت</div><div class="netgrid">${nt.countries.slice(0,12).map(c=>`<div class="box netc" style="--nc:${NLV[c.level][0]}"><b>${esc(c.name)}</b><span class="st">${NLV[c.level][1]}</span></div>`).join('')}</div></div></div>`}
  if(k===3){await loadCty();const top=CTY.slice().sort((a,b)=>b.day-a.day).slice(0,12);const mx=Math.max(1,...top.map(c=>c.day));
   $('#wpanel').innerHTML=`<div class="wbig">الدول الأكثر حضوراً اليوم</div><div class="netgrid" style="grid-template-columns:repeat(3,1fr)">${top.map(c=>`<div class="box netc" style="--nc:var(--acc)"><b style="font-size:20px">${esc(c.name)}</b><span class="st">${c.day} خبراً اليوم</span><div class="cbar"><i style="width:${Math.round(c.day/mx*100)}%"></i></div></div>`).join('')}</div>`}
 }catch(e){}
 WALL.i++;clearTimeout(WALL.to);WALL.to=setTimeout(wallShow,20000)}
document.addEventListener('fullscreenchange',()=>{if(!document.fullscreenElement&&!$('#wall').hidden){}});

/* لوحة الأوامر */
let CMDI=[],CMDS=0;
function cmdOpen(){$('#cmdk').hidden=false;$('#cmdin').value='';cmdFill('');setTimeout(()=>$('#cmdin').focus(),20)}
function cmdClose(){$('#cmdk').hidden=true}
function nrm(t){return (t||'').replace(/[أإآ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').toLowerCase()}
function cmdFill(qq){const n=nrm(qq.trim());const out=[];
 const views=Object.keys(CICON).filter(k=>EXTRA[k]||CAT[k]).map(k=>({ic:CICON[k],t:EXTRA[k]||CAT[k].name,k:'قسم',run:()=>setView(k)}));
 const ctys=CTY.map(c=>({ic:'flag',t:c.name,k:'دولة',run:()=>openCountry(c.name)}));
 const ctrs=CENTERS.map(c=>({ic:'centers',t:c.name,k:'مركز',run:()=>openCenter(c.name)}));
 const pool=n?[...views,...ctys,...ctrs].filter(o=>nrm(o.t).includes(n)):views;
 out.push(...pool.slice(0,9));
 if(n){out.push({ic:'search',t:`ابحث في الأخبار عن: ${qq.trim()}`,k:'بحث',run:()=>{$('#q').value=qq.trim();S.q=qq.trim();setView('all')}});
  out.push({ic:'search',t:`اسأل المركز: ${qq.trim()}`,k:'سؤال',run:()=>{setView('ask');$('#askq').value=qq.trim();askGo()}});}
 out.push({ic:'screen',t:'وضع الشاشة الكبيرة',k:'أمر',run:wallStart});
 CMDI=out;CMDS=0;cmdDraw()}
function cmdDraw(){$('#cmdlist').innerHTML=CMDI.map((o,i)=>`<li class="${i===CMDS?'on':''}" data-cmdi="${i}">${ico(o.ic)}<span>${esc(o.t)}</span><span class="k">${esc(o.k)}</span></li>`).join('');
 const el=$('#cmdlist .on');el&&el.scrollIntoView({block:'nearest'})}
function cmdRun(i){const o=CMDI[i];if(!o)return;cmdClose();o.run()}
$('#cmdin').addEventListener('input',e=>cmdFill(e.target.value));
$('#cmdin').addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();CMDS=Math.min(CMDI.length-1,CMDS+1);cmdDraw()}else if(e.key==='ArrowUp'){e.preventDefault();CMDS=Math.max(0,CMDS-1);cmdDraw()}else if(e.key==='Enter'){e.preventDefault();cmdRun(CMDS)}else if(e.key==='Escape'){cmdClose()}});
$('#cmdlist').addEventListener('click',e=>{const li=e.target.closest('[data-cmdi]');if(li)cmdRun(+li.dataset.cmdi)});
$('#cmdk').addEventListener('click',e=>{if(e.target.id==='cmdk')cmdClose()});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&(e.key==='k'||e.key==='K'||e.code==='KeyK')){e.preventDefault();$('#cmdk').hidden?cmdOpen():cmdClose()}
 else if(e.key==='Escape'&&!$('#wall').hidden)wallStop()});

/* بوت تيليغرام */
let BOTD=null,BOTON=false;
function bpost(body,msg){return api('/api/bot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(()=>{if(msg)toast(msg);return loadBot()}).catch(e=>{toast(e.message);loadBot()})}
async function loadBot(statusOnly){
 try{BOTD=await api('/api/bot')}catch(e){return}
 const c=BOTD.cfg,st=BOTD.state;BOTON=c.enabled;
 const left=Math.max(0,st.next_due-st.now);
 $('#bstat').innerHTML=`الحالة: <b class="${c.enabled?'ok':''}">${c.enabled?'يعمل':'متوقف'}</b>${st.bot_name?` (@${esc(st.bot_name)})`:''}<br>
  أُرسل اليوم: <b>${st.sent_today}</b> مقالة<br>
  آخر إرسال: <b>${st.last_sent?ago(st.last_sent):'—'}</b><br>
  ${c.enabled?`الإرسال القادم: <b>${left?'بعد '+left+' ثانية':'الآن'}</b><br>`:''}
  ${st.last_error?`<span class="warn">آخر خطأ: ${esc(st.last_error)}</span>`:''}
  <div class="hint" style="margin-top:6px;color:var(--faint);font-size:12px">يعمل البوت ما دام البرنامج مفتوحاً على جهازك.</div>`;
 $('#brecent').innerHTML=BOTD.recent.length?BOTD.recent.map(r=>`<li><button class="t" data-open="${r.id}">${esc(r.title||'')}<span class="wstat" style="display:block">${fmt(r.sent)}</span></button></li>`).join(''):'<li class="count" style="padding:12px 14px">لم يُرسل شيء بعد.</li>';
 if(statusOnly&&$('#bform').innerHTML)return;
 const ck=(k,label,sub)=>`<label class="opt"><input type="checkbox" data-bopt="${k}"${c[k]?' checked':''}><span>${label}${sub?`<small>${sub}</small>`:''}</span></label>`;
 $('#bform').innerHTML=`
  <div class="bigtoggle"><span><b>تشغيل النشر الآلي</b><br><span class="hint">${c.has_token&&c.chat?'كل شيء جاهز':'أكمل الخطوتين 1 و2 أولاً'}</span></span><label class="sw"><input type="checkbox" id="benabled"${c.enabled?' checked':''}><span></span></label></div>
  <label class="f">1. رمز البوت (Token)
   <div class="row"><input type="password" id="btoken" class="ltr" placeholder="${c.has_token?esc(c.token_hint)+' (محفوظ)':'123456789:AA...'}" autocomplete="off"><button class="ibtn primary" id="btokensave">حفظ</button></div>
   <span class="hint">أنشئ بوتاً من <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a> في تيليغرام: أرسل له <code>/newbot</code> واختر اسماً، فيعطيك الرمز.</span></label>
  <label class="f">2. أين تُرسل المقالات؟ (معرّف القناة أو المجموعة)
   <div class="row"><input type="text" id="bchat" class="ltr" value="${esc(c.chat)}" placeholder="@my_channel  أو  -1001234567890"><button class="ibtn" id="bchatsave">حفظ</button><button class="ibtn" id="bdetect">اكتشاف تلقائي</button></div>
   <span class="hint"><ol><li>لقناة: أضف البوت مشرفاً في القناة، ثم اكتب معرّفها مثل <code>@my_channel</code>.</li><li>لمجموعة أو محادثة خاصة: أضف البوت أو أرسل له <code>/start</code>، ثم اضغط «اكتشاف تلقائي» واختر من القائمة.</li></ol></span>
   <div class="chatlist" id="bchats"></div></label>
  <div class="row"><button class="ibtn" id="btest">إرسال رسالة تجريبية</button></div>
  <label class="f">3. كل كم يُرسل؟
   <select id="binterval">${[[60,'كل دقيقة'],[120,'كل دقيقتين'],[300,'كل 5 دقائق'],[600,'كل 10 دقائق'],[900,'كل 15 دقيقة'],[1800,'كل 30 دقيقة'],[3600,'كل ساعة']].map(([v,n])=>`<option value="${v}"${+c.interval===v?' selected':''}>${n}</option>`).join('')}</select></label>
  <label class="f">4. الأقسام التي يُرسل منها
   <div class="cks">${BOTD.cats.map(k=>`<label><input type="checkbox" data-bcat="${k.key}"${c.cats.includes(k.key)?' checked':''}>${esc(k.name)}</label>`).join('')}</div></label>
  <div class="f" style="display:flex;flex-direction:column;gap:10px">
   ${ck('preview','معاينة الرابط','يُظهر تيليغرام صورة المقال وعنوانه أسفل الرسالة')}
   <span class="hint">لا تُرسل الأخبار النوعية ولا الإنذارات ولا مقاطع الفيديو؛ يرسل البوت المقالات والدراسات والأخبار العالمية فقط.</span>
  </div>`}
$('#botview').addEventListener('change',e=>{const t=e.target;
 if(t.id==='benabled')return bpost({enabled:t.checked},t.checked?'بدأ النشر الآلي':'توقف النشر الآلي');
 if(t.id==='binterval')return bpost({interval:+t.value},'حُفظ');
 if(t.dataset.bcat)return bpost({cats:[...document.querySelectorAll('[data-bcat]:checked')].map(x=>x.dataset.bcat)},'حُفظت الأقسام');
 if(t.dataset.bopt)return bpost({[t.dataset.bopt]:t.checked},'حُفظ')});
$('#botview').addEventListener('click',async e=>{const t=e.target.closest('button');if(!t)return;
 if(t.id==='btokensave'){const v=$('#btoken').value.trim();if(!v)return;toast('جارٍ التحقق من الرمز…');return bpost({token:v},'حُفظ رمز البوت')}
 if(t.id==='bchatsave')return bpost({chat:$('#bchat').value.trim()},'حُفظ معرّف المحادثة');
 if(t.id==='btest'){try{await api('/api/bot/test',{method:'POST'});toast('أُرسلت الرسالة التجريبية، تحقق من تيليغرام')}catch(err){toast(err.message)}return}
 if(t.id==='bsendnow'){t.disabled=true;try{const d=await api('/api/bot/send-now',{method:'POST'});toast(d.sent?'أُرسلت مقالة':'لا توجد مقالات جديدة غير مرسلة في الأقسام المختارة')}catch(err){toast(err.message)}t.disabled=false;return loadBot(true)}
 if(t.id==='breset'){if(!confirm('مسح سجل الإرسال؟ قد يُعاد إرسال مقالات سبق إرسالها.'))return;await api('/api/bot/reset',{method:'POST'});toast('مُسح السجل');return loadBot(true)}
 if(t.id==='bdetect'){$('#bchats').innerHTML='<span class="spinner">جارٍ البحث…</span>';
  try{const d=await api('/api/bot/chats');$('#bchats').innerHTML=d.chats.length?d.chats.map(c=>`<button data-bchat="${c.id}">${esc(c.name||String(c.id))} <span class="mt" style="color:var(--faint)">${c.id} · ${esc(c.type)}</span></button>`).join(''):'<span class="hint">لم يُعثر على محادثات. أرسل للبوت رسالة أو اكتب في المجموعة بعد إضافته، ثم أعد المحاولة.</span>'}
  catch(err){$('#bchats').innerHTML=`<span class="warn">${esc(err.message)}</span>`}return}
 if(t.dataset.bchat){$('#bchat').value=t.dataset.bchat;return bpost({chat:t.dataset.bchat},'حُفظ معرّف المحادثة')}});
setInterval(()=>{if(S.cat==='bot')loadBot(true)},5000);

/* كاتب المقالات */
let WCFG=null,WBODY='',WABORT=null,WSAVED=null;
const MD_ESC=t=>esc(t).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/(https?:\/\/[^\s<)]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>');
function md(t){
 const out=[];let list=null;
 for(const raw of t.split('\n')){const l=raw.trim();
  if(/^[-*•]\s+/.test(l)||/^\d+[.)]\s+/.test(l)){const ol=/^\d/.test(l);if(!list||list.ol!==ol){if(list)out.push(list.ol?'</ol>':'</ul>');out.push(ol?'<ol>':'<ul>');list={ol}}out.push('<li>'+MD_ESC(l.replace(/^([-*•]|\d+[.)])\s+/,''))+'</li>');continue}
  if(list){out.push(list.ol?'</ol>':'</ul>');list=null}
  if(!l)continue;
  const h=l.match(/^(#{1,3})\s+(.*)/);
  if(h){out.push(`<h${h[1].length}>${MD_ESC(h[2])}</h${h[1].length}>`);continue}
  out.push(`<p dir="auto">${MD_ESC(l)}</p>`)}
 if(list)out.push(list.ol?'</ol>':'</ul>');return out.join('')}
const PROVS=[['free','مجاني فوري: بلا مفتاح ولا تثبيت'],['gemini','Gemini: مفتاح مجاني'],['ollama','Ollama: على جهازك'],['claude','Claude: مدفوع']];
async function loadWriter(){
 try{WCFG=await api('/api/writer/config')}catch(e){return}
 const opt=(l,cur)=>l.map(o=>`<option value="${esc(o.id)}"${o.id===cur?' selected':''}>${esc(o.name)}</option>`).join('');
 if(!$('#wtype').options.length){$('#wtype').innerHTML=opt(WCFG.types,'analysis');$('#wlen').innerHTML=opt(WCFG.lengths,'medium');$('#wtone').innerHTML=opt(WCFG.tones,'analytical')}
 renderWKey();loadArticles();
 if(WCFG.ollama.pull.running)setTimeout(()=>S.cat==='writer'&&loadWriter(),2000)}
function renderWKey(){
 const c=WCFG,p=c.provider;const opt=(l,cur)=>l.map(o=>typeof o==='string'?`<option${o===cur?' selected':''}>${esc(o)}</option>`:`<option value="${esc(o.id)}"${o.id===cur?' selected':''}>${esc(o.name)}</option>`).join('');
 let h=`<span style="font:700 13.5px var(--fd)">محرك الكتابة</span><div class="seg">${PROVS.map(([k,n])=>`<button data-wprov="${k}" class="${p===k?'on':''}">${n}</button>`).join('')}</div><span class="sp" style="flex:1"></span>${c.ready?'<span class="badge2">جاهز للكتابة</span>':'<span class="badge2" style="color:var(--red);background:rgba(244,63,94,.1)">غير جاهز</span>'}`;
 if(p==='free'){const f=c.free;
  h+=`<label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wfreemodel">${opt(f.models,f.model)}</select></label>
  <div class="full">يعمل فوراً دون مفتاح أو حساب أو تثبيت، عبر خدمة Pollinations المجانية المفتوحة. لاحظ أنها خدمة مجانية من طرف ثالث: قد تكون أبطأ أحياناً، وتسمح بطلب كل بضع ثوانٍ، وقد تغيّر شروطها مستقبلاً. والموضوع والمواد المرجعية تُرسل إليها لكتابة النص، فلا تضع فيها معلومات حساسة. للجودة الأعلى استخدم Gemini بمفتاحه المجاني.</div>`}
 if(p==='ollama'){const o=c.ollama,pl=o.pull;
  if(!o.running)h+=`<div class="full">Ollama برنامج مجاني يشغّل نموذج الكتابة على جهازك نفسه، بلا مفتاح ولا إنترنت ولا تكلفة.<ol><li>نزّله من <a href="https://ollama.com/download" target="_blank" rel="noopener">ollama.com/download</a> وثبّته مثل أي برنامج.</li><li>شغّله (يعمل في الخلفية بجانب الساعة).</li><li>اضغط «تحقق» هنا، ثم نزّل نموذجاً من القائمة التي ستظهر.</li></ol></div><button class="ibtn primary" id="wcheck">تحقق</button>`;
  else{
   if(o.models.length)h+=`<label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wollmodel">${opt(o.models,o.model)}</select></label>`;
   h+=`<div class="sugg"><span style="font:600 12.5px var(--fd)">${o.models.length?'نماذج أخرى يمكنك تنزيلها:':'Ollama يعمل. نزّل نموذجاً للكتابة (مرة واحدة):'}</span>${o.suggest.filter(m=>!o.models.includes(m.id)).map(m=>`<div><button class="ibtn" data-wpull="${esc(m.id)}" ${pl.running?'disabled':''} style="height:30px">تنزيل</button><span>${esc(m.name)}</span></div>`).join('')}</div>`;
   if(pl.running||pl.error)h+=`<div class="full">${pl.error?`<span class="warn">فشل التنزيل: ${esc(pl.error)}</span>`:`جارٍ تنزيل ${esc(pl.model)}: ${esc(pl.status)} ${pl.pct}%`}</div>${pl.running?`<div class="wprog"><i style="width:${pl.pct}%"></i></div>`:''}`;
   h+=`<div class="full">ملاحظة: النماذج المحلية أضعف من Gemini وClaude في العربية والنصوص الطويلة، وسرعتها تعتمد على جهازك.</div>`}}
 if(p==='gemini'){const g=c.gemini;
  if(!g.has_key)h+=`<div class="full">مفتاح Gemini مجاني من Google، يكفي لعدد جيد من المقالات يومياً. احصل عليه خلال دقيقة من <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a> (سجّل بحساب Google ثم «Create API key»).</div><input id="wgemkey" type="password" placeholder="AIza..." autocomplete="off"><button class="ibtn primary" id="wgemsave">حفظ المفتاح</button>`;
  else h+=`<span class="mt" style="color:var(--faint);font-size:12px">${esc(g.key_hint)}</span>${g.error?`<span class="warn" style="font-size:12.5px">${esc(g.error)}</span>`:`<label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wgemmodel">${opt(g.models,g.model)}</select></label>`}<button class="ibtn" id="wgemedit">تغيير المفتاح</button>`}
 if(p==='claude'){const k=c.claude;
  if(!k.has_key)h+=`<div class="full">Claude أعلى جودة في العربية، ويحتاج مفتاحاً مدفوعاً حسب الاستخدام من <a href="https://console.anthropic.com" target="_blank" rel="noopener">console.anthropic.com</a>.</div><input id="wkeyin" type="password" placeholder="sk-ant-..." autocomplete="off"><button class="ibtn primary" id="wkeysave">حفظ المفتاح</button>`;
  else h+=`<span class="mt" style="color:var(--faint);font-size:12px">${esc(k.key_hint)}</span><label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wmodel">${opt(k.models,k.model)}</select></label><button class="ibtn" id="wkeyedit">تغيير المفتاح</button>`}
 h+=`<div class="full" style="color:var(--faint)">المفاتيح تُحفظ على جهازك فقط داخل قاعدة بيانات البرنامج.</div>`;
 $('#wkey').innerHTML=h}
function wcfg(body,msg){return api('/api/writer/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(()=>{if(msg)toast(msg);return loadWriter()}).catch(e=>toast(e.message))}
const ENG={free:'مجاني',gemini:'Gemini',ollama:'Ollama',claude:'Claude'};
function renderWLog(){const all=window._WARTS||[];const qq=($('#wlogq').value||'').trim();
 const l=qq?all.filter(a=>(a.title+' '+a.topic+' '+a.body).includes(qq)):all;
 $('#wlogcount').textContent=l.length+' مقالاً';$('#wlogn').textContent=all.length?'('+all.length+')':'';
 const TN={opinion:'مقال رأي',analysis:'تحليل',study:'دراسة',assessment:'تقدير موقف',report:'تقرير'};
 $('#wloglist').innerHTML=l.length?`<table class="tbl"><thead><tr><th>العنوان</th><th>النوع</th><th>الكلمات</th><th>المحرك</th><th>التاريخ</th><th></th></tr></thead><tbody>${l.map(a=>`<tr><td><b>${esc(a.title||a.topic)}</b><span class="sub">${esc(a.topic||'')}</span></td><td>${esc(TN[a.type]||a.type||'—')}</td><td class="mt">${a.words||(a.body||'').split(/\s+/).length}</td><td>${esc(ENG[a.engine]||a.engine||'—')}</td><td class="mt" style="white-space:nowrap">${fmt(a.created)}</td><td style="white-space:nowrap"><button class="ibtn" data-wlopen="${a.id}" style="height:30px">فتح</button> <button class="ibtn" data-wlcopy="${a.id}" style="height:30px">نسخ</button> <button class="ibtn" data-wlpdf="${a.id}" style="height:30px">PDF</button> <button class="ibtn" data-wdel="${a.id}" style="height:30px;color:var(--red)">حذف</button></td></tr>`).join('')}</tbody></table>`
  :'<div class="empty"><b>لا توجد مقالات في السجل</b>كل مقال يكتبه الكاتب يُحفظ هنا تلقائياً.</div>'}
async function loadArticles(){try{const d=await api('/api/articles');
 $('#warts').innerHTML=d.items.length?d.items.map(a=>`<li><button class="t" data-wart="${a.id}">${esc(a.title||a.topic)}<span class="wstat" style="display:block">${fmt(a.created)}</span></button><button class="x" data-wdel="${a.id}" aria-label="حذف">×</button></li>`).join(''):'<li class="count" style="padding:12px 14px">لا توجد مقالات محفوظة بعد.</li>';
 window._WARTS=d.items;$('#wlogn').textContent=d.items.length?'('+d.items.length+')':'';if(!$('#wlogview').hidden)renderWLog()}catch(e){}}
let wst;$('#wtopic').oninput=()=>{clearTimeout(wst);wst=setTimeout(wSources,600)};
async function wSources(){const t=$('#wtopic').value.trim();const box=$('#wsrc');
 if(!t||!$('#wsrcuse').checked){box.hidden=true;return}
 try{const d=await api('/api/writer/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:t})});
  box.hidden=false;box.innerHTML=d.items.length?`<b style="font:600 12.5px var(--fd)">${d.items.length} مادة مرصودة سيستند إليها:</b>`+d.items.slice(0,12).map(i=>`<div>${esc(i.source_ar)}: ${esc(i.title_ar||i.title)}</div>`).join(''):'لا توجد مواد مرصودة عن هذا الموضوع؛ سيكتب من معرفته العامة.'}catch(e){box.hidden=true}}
$('#wsrcuse').onchange=wSources;
document.addEventListener('change',e=>{const id=e.target.id;
 if(id==='wmodel')wcfg({model:e.target.value},'تم تغيير النموذج');
 if(id==='wgemmodel')wcfg({gemini_model:e.target.value},'تم تغيير النموذج');
 if(id==='wollmodel')wcfg({ollama_model:e.target.value},'تم تغيير النموذج');
 if(id==='wfreemodel')wcfg({free_model:e.target.value},'تم تغيير النموذج')});
let WCONT=false;
function wRender(done){$('#wdoc').innerHTML=md(WBODY)+(done?'':'<span class="cursor"></span>');
 const words=WBODY.trim()?WBODY.trim().split(/\s+/).length:0;$('#wstat').textContent=words+' كلمة'+(WCONT&&!done?'، جارٍ إكمال النص…':'');
 const m=WBODY.match(/^#\s*(.+)/m);$('#wtitle').textContent=m?m[1].slice(0,60):'النص'}
async function wGenerate(){
 const topic=$('#wtopic').value.trim();if(!topic){toast('اكتب الموضوع أولاً');return}
 if(!WCFG?.ready){toast('محرك الكتابة غير جاهز بعد؛ أكمل إعداده في أعلى الصفحة');window.scrollTo({top:0});return}
 WBODY='';WSAVED=null;wRender(false);
 ['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=true);$('#wgo').disabled=true;$('#wgo').textContent='جارٍ الكتابة…';$('#wstop').hidden=false;
 WABORT=new AbortController();
 try{
  const r=await fetch('/api/writer/generate',{method:'POST',signal:WABORT.signal,headers:{'Content-Type':'application/json'},
   body:JSON.stringify({topic,type:$('#wtype').value,length:$('#wlen').value,tone:$('#wtone').value,lang:$('#wlang').value,angle:$('#wangle').value.trim(),use_sources:$('#wsrcuse').checked})});
  const rd=r.body.getReader();const dec=new TextDecoder();
  while(true){const {done,value}=await rd.read();if(done)break;WBODY+=dec.decode(value,{stream:true});
   if(WBODY.includes('[[WAIT]]')){WBODY=WBODY.split('[[WAIT]]').join('');WCONT=true}else WCONT=false;
   if(WBODY.includes('[[END]]'))WBODY=WBODY.split('[[END]]').join('');
   const k=WBODY.indexOf('[[ERROR]]');if(k>=0){const err=WBODY.slice(k+9).trim();WBODY=WBODY.slice(0,k);wRender(true);toast(err);if(!WBODY.trim())$('#wdoc').innerHTML=`<div class="wempty"><b>تعذّرت الكتابة</b>${esc(err)}</div>`;break}
   wRender(false)}
 }catch(e){if(e.name!=='AbortError')toast('انقطع الاتصال أثناء الكتابة')}
 wRender(true);WABORT=null;$('#wgo').disabled=false;$('#wgo').textContent='اكتب الآن';$('#wstop').hidden=true;
 if(WBODY.trim()){['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=false);await wSave(true)}}
async function wSave(auto){if(!WBODY.trim())return;
 try{const d=await api('/api/articles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:WSAVED,topic:$('#wtopic').value.trim(),type:$('#wtype').value,length:$('#wlen').value,lang:$('#wlang').value,engine:WCFG?.provider,body:WBODY})});
  WSAVED=d.id;loadArticles();if(!auto)toast('حُفظ المقال')}catch(e){toast('تعذّر الحفظ')}}
function wPdf(){const m=WBODY.match(/^#\s*(.+)/m);const w=window.open('','_blank');
 w.document.write(`<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>${esc(m?m[1]:'مقال')}</title><link href="https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;700&family=Noto+Kufi+Arabic:wght@700&display=swap" rel="stylesheet"><style>@page{size:A4;margin:20mm 18mm}body{font:13pt/2 "Noto Naskh Arabic",Arial,sans-serif;color:#111;max-width:760px;margin:0 auto;padding:20px}h1{font:700 21pt/1.5 "Noto Kufi Arabic",Arial}h2{font:700 15pt/1.6 "Noto Kufi Arabic",Arial;margin-top:22px}h3{font:700 13pt "Noto Kufi Arabic",Arial}p{text-align:justify;margin:0 0 12px}a{color:#333;word-break:break-all}</style></head><body>${md(WBODY)}<script>addEventListener('load',()=>setTimeout(()=>print(),700))<\/script></body></html>`);w.document.close()}
$('#wgo').onclick=wGenerate;
$('#wstop').onclick=()=>{if(WABORT)WABORT.abort()};
$('#wcopy').onclick=()=>navigator.clipboard.writeText(WBODY).then(()=>toast('نُسخ النص'));
$('#wsave').onclick=()=>wSave(false);
$('#wpdf').onclick=wPdf;

/* مكتبة الكتب */
const BF={topic:'',lang:'',q:''};const BOOKS=new Map();const BCOL={terror:'#E5484D',war:'#E8774A',politics:'#5B9BD5',security:'#F472B6'};
function coverHtml(b){const col=BCOL[b.topic]||'var(--acc)';
 const ph=`<span class="phx">${esc((b.title||'').slice(0,70))}<small>${esc(b.year)}</small></span>`;
 return b.image?`<div class="cover" style="--c:${col}"><img src="${esc(b.image)}" alt="غلاف ${esc(b.title_ar||b.title)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.classList.add('ph');this.remove()">${ph}</div>`
  :`<div class="cover ph" style="--c:${col}">${ph}</div>`}
function bookCard(b,topics){
 const tname=(topics.find(t=>t.key===b.topic)||{}).name||'';
 return `<article class="book" style="--c:${BCOL[b.topic]||'var(--acc)'}">${coverHtml(b)}
  <div class="binfo"><span class="btopic">${esc(tname)}</span><h3>${esc(b.title_ar||b.title)}</h3>
   ${b.title_ar&&b.title_ar!==b.title?`<span class="borig" title="${esc(b.title)}">${esc(b.title)}</span>`:''}
   <span class="bmeta">${esc(b.authors||'مؤلف غير معروف')}، ${esc(b.published||b.year)}${b.publisher?'، '+esc(b.publisher):''}</span>
   ${(b.description_ar||b.description)?`<p dir="auto">${esc(b.description_ar||b.description)}</p>`:'<p>لا يتوفر ملخص لهذا الكتاب.</p>'}
   <div class="bacts"><button class="ibtn" data-book="${esc(b.id)}">${ico('open')}الملخص الكامل</button>${b.link?`<a class="ibtn primary" href="${esc(b.link)}" target="_blank" rel="noopener">${ico('link')}رابط الكتاب</a>`:''}</div></div></article>`}
let BTOPICS=[];
async function loadBooks(){
 const g=$('#bookgrid');g.innerHTML='<div class="loading spinner">جارٍ تحميل المكتبة…</div>';
 try{const d=await api('/api/books?'+new URLSearchParams(BF));BTOPICS=d.topics;
  BOOKS_N=d.topics.reduce((a,t)=>a+t.count,0);
  $('#btopic').innerHTML=`<button data-btopic="" class="${!BF.topic?'on':''}">كل المواضيع</button>`+d.topics.map(t=>`<button data-btopic="${t.key}" class="${BF.topic===t.key?'on':''}">${esc(t.name)} <span class="mt" style="opacity:.6">${t.count}</span></button>`).join('');
  d.items.forEach(b=>BOOKS.set(b.id,b));
  $('#bcount').textContent=d.items.length+' كتاباً';
  g.innerHTML=d.items.length?d.items.map(b=>bookCard(b,d.topics)).join(''):`<div class="empty"><b>${d.running||!BOOKS_N?'يجري تجهيز المكتبة':'لا توجد كتب مطابقة'}</b>${d.running||!BOOKS_N?'يبحث المركز عن الكتب الصادرة في آخر سنتين ويترجم ملخصاتها، وتظهر هنا خلال دقائق.':'غيّر الموضوع أو اللغة أو امسح البحث.'}</div>`;
  if(d.running)setTimeout(()=>S.cat==='books'&&loadBooks(),20000);
 }catch(e){g.innerHTML='<div class="empty"><b>تعذّر تحميل المكتبة</b>تأكد أن البرنامج ما زال يعمل.</div>'}}
function openBook(id){
 const b=BOOKS.get(id);if(!b)return;S.openId=null;CUR={id:null,full:null,showOrig:false};
 const tname=(BTOPICS.find(t=>t.key===b.topic)||{}).name||'';
 $('#dlgMeta').innerHTML=`<span class="src" style="--c:${BCOL[b.topic]||'var(--acc)'}">${esc(tname)}</span><span>${esc(b.published||b.year)}</span>${b.pages?`<span>${b.pages} صفحة</span>`:''}`;
 $('#dlgBody').innerHTML=`<div class="dossier">BOOK / ${esc(id.toUpperCase())}</div>
  <div class="bookdlg">${coverHtml(b)}<div>
   <h2 id="dlgTitle" style="margin-top:0">${esc(b.title_ar||b.title)}</h2>
   ${b.title_ar&&b.title_ar!==b.title?`<p class="note" dir="auto">${esc(b.title)}</p>`:''}
   <p class="lead">${esc(b.authors||'مؤلف غير معروف')}${b.publisher?'، '+esc(b.publisher):''}</p>
   <div class="dlgtools"><div class="grp">${b.link?`<a class="ibtn primary" href="${esc(b.link)}" target="_blank" rel="noopener">${ico('link')}رابط الكتاب</a>`:''}${b.translated!==1?`<button class="ibtn tr" data-booktr="${esc(b.id)}">${ico('lang')}ترجم</button>`:''}</div></div>
  </div></div>
  ${b.description_ar?`<h4>ملخص الكتاب</h4><p dir="auto" style="font-size:16px;line-height:2">${esc(b.description_ar)}</p>`:''}
  ${b.description&&b.description!==b.description_ar?`<h4>الملخص الأصلي</h4><p dir="auto" style="color:var(--muted)">${esc(b.description)}</p>`:''}
  ${!b.description?'<p class="note">لا يتوفر ملخص لهذا الكتاب.</p>':''}`;
 const dlg=$('#dlg');if(!dlg.open)dlg.showModal()}
async function translateBook(id){
 const btn=document.querySelector(`[data-booktr="${CSS.escape(id)}"]`);if(btn){btn.disabled=true;btn.innerHTML='<span class="spinner" style="padding:0">جارٍ الترجمة…</span>'}
 try{const d=await api('/api/books/translate/'+encodeURIComponent(id),{method:'POST'});if(d.item){BOOKS.set(id,d.item);openBook(id)}
  toast(d.ok?'تمت ترجمة الكتاب':'تعذّرت الترجمة الآن')}catch(e){toast('تعذّرت الترجمة الآن')}}

/* تيليغرام */
let TG_LAST=0,TG_INT=120,TG_LOADED=0;
async function loadTgBoard(){
 try{
  const d=await api('/api/telegram/board');TG_LOADED=Date.now();TG_LAST=d.last;TG_INT=d.interval;
  const okN=d.channels.filter(c=>c.posts.length).length;
  $('#tgcount').innerHTML=`<b>${okN}</b> قناة نشطة من ${d.channels.length}، وآخر 3 منشورات من كل قناة`;
  $('#tgboard').innerHTML=d.channels.map(c=>{c.posts.forEach(p=>ITEMS.set(p.id,p));
   const st=c.ok===1?'ok':(c.ok===0?'bad':'');
   return `<section class="box tgc"><div class="boxh"><span class="av" aria-hidden="true">${esc((c.name_ar||'?').replace(/^ال/,'')[0])}<img src="/icon/${c.platform==='bluesky'?'bs':'tg'}/${esc(c.channel)}" alt="" loading="lazy" onerror="this.remove()"></span><span style="min-width:0"><a href="${esc(c.url||'https://t.me/'+c.channel)}" target="_blank" rel="noopener" style="text-decoration:none">${esc(c.name_ar)}</a><span class="uh">@${esc(c.channel)}</span></span><span class="sp"></span><span class="plat">${c.platform==='bluesky'?'BLUESKY':'TELEGRAM'}</span><span class="st ${st}" title="${st==='ok'?'تعمل':(st==='bad'?'لا تستجيب':'لم تُفحص بعد')}"></span><button class="x" ${c.platform==='bluesky'?'data-bsdel':'data-tgdel'}="${esc(c.channel)}" aria-label="حذف ${esc(c.name_ar)}" title="حذف القناة">×</button></div>
   ${c.posts.length?`<ol>${c.posts.map(p=>`<li><button class="tgp${seen(p.id)?' seen':''}" data-open="${p.id}"><span class="meta"><time>${ago(p.published)}</time>${seen(p.id)?'<span>✓ تمت زيارتها</span>':''}${state(p)}</span><span class="t">${esc(T(p))}</span></button></li>`).join('')}</ol>`:`<div class="err">${c.ok===0?esc(c.error||'القناة لا تستجيب')+'. تأكد من اسمها في تطبيق تيليغرام، أو احذفها.':'بانتظار أول تحديث…'}</div>`}</section>`}).join('')||'<div class="empty"><b>لا توجد قنوات</b>أضف قناة من الحقل أعلاه.</div>';
  tgNext();
 }catch(e){$('#tgboard').innerHTML='<div class="empty"><b>تعذّر الاتصال بالخادم</b>تأكد أن البرنامج ما زال يعمل.</div>'}}
function tgNext(){if(!TG_LAST)return;const left=Math.max(0,Math.round(TG_LAST+TG_INT-Date.now()/1000));$('#tgnext').textContent=left?`التحديث القادم بعد ${left} ثانية`:'يجري التحديث…'}
async function addTg(){
 const ch=$('#tgch').value.trim();if(!ch)return;const bs=$('#tgplat').value==='bluesky';
 try{await api(bs?'/api/bluesky':'/api/telegram',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bs?{handle:ch,name_ar:$('#tgname').value.trim()}:{channel:ch,name_ar:$('#tgname').value.trim()})});
  $('#tgch').value='';$('#tgname').value='';toast('أُضيفت القناة، ويجري جلب منشوراتها');setTimeout(loadTgBoard,5000)}catch(e){toast(e.message)}}
async function loadTweets(){
 try{const d=await api('/api/items?'+new URLSearchParams({cat:'tweets',per:12}));
  d.items.forEach(i=>ITEMS.set(i.id,i));
  const h=d.items.length?d.items.map(i=>`<li><button data-open="${i.id}" class="${seen(i.id)?'seen':''}"><span class="meta"><span class="src" style="--c:#38BDF8">${esc(i.source_ar)}</span><span>${ago(i.published)}</span>${state(i)}</span>${esc(T(i))}</button></li>`).join(''):'<li style="padding:12px 14px" class="count">لا توجد منشورات بعد.</li>';
  $('#tweets').innerHTML=h;$('#dashTg').innerHTML=h}catch(e){}}

/* دليل المراكز */
const CCATS=[['','الكل'],['think_global','أبحاث أجنبية'],['think_arab','أبحاث عربية'],['terror','مكافحة الإرهاب'],['war','حروب ودفاع'],['intel','أمن واستخبارات']];
async function renderCenters(){
 $('#cgrid').innerHTML='<div class="loading spinner">جارٍ تحميل المراكز…</div>';
 try{await loadCenters()}catch(e){$('#cgrid').innerHTML='<div class="empty"><b>تعذّر تحميل المراكز</b>تأكد أن البرنامج ما زال يعمل.</div>';return}
 const regions=['',...new Set(CENTERS.map(c=>c.region))];
 $('#cregion').innerHTML=regions.map(r=>`<button data-cregion="${esc(r)}" class="${CF.region===r?'on':''}">${esc(r||'كل المناطق')}</button>`).join('');
 $('#ccat').innerHTML=CCATS.map(([k,n])=>`<button data-ccat="${k}" class="${CF.cat===k?'on':''}">${n}</button>`).join('');
 renderCenterGrid()}
function centerCard(c){
 const col=CAT[c.cat]?.color||'var(--acc)';
 return `<button class="ccard" data-center="${esc(c.name)}" style="--c:${col}">
  <span class="cdot ${c.ok===1?'ok':(c.ok===0?'bad':'')}" title="${c.ok===1?'المصدر يعمل':(c.ok===0?'المصدر متعطل':'لم يُفحص بعد')}"></span>
  <span class="chead"><span class="mono">${esc(mono(c.name))}${c.site?`<img src="/icon/${esc(c.site.split('/')[0])}" alt="" loading="lazy" onerror="this.remove()">`:''}</span><span><span class="cname">${esc(c.name)}</span><span class="cmeta"><span class="pill">${esc(c.region)}</span><span>${esc(CAT[c.cat]?.name||'')}</span></span></span></span>
  <span class="cstats"><span><b>${c.count}</b>مادة</span><span>${c.last?'آخر نشر '+ago(c.last):'لا مواد بعد'}</span></span>
  <span class="ctags">${c.tags.slice(0,4).map(t=>`<span class="tag">${esc(t.tag)}</span>`).join('')}</span>
 </button>`}
function renderCenterGrid(){
 const qq=CF.q.toLowerCase();
 const l=CENTERS.filter(c=>(!CF.region||c.region===CF.region)&&(!CF.cat||c.cat===CF.cat)&&(!qq||(c.name+' '+c.site).toLowerCase().includes(qq)));
 $('#ccount').textContent=l.length+' مركزاً';
 $('#cgrid').innerHTML=l.length?l.map(centerCard).join(''):'<div class="empty"><b>لا توجد مراكز مطابقة</b>غيّر المنطقة أو النوع أو امسح البحث.</div>'}
function openCenter(name){S.center=name;setView('center')}
function renderCenterHead(){
 const c=CENTERS.find(x=>x.name===S.center)||{name:S.center,region:'',cat:'',site:'',count:0,tags:[]};
 const col=CAT[c.cat]?.color||'var(--acc)';
 document.title=c.name+' | '+TITLE_DEFAULT;
 $('#centerhead').innerHTML=`<button class="back" data-cat="centers">${ico('arrow')}كل المراكز</button>
  <div class="box chero" style="--c:${col}"><span class="mono big" style="--c:${col}">${esc(mono(c.name))}${c.site?`<img src="/icon/${esc(c.site.split('/')[0])}" alt="" onerror="this.remove()">`:''}</span>
   <div class="grow"><h1>${esc(c.name)}</h1><div class="cmeta">${c.region?`<span class="pill">${esc(c.region)}</span>`:''}<span>${esc(CAT[c.cat]?.name||'')}</span>${c.site?`<a href="https://${esc(c.site)}" target="_blank" rel="noopener">${esc(c.site)}</a>`:''}${c.last?`<span>آخر نشر ${ago(c.last)}</span>`:''}</div></div>
   <div class="num"><b>${c.count}</b><span>مادة خلال الشهر</span></div></div>
  ${c.tags.length?`<div class="box ctopics"><div class="tags" style="padding:0"><span class="clbl">مواضيع المركز:</span>
   <button class="tag${!S.tag?' on':''}" data-ctag="">كل المواضيع</button>
   ${c.tags.map(t=>`<button class="tag${S.tag===t.tag?' on':''}" data-ctag="${esc(t.tag)}">${esc(t.tag)} <em>${t.count}</em></button>`).join('')}</div></div>`:''}`}

/* الكلمات المفتاحية */
async function addKw(){
 const w=$('#kwinput').value.trim();if(!w)return;
 try{await api('/api/keywords',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({word:w})});
  $('#kwinput').value='';toast('أُضيفت الكلمة، ويجري البحث عنها الآن');await loadMeta();setTimeout(()=>S.cat==='keywords'&&load(true),6000)}catch(e){toast(e.message)}}

/* الأشرطة */
const TK_SIG={};
async function loadTicker(){
 const d=await api('/api/ticker');
 for(const [key,items] of Object.entries(d)){
  items.forEach(i=>ITEMS.has(i.id)||ITEMS.set(i.id,i));
  const sig=items.map(i=>i.id).join();if(TK_SIG[key]===sig)continue;TK_SIG[key]=sig;
  const run=$('#tk-'+key);if(!run)continue;
  run.innerHTML=items.length?items.map(i=>`<button data-open="${i.id}">${esc(i.title_ar)}<span>${esc(i.source_ar)}، ${ago(i.published)}</span></button>`).join(''):'<span style="margin:0 20px;color:var(--faint)">بانتظار أول العناوين المترجمة…</span>';
  run.style.animationDuration=Math.max(60,(run.scrollWidth+innerWidth)/50)+'s';
 }}

/* التحديث الدوري */
async function poll(){
 try{
  await loadQStats().catch(()=>{});
  loadAlertCount();
  await loadMeta();loadTicker();
  if(S.cat==='dash')return loadDash();
  if(S.cat==='tweets')return loadTgBoard();
  loadTweets();
  if(S.cat==='health')return renderHealth();
  if(S.cat==='bot')return loadBot(true);
  if(S.cat==='map')return loadMap(true);
  if(S.cat==='net')return loadNet();
  if(['ask','sanctions','cases','archive','settings'].includes(S.cat))return;
  if(S.cat==='alerts')return loadAlerts();
  if(['saved','centers','countries','books','writer'].includes(S.cat))return;
  const d=await api('/api/items?'+params(1,50));
  d.items.forEach(i=>{const o=ITEMS.get(i.id);if(o&&o.translated!==1&&i.translated===1){ITEMS.set(i.id,i);const el=document.querySelector(`#feed [data-id="${i.id}"]`);if(el)el.outerHTML=card(i,el.classList.contains('lead'))}});
  if(!S.ids.size&&d.items.length)return load(true);
  const fresh=d.items.filter(i=>!S.ids.has(i.id));
  if(fresh.length){$('#newpill').hidden=false;$('#newpill').textContent=fresh.length+' عنصر جديد، اضغط لعرضها';document.title=`(${fresh.length}) مركز أبو زبيدة`}
 }catch(e){}}

/* نافذة القراءة */
let CUR={id:null,full:null,showOrig:false};
function dlgHtml(it){
 const c=CAT[it.cat]||{color:'var(--acc)',name:''};
 const o=CUR.showOrig;
 $('#dlgMeta').innerHTML=`<span class="src" style="--c:${c.color}">${esc(it.source_ar)}</span><span>${esc(c.name)}</span><span>${esc(fmt(it.published))}</span>`;
 const title=o?it.title:T(it);
 const sum=o?(it.summary||''):(it.summary_ar||it.summary||'');
 const pending=(it.translated!==1||(it.summary&&!it.summary_ar))&&it.lang!=='ar';
 return `<div class="dossier">FILE REF-${it.id.slice(0,8).toUpperCase()} <span class="viewlbl">· ${o?'ORIGINAL / النص الأصلي':'ARABIC / الترجمة العربية'}</span></div>
  <h2 id="dlgTitle" dir="auto">${esc(title)}</h2>
  ${pending&&!o?'<p class="note" id="trnote">لم يُترجم هذا العنصر بعد. اضغط «ترجم» لترجمته الآن.</p>':''}
  ${sum?`<p class="lead" dir="auto">${esc(sum)}</p>`:''}
  <div class="tags" style="padding:0;margin-top:8px">${tagsHtml(it.tags)}</div>
  <div class="dlgtools">
   <div class="grp">
    <button class="ibtn tr" id="trbtn">${ico('lang')}ترجم</button>
    ${it.lang!=='ar'?`<button class="ibtn${o?' on':''}" id="origbtn">${ico('swap')}${o?'عرض الترجمة':'عرض النص الأصلي'}</button>`:''}
   </div><span class="sep"></span>
   <div class="grp">
    <a class="ibtn" href="/print/${it.id}" target="_blank" rel="noopener" title="صفحة جاهزة للحفظ بصيغة PDF فيها الترجمة والنص الأصلي">${ico('pdf')}حفظ PDF</a>
   </div><span class="sep"></span>
   <div class="grp">
    ${it.link?`<a class="ibtn primary" href="/go/${it.id}" target="_blank" rel="noopener">${ico('link')}فتح في موقعه</a>`:''}
    <button class="ibtn" data-save="${it.id}">${ico('bookmark')}${isSaved(it.id)?'محفوظ':'حفظ'}</button>
    <button class="ibtn" data-copy="${it.id}">${ico('copy')}نسخ</button>
    ${CENTER_SET.has(it.source_ar)?`<button class="ibtn" data-center="${esc(it.source_ar)}">${ico('centers')}مواد المركز</button>`:''}
   </div><span class="sep"></span>
   <div class="grp">
    <button class="ibtn" data-tocase="${it.id}">${ico('centers')}ملف قضية</button>
    <button class="ibtn" data-arch="${it.id}" title="يحفظ نسخة من النص على جهازك ونسخة عامة في أرشيف الإنترنت">${ico('bookmark')}أرشف</button>
   </div>
  </div>
  ${it.edits?'<div id="edsec"><h4>تعديلات العنوان</h4><div class="spinner">…</div></div>':''}
  ${it.cluster&&(it.nsrc||1)>1?'<div id="vsec"><h4>نقلته أيضاً مصادر أخرى</h4><div class="spinner">…</div></div>':''}
  ${it.kind==='video'&&ytId(it.link)?`<div class="vidwrap"><iframe src="https://www.youtube.com/embed/${ytId(it.link)}" title="${esc(T(it))}" allow="accelerometer; encrypted-media; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>`:''}
  ${it.kind==='tweet'||it.kind==='video'?'':'<div id="full"></div>'}`}
function ytId(u){const m=(u||'').match(/[?&]v=([\w-]{6,})/);return m?m[1]:''}
async function loadVSec(it){if(!$('#vsec'))return;
 try{const d=await api('/api/cluster/'+encodeURIComponent(it.cluster));if(CUR.id!==it.id||!$('#vsec'))return;
  const others=d.items.filter(x=>x.id!==it.id);others.forEach(x=>ITEMS.has(x.id)||ITEMS.set(x.id,x));
  $('#vsec').innerHTML=`<h4>نقلته أيضاً ${others.length} ${others.length>2?'مصادر أخرى':'مصدر آخر'}</h4><ul class="vlist">${others.map(x=>`<li><button data-open="${x.id}"><span class="meta"><span class="src" style="--c:${CAT[x.cat]?.color||'var(--acc)'}">${esc(x.source_ar)}</span><span>${ago(x.published)}</span></span>${esc(T(x))}</button></li>`).join('')}</ul>`}catch(e){}}
function renderDlg(){const it=ITEMS.get(CUR.id)||savedList().find(x=>x.id===CUR.id);if(!it)return;$('#dlgBody').innerHTML=dlgHtml(it);renderFull()}
function renderFull(){
 const box=$('#full');if(!box)return;const d=CUR.full;const id=CUR.id;
 if(!d){box.innerHTML='<div class="spinner">جارٍ جلب النص الكامل وترجمته…</div>';return}
 if(!d.ok){box.innerHTML=`<h4>النص الكامل</h4><p class="err">${esc(d.error)}</p><div class="dlgacts"><a class="ibtn primary" href="/go/${id}" target="_blank" rel="noopener">${ico('link')}فتح المقال في موقعه</a><button class="ibtn" id="retryfull">أعد المحاولة</button></div>`;return}
 let host='';try{host=new URL(d.link).hostname}catch(e){}
 const o=CUR.showOrig;const paras=o?(d.orig||d.paragraphs):d.paragraphs;
 box.innerHTML=`<h4>${o?'النص الكامل الأصلي':'النص الكامل مترجماً'}</h4>`
  +(d.partial?'<p class="note">تعذّر استخراج المقال كاملاً (قد يكون خلف اشتراك)، وهذا ما أمكن جلبه:</p>':'')
  +(!o&&d.untranslated?`<p class="note">${d.untranslated} فقرة لم تُترجم بعد. اضغط «ترجم» لإعادة المحاولة.</p>`:'')
  +`<div ${o?'dir="auto" lang="en"':''}>`+paras.map(p=>`<p dir="auto">${esc(p)}</p>`).join('')+'</div>'
  +`<p class="note">مصدر النص: ${esc(d.via||'')}، الموقع: <a href="/go/${id}" target="_blank" rel="noopener">${esc(host)}</a></p>`}
async function openItem(id){
 const it=ITEMS.get(id)||savedList().find(x=>x.id===id);if(!it)return;
 ITEMS.set(id,it);S.openId=id;CUR={id,full:null,showOrig:false};
 renderDlg();
 const dlg=$('#dlg');if(!dlg.open)dlg.showModal();
 markVisited(id);
 if((it.translated!==1||(it.summary&&!it.summary_ar))&&it.lang!=='ar')translateTitle(id,false);
 if(it.kind!=='tweet'&&it.kind!=='video')loadFull(id,false);
 loadVSec(it);if(it.edits)loadEdits(it)}
async function loadEdits(it){try{const d=await api('/api/edits/'+it.id);if(CUR.id!==it.id||!$('#edsec'))return;
 $('#edsec').innerHTML='<h4>تعديلات العنوان بعد النشر</h4><ul class="edlist">'+d.items.map(c=>`<li><span class="wstat">${fmt(c.changed)}</span><br><del dir="auto">${esc(c.old_title)}</del><br><ins dir="auto">${esc(c.new_title)}</ins>${c.old_ar?`<br><span class="note">الترجمة السابقة: ${esc(c.old_ar)}</span>`:''}</li>`).join('')+'</ul>'}catch(e){}}
async function translateTitle(id,force){
 try{const d=await api('/api/translate/'+id+(force?'?force=1':''),{method:'POST'});
  if(CUR.id!==id)return d;
  if(d.item){ITEMS.set(id,d.item);renderDlg();
   const el=document.querySelector(`#feed [data-id="${id}"]`);if(el)el.outerHTML=card(d.item,el.classList.contains('lead'))}
  return d}catch(e){return {ok:false}}}
async function loadFull(id,force){
 try{const d=await api('/api/article/'+id+(force?'?force=1':''));if(CUR.id!==id)return d;
  if(d.link&&ITEMS.get(id))ITEMS.get(id).link=d.link;
  CUR.full=d;renderFull();return d}
 catch(e){if(CUR.id===id){CUR.full={ok:false,error:e.message||'تعذّر جلب النص الكامل.'};renderFull()}return {ok:false}}}
async function translateNow(){
 const id=CUR.id;if(!id)return;const it=ITEMS.get(id);
 const btn=$('#trbtn');if(btn){btn.disabled=true;btn.innerHTML='<span class="spinner" style="padding:0">جارٍ الترجمة…</span>'}
 CUR.showOrig=false;
 const tasks=[translateTitle(id,true)];
 if(it&&it.kind!=='tweet'){CUR.full=null;renderFull();tasks.push(loadFull(id,true))}
 const [t,f]=await Promise.all(tasks);
 if(CUR.id!==id)return;
 renderDlg();
 const okT=(ITEMS.get(id)||{}).translated===1||(ITEMS.get(id)||{}).lang==='ar';
 const okF=!f||(f.ok&&!f.untranslated);
 if(okT&&okF)return toast('تمت الترجمة');
 try{await loadMeta()}catch(e){}
 const err=META?.tr_stats?.last_error||'';
 toast('تعذّرت ترجمة بعض الأجزاء'+(err?': '+err.slice(0,90):'')+'. راجع «صحة المصادر والترجمة»')}
function toggleSave(id){
 const it=ITEMS.get(id);let l=savedList();
 if(l.some(i=>i.id===id)){l=l.filter(i=>i.id!==id);toast('أُزيل من المحفوظات')}else if(it){l.unshift(it);toast('حُفظ في المحفوظات');api('/api/archive/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:'محفوظات'})}).catch(()=>{})}
 setSaved(l);const s=isSaved(id);
 document.querySelectorAll(`.acts [data-save="${id}"]`).forEach(b=>{b.classList.toggle('saved',s);b.title=s?'محفوظ':'حفظ'});
 document.querySelectorAll(`.dlgacts [data-save="${id}"]`).forEach(b=>b.innerHTML=ico('bookmark')+(s?'محفوظ':'حفظ'));
 if(META)renderNav();if(S.cat==='saved')renderSaved()}
async function copyItem(id){const it=ITEMS.get(id)||savedList().find(x=>x.id===id);if(!it)return;
 if((it.link||'').includes('news.google.com')){try{const d=await api('/api/resolve/'+id);it.link=d.link}catch(e){}}
 const t=[T(it),it.summary_ar,'المصدر: '+it.source_ar,it.link].filter(Boolean).join('\n');
 navigator.clipboard.writeText(t).then(()=>toast('نُسخ النص والرابط'),()=>toast('تعذّر النسخ'))}

/* الأحداث */
document.addEventListener('click',e=>{
 const t=e.target.closest('button,a');if(!t)return;
 const ds=t.dataset;
 const gm=(t.getAttribute('href')||'').match(/^\/(?:go|print)\/([0-9a-f]+)/);if(gm)markVisited(gm[1]);
 if(ds.cat){e.preventDefault();$('#dlg').open&&$('#dlg').close();return setView(ds.cat)}
 if(ds.center!==undefined){$('#dlg').open&&$('#dlg').close();return openCenter(ds.center)}
 if(ds.open)return openItem(ds.open);
 if(ds.save)return toggleSave(ds.save);
 if(ds.copy)return copyItem(ds.copy);
 if(ds.skin)return applySkin(ds.skin);
 if(ds.bsdel){if(!confirm('حذف هذا الحساب من المتابعة؟'))return;api('/api/bluesky/'+encodeURIComponent(ds.bsdel),{method:'DELETE'}).then(()=>{toast('حُذف الحساب');loadTgBoard()});return}
 if(ds.tgdel){if(!confirm('حذف هذه القناة من المتابعة؟'))return;api('/api/telegram/'+encodeURIComponent(ds.tgdel),{method:'DELETE'}).then(()=>{toast('حُذفت القناة');loadTgBoard()});return}
 if(ds.kwdel){api('/api/keywords/'+encodeURIComponent(ds.kwdel),{method:'DELETE'}).then(()=>{toast('حُذفت الكلمة');loadMeta()});return}
 if(ds.qf!==undefined){QF=ds.qf;QITEMS=[];return loadQualBox()}
 if(ds.qgo!==undefined)return showQ(+ds.qgo);
 if(ds.cluster){openCluster(ds.cluster);return}
 if(ds.nset!==undefined){return}
 if(ds.edits)return openItem(ds.edits);
 if(ds.arch){t.disabled=true;api('/api/archive/'+ds.arch,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:'يدوي'})}).then(()=>toast('أُرشف المقال، وتُرسل نسخة إلى أرشيف الإنترنت')).catch(()=>toast('تعذّرت الأرشفة'));return}
 if(ds.tocase)return pickCase(ds.tocase);
 if(ds.pickcase){addToCase(ds.pickcase,PICKITEM);return}
 if(ds.sgroup!==undefined){SANCGROUP=ds.sgroup;SANCPAGE=1;return loadSanc()}
 if(ds.spg){SANCPAGE=+ds.spg;$('#sanclist').scrollIntoView({block:'start'});return loadSanc()}
 if(ds.stab){SANCMODE=ds.stab;SANCPAGE=1;document.querySelectorAll('#sanctabs button').forEach(b=>b.classList.toggle('on',b===t));return loadSanc()}
 if(ds.atab){ATAB=ds.atab;APAGE=1;document.querySelectorAll('[data-atab]').forEach(b=>b.classList.toggle('on',b===t));return loadArch()}
 if(ds.ah!==undefined){AH=+ds.ah;APAGE=1;document.querySelectorAll('#archhours button').forEach(b=>b.classList.toggle('on',b===t));return loadArch()}
 if(ds.apg){APAGE=+ds.apg;$('#archbox').scrollIntoView({block:'start'});return loadArch()}
 if(ds.adel){api('/api/archive/'+ds.adel,{method:'DELETE'}).then(()=>{toast('حُذفت من الأرشيف');loadArch()});return}
 if(ds.edel){api('/api/edits/'+ds.edel,{method:'DELETE'}).then(()=>loadArch());return}
 if(ds.archopen)return openArchived(ds.archopen);
 if(ds.case)return openCase(ds.case);
 if(ds.cidel){if(!confirm('إزالة هذه المادة من القضية؟'))return;api(`/api/cases/${CASE}/${ds.cidel}`,{method:'DELETE'}).then(()=>openCase(CASE));return}
 if(ds.cnote){const v=document.querySelector(`[data-noteof="${ds.cnote}"]`).value;api(`/api/cases/${CASE}/note`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:ds.cnote,note:v})}).then(()=>toast('حُفظت الملاحظة'));return}
 if(ds.askex){$('#askq').value=ds.askex;return askGo()}
 if(ds.wtab){document.querySelectorAll('[data-wtab]').forEach(b=>b.classList.toggle('on',b===t));$('#wlogview').hidden=ds.wtab!=='log';$('#wwriteview').hidden=ds.wtab==='log';if(ds.wtab==='log')renderWLog();return}
 if(ds.wlopen){const a=(window._WARTS||[]).find(x=>x.id===ds.wlopen);if(a){WBODY=a.body;WSAVED=a.id;$('#wtopic').value=a.topic||'';wRender(true);['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=false);document.querySelector('[data-wtab="write"]').click();window.scrollTo({top:0})}return}
 if(ds.wlcopy){const a=(window._WARTS||[]).find(x=>x.id===ds.wlcopy);if(a)navigator.clipboard.writeText(a.body).then(()=>toast('نُسخ المقال'));return}
 if(ds.wlpdf){const a=(window._WARTS||[]).find(x=>x.id===ds.wlpdf);if(a){const keep=WBODY;WBODY=a.body;wPdf();WBODY=keep}return}
 if(ds.mh){MAPH=+ds.mh;document.querySelectorAll('#maphours button').forEach(b=>b.classList.toggle('on',b===t));return loadMap()}
 if(ds.alh){ALH=+ds.alh;document.querySelectorAll('#alhours button').forEach(b=>b.classList.toggle('on',b===t));return loadAlerts()}
 if(ds.alcountry!==undefined)return openCountry(ds.alcountry);
 if(ds.altopic!==undefined){setView('all');S.tag=ds.altopic;renderActiveTag();if(META)renderTags();return load(true)}
 if(ds.wart){const a=(window._WARTS||[]).find(x=>x.id===ds.wart);if(a){WBODY=a.body;WSAVED=a.id;$('#wtopic').value=a.topic||'';wRender(true);['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=false);window.scrollTo({top:0})}return}
 if(ds.wdel){if(!confirm('حذف هذا المقال نهائياً؟'))return;api('/api/articles/'+ds.wdel,{method:'DELETE'}).then(()=>{toast('حُذف المقال');loadArticles()});return}
 if(ds.qev!==undefined){S.event=ds.qev;renderQualFilter();return load(true)}
 if(ds.ctag!==undefined){S.tag=ds.ctag;S.cat==='country'?renderCountryHead():renderCenterHead();load(true);return}
 if(ds.country!==undefined){$('#dlg').open&&$('#dlg').close();return openCountry(ds.country)}
 if(ds.ctyregion!==undefined){CTYF.region=ds.ctyregion;document.querySelectorAll('#ctyregion button').forEach(b=>b.classList.toggle('on',b===t));return renderCtyGrid()}
 if(ds.btopic!==undefined){BF.topic=ds.btopic;document.querySelectorAll('#btopic button').forEach(b=>b.classList.toggle('on',b===t));return loadBooks()}
 if(ds.blang!==undefined){BF.lang=ds.blang;document.querySelectorAll('#blang button').forEach(b=>b.classList.toggle('on',b===t));return loadBooks()}
 if(ds.book)return openBook(ds.book);
 if(ds.booktr)return translateBook(ds.booktr);
 if(ds.tag){$('#dlg').open&&$('#dlg').close();if(['saved','health','centers','dash','tweets','countries','books','writer','bot','map','alerts','ask','sanctions','cases','archive','net','settings'].includes(S.cat))setView('all');S.tag=ds.tag;renderActiveTag();if(S.cat==='center')renderCenterHead();if(S.cat==='country')renderCountryHead();if(META)renderTags();load(true);return}
 if(ds.hours!==undefined){S.hours=+ds.hours;document.querySelectorAll('#hours button').forEach(b=>b.classList.toggle('on',b===t));if(S.cat!=='saved')load(true);return}
 if(ds.cregion!==undefined){CF.region=ds.cregion;document.querySelectorAll('#cregion button').forEach(b=>b.classList.toggle('on',b===t));return renderCenterGrid()}
 if(ds.ccat!==undefined){CF.cat=ds.ccat;document.querySelectorAll('#ccat button').forEach(b=>b.classList.toggle('on',b===t));return renderCenterGrid()}
 if(t.id==='trtest')return trTest();
 if(t.id==='updgo'||t.id==='updgo2'){toast('يجري إعادة التشغيل…');api('/api/update/restart',{method:'POST'}).catch(()=>{});setTimeout(()=>location.reload(),6000);return}
 if(t.id==='updlater'){sessionStorage.setItem('upd_later','1');$('#updbar').hidden=true;return}
 if(t.id==='updsave'){api('/api/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({repo:$('#updrepo').value,branch:$('#updbranch').value})}).then(()=>{toast('حُفظ');loadUpdBox()});return}
 if(t.id==='updcheck'){t.disabled=true;t.textContent='جارٍ الفحص…';api('/api/update/check',{method:'POST'}).then(d=>{toast(d.state.error||d.state.state||'تم');loadUpdBox();loadMeta().then(updBanner)}).catch(()=>toast('تعذّر الفحص'));return}
 if(t.id==='wallbtn'||t.id==='wallgo')return wallStart();
 if(t.id==='wallexit')return wallStop();
 if(t.id==='cmdbtn')return cmdOpen();
 if(t.id==='askgo')return askGo();
 if(t.id==='askcopy')return navigator.clipboard.writeText(ASKTXT).then(()=>toast('نُسخت الإجابة'));
 if(t.id==='archclear'){const lbl=AH?`أرشيف آخر ${AH==24?'24 ساعة':AH==168?'أسبوع':'شهر'}`:'الأرشيف كله';
  if(!confirm('حذف الأرشيف نهائياً؟\nاضغط «موافق» لحذف كل المواد المؤرشفة.'))return;
  api('/api/archive',{method:'DELETE'}).then(()=>{toast('حُذف الأرشيف');APAGE=1;loadArch()});return}
 if(t.id==='sancref'){api('/api/sanctions/refresh',{method:'POST'}).then(()=>{toast('يجري تنزيل القوائم، قد يستغرق دقيقة');setTimeout(loadSanc,1500)});return}
 if(t.id==='casenew'){const tt=prompt('عنوان القضية الجديدة:');if(!tt)return;api('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:tt})}).then(d=>{CASE=d.id;loadCases()});return}
 if(t.id==='casedel'){if(!confirm('حذف القضية وكل ما فيها من ملاحظات؟'))return;api('/api/cases/'+CASE,{method:'DELETE'}).then(()=>{CASE=null;loadCases()});return}
 if(t.id==='casesave'){api('/api/cases/'+CASE,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:$('#ctitle').value,descr:$('#cdescr').value})}).then(()=>{toast('حُفظ');loadCases()});return}
 if(t.id==='pickclose'){$('#casepick')?.remove();return}
 if(t.id==='picknew'){const tt=$('#picktitle').value.trim();if(!tt)return;api('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:tt,item_id:PICKITEM})}).then(()=>{$('#casepick')?.remove();toast('أُنشئت القضية وأُضيفت المادة إليها')});return}
 if(t.id==='wlogdelall'){if(!confirm('حذف كل المقالات المكتوبة نهائياً؟'))return;api('/api/articles',{method:'DELETE'}).then(()=>{toast('حُذفت كل المقالات');loadArticles().then(renderWLog)});return}
 if(t.id==='lansave'){api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lan:$('#lanon').checked,pin:$('#lanpin').value})}).then(()=>{toast('حُفظ. أعد تشغيل البرنامج ليُطبَّق');renderHealth()}).catch(e=>toast(e.message));return}
 if(ds.wprov)return wcfg({provider:ds.wprov});
 if(ds.wpull){api('/api/writer/ollama/pull',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:ds.wpull})}).then(()=>{toast('بدأ التنزيل، قد يستغرق عدة دقائق');setTimeout(loadWriter,1500)}).catch(e=>toast(e.message));return}
 if(t.id==='wcheck')return loadWriter().then(()=>toast(WCFG.ollama.running?'Ollama يعمل':'لم يُعثر على Ollama؛ تأكد أنه مثبت ومشغّل'));
 if(t.id==='wkeyedit'){WCFG.claude.has_key=false;return renderWKey()}
 if(t.id==='wgemedit'){WCFG.gemini.has_key=false;return renderWKey()}
 if(t.id==='wkeysave')return wcfg({key:$('#wkeyin').value.trim()},'حُفظ المفتاح');
 if(t.id==='wgemsave'){toast('جارٍ التحقق من المفتاح…');return wcfg({gemini_key:$('#wgemkey').value.trim()},'حُفظ مفتاح Gemini')}
 if(t.id==='hall'){HONLY=false;return drawHealth()}
 if(t.id==='hbad'){HONLY=true;return drawHealth()}
 if(t.id==='hcopy')return copyBroken();
 if(t.id==='trbtn')return translateNow();
 if(t.id==='origbtn'){CUR.showOrig=!CUR.showOrig;return renderDlg()}
 if(t.id==='retryfull'){const id=CUR.id;if(id){CUR.full=null;renderFull();loadFull(id,true)}return}
 if(t.id==='cleartag'){S.tag='';renderActiveTag();if(META)renderTags();load(true)}
});
$('#source').onchange=e=>{S.source=e.target.value;load(true)};
$('#more').onclick=()=>{S.page++;load(false)};
$('#newpill').onclick=()=>{window.scrollTo({top:0});load(true);$('#newpill').hidden=true;document.title=TITLE_DEFAULT};
$('#dedupe').classList.toggle('on',DEDUPE);
$('#dedupe').onclick=()=>{DEDUPE=!DEDUPE;lsSet('rased_dedupe',DEDUPE?'1':'0');$('#dedupe').classList.toggle('on',DEDUPE);if(S.cat!=='saved')load(true)};
$('#hideseen').onclick=()=>{S.hideSeen=!S.hideSeen;$('#hideseen').classList.toggle('on',S.hideSeen);S.cat==='saved'?renderSaved():load(true)};
$('#density').onclick=()=>{S.compact=!S.compact;lsSet('rased_compact',S.compact?'1':'0');$('#density').classList.toggle('on',S.compact);S.cat==='saved'?renderSaved():load(true)};
$('#kwadd').onclick=addKw;$('#kwinput').onkeydown=e=>{if(e.key==='Enter')addKw()};
$('#tgadd').onclick=addTg;$('#tgplat').onchange=e=>{$('#tgch').placeholder=e.target.value==='bluesky'?'اسم الحساب أو رابطه، مثل: apnews.com أو name.bsky.social':'اسم القناة أو رابطها، مثل: t.me/AJArabic'};$('#tgch').onkeydown=e=>{if(e.key==='Enter')addTg()};
$('#tgrefresh').onclick=async()=>{await api('/api/telegram/refresh',{method:'POST'});toast('يجري تحديث كل القنوات');setTimeout(loadTgBoard,8000)};
$('#cq').oninput=e=>{CF.q=e.target.value.trim();renderCenterGrid()};
$('#ctyq').oninput=e=>{CTYF.q=e.target.value.trim();renderCtyGrid()};
let bqt;$('#bq').oninput=e=>{clearTimeout(bqt);bqt=setTimeout(()=>{BF.q=e.target.value.trim();loadBooks()},400)};
$('#brefresh').onclick=async()=>{await api('/api/books/refresh',{method:'POST'});toast('يجري البحث عن الكتب الجديدة، وستظهر خلال دقائق');setTimeout(loadBooks,15000)};
$('#dlgClose').onclick=()=>$('#dlg').close();
$('#dlg').addEventListener('click',e=>{if(e.target.id==='dlg')$('#dlg').close()});
$('#dlg').addEventListener('close',()=>{S.openId=null;CUR.id=null});
/* البحث داخل القسم الحالي */
let QALL=false,QBASE='',QSETTING=false;
const QLOCAL={countries:'#ctyq',books:'#bq',archive:'#archq',sanctions:'#sancq',writer:'#wlogq'};
const QGLOBAL=['dash','health','tweets','bot','map','alerts','ask','cases','net','settings'];
function scopeLabel(){const c=S.cat;
 if(c==='center')return S.center;if(c==='country')return S.country;if(c==='centers'||c==='research')return 'المراكز';
 if(QALL||QGLOBAL.includes(c)||c==='all')return '';return EXTRA[c]||CAT[c]?.name||''}
function updScope(){const l=scopeLabel(),b=$('#qscope');$('#q').closest('.search').classList.toggle('scoped',!!l);
 if(!l){b.hidden=true;$('#q').placeholder='ابحث في الأخبار والدراسات والمصادر…';return}
 b.hidden=false;b.className='qscope';b.textContent='في: '+l;$('#q').placeholder='ابحث في '+l+'…'}
function runSearch(v){
 const c=S.cat;S.q=v;
 if(QALL||QGLOBAL.includes(c)){QSETTING=true;setView('all');QSETTING=false;return}
 if(QLOCAL[c]){const el=$(QLOCAL[c]);el.value=v;el.dispatchEvent(new Event('input'));if(c==='writer'&&v)document.querySelector('[data-wtab="log"]')?.click();return}
 if(c==='centers'){if(v){QSETTING=true;setView('research');QSETTING=false}return}
 if(c==='research'&&!v){setView('centers');return}
 if(c==='saved')return renderSaved();
 load(true)}
let qt;$('#q').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>runSearch(e.target.value.trim()),400)};
$('#qscope').onclick=()=>{QALL=true;updScope();if($('#q').value.trim())runSearch($('#q').value.trim());$('#q').focus()};
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&document.activeElement?.id==='qslide'){openItem(document.activeElement.dataset.open);return}if(e.key==='/'&&!['INPUT','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('#q').focus()}});
$('#refresh').onclick=async()=>{const d=await api('/api/refresh',{method:'POST'});toast(d.running?'دورة جلب جارية بالفعل':'بدأ تحديث جميع المصادر');$('#refresh').classList.add('spin');setTimeout(poll,4000)};
function applySkin(t){if(!['neon','ops','gold','light'].includes(t))t='neon';document.documentElement.dataset.theme=t;document.querySelectorAll('[data-skin]').forEach(b=>b.classList.toggle('on',b.dataset.skin===t));lsSet('rased_skin',t)}
function applyTk(on){$('#tickers').classList.toggle('off',!on);$('#tkTxt').textContent=on?'إخفاء الأشرطة':'إظهار الأشرطة';$('#tkToggle').setAttribute('aria-pressed',on);lsSet('rased_tk',on?'1':'0')}
$('#tkToggle').onclick=()=>applyTk($('#tickers').classList.contains('off'));

if('serviceWorker' in navigator&&(location.protocol==='https:'||['localhost','127.0.0.1'].includes(location.hostname)))navigator.serviceWorker.register('/sw.js').catch(()=>{});
(async()=>{
 if(!lsGet('rased_skin_v2',''))lsSet('rased_skin','neon'),lsSet('rased_skin_v2','1');
 applySkin(lsGet('rased_skin','neon'));applyTk(lsGet('rased_tk','1')!=='0');
 S.compact=lsGet('rased_compact','0')==='1';$('#density').classList.toggle('on',S.compact);
 clocks();setInterval(clocks,1000);
 try{await loadCenters()}catch(e){}
 try{await loadCty()}catch(e){}
 try{await loadQStats()}catch(e){}
 try{const nt=await api('/api/net');NETBAD=nt.countries.filter(c=>c.level!=='normal').length}catch(e){}
 try{BOTON=(await api('/api/bot')).cfg.enabled}catch(e){}
 loadAlertCount();
 try{const b=await api('/api/books');BOOKS_N=b.topics.reduce((a,t)=>a+t.count,0)}catch(e){}
 try{await loadMeta()}catch(e){}
 setView('dash');loadTicker().catch(()=>{});
 setInterval(poll,45000);
 setInterval(()=>{if(S.cat==='tweets'){tgNext();if(TG_LAST&&Date.now()/1000>TG_LAST+TG_INT+15&&Date.now()-TG_LOADED>20000)loadTgBoard()}},1000);
 setInterval(()=>document.querySelectorAll('#feed time').forEach(t=>{const it=ITEMS.get(t.closest('[data-id]')?.dataset.id);if(it)t.textContent=ago(it.published)}),60000);
})();
