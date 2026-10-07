'use strict';
const methods=['查資料學','請老師或助教協助','與同學討論','講解給別人聽','自己重做練習','看影片學','其他方式'];
const resources=['課程教材／習題','圖書館／資料庫／館員','授課老師／助教','教學發展中心學習輔導','課程學習社群','學伴／同學','其他資源'];
const examples=['查課本與圖書館資料，找出 debit、credit 的意思。','帶著自己寫的分錄與同學討論，指出彼此判斷不同的地方。','遮住答案重做，再向同學講解為什麼 Cash 記在借方。'];
const $=id=>document.getElementById(id);
const msg=s=>$('status').textContent=s;
let files=[[],[],[]],db,dirty=false;
for(let i=0;i<3;i++){
 const section=document.createElement('section');section.className='record';
 section.innerHTML=`<h2>學習方式 ${i+1}</h2><p class="example">填寫參考：${examples[i]}（你可以選自己的方法）</p><div class="grid"><div><label for="method${i}">① 我用什麼方法？</label><select id="method${i}" name="method${i}"><option value="">請選擇</option>${methods.map(x=>`<option>${x}</option>`).join('')}</select><input id="other${i}" name="other${i}" aria-label="自訂學習方式 ${i+1}" placeholder="選其他方式時，請寫方法名稱" hidden></div><div><label for="resource${i}">使用什麼資源？</label><select id="resource${i}" name="resource${i}"><option value="">請選擇</option>${resources.map(x=>`<option>${x}</option>`).join('')}</select><input name="detail${i}" aria-label="資源名稱 ${i+1}" placeholder="例：教材頁碼、同學姓名或服務名稱"></div></div><label for="action${i}">② 我實際做了什麼？</label><textarea id="action${i}" name="action${i}" placeholder="寫出你做的步驟，不只寫「看書」或「討論」。"></textarea><label for="learn${i}">③ 我學會什麼／改正什麼？</label><textarea id="learn${i}" name="learn${i}" placeholder="例：我原本把收入寫在借方，現在知道收入增加要記貸方。"></textarea><label for="evidence${i}">④ 附上佐證</label><textarea id="evidence${i}" name="evidence${i}" placeholder="貼上可供老師查看的分享連結，或描述下方附件如何證明你的學習。"></textarea><label for="file${i}">加入照片、截圖或 PDF</label><input type="file" id="file${i}" accept="image/png,image/jpeg,image/webp,application/pdf" multiple><p class="note">每檔最多 5 MB，全部附件合計最多 15 MB。圖片或 PDF 可存入本機備份。</p><ul class="attachments" id="attachments${i}"></ul>`;
 $('records').append(section);
 $('method'+i).addEventListener('change',()=>{$('other'+i).hidden=$('method'+i).value!=='其他方式';});
 $('file'+i).addEventListener('change',async e=>{
  try{
   for(const f of e.target.files){
    if(!['image/png','image/jpeg','image/webp','application/pdf'].includes(f.type))throw Error('附件只接受 PNG、JPEG、WebP 圖片或 PDF。');
    if(f.size>5*1024*1024||files.flat().reduce((n,x)=>n+x.size,0)+f.size>15*1024*1024)throw Error('附件超過大小上限，請縮小檔案後再加入。');
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(f);});
    files[i].push({name:f.name,type:f.type,size:f.size,data});
   }
   dirty=true;renderFiles(i);update();msg('附件已加入，請儲存進度。');
  }catch(err){dirty=true;renderFiles(i);update();msg(err.message);}finally{e.target.value='';}
 });
}
function renderFiles(i){
 const ul=$('attachments'+i);ul.replaceChildren();
 files[i].forEach((f,j)=>{
  const li=document.createElement('li'),a=document.createElement('a');a.textContent=f.name;a.href=f.data;a.download=f.name;li.append(a);
  if(f.type.startsWith('image/')){const im=document.createElement('img');im.src=f.data;im.alt='佐證：'+f.name;li.append(im);}
  const button=document.createElement('button');button.type='button';button.textContent='移除';button.setAttribute('aria-label','移除 '+f.name);button.onclick=()=>{files[i].splice(j,1);dirty=true;renderFiles(i);update();msg('附件已移除，請儲存進度。');};li.append(button);ul.append(li);
 });
}
function capture(){return {version:1,fields:Object.fromEntries(new FormData($('book'))),files};}
function apply(data){$('book').reset();for(const [k,v] of Object.entries(data.fields)){const el=$('book').elements.namedItem(k);if(el)el.value=v;}files=data.files;for(let i=0;i<3;i++){$('other'+i).hidden=$('method'+i).value!=='其他方式';renderFiles(i);}dirty=false;update();}
function update(){
 let n=0;const names=[],complete=new Set();
 for(let i=0;i<3;i++){
  const method=$('method'+i).value==='其他方式'?$('other'+i).value.trim():$('method'+i).value;
  if(method)names.push(method);
  const resource=$('resource'+i).value;
  const detail=$('book').elements.namedItem('detail'+i).value.trim();
  if(method&&resource&&(resource!=='其他資源'||detail)&&$('action'+i).value.trim()&&$('learn'+i).value.trim()&&($('evidence'+i).value.trim()||files[i].length))complete.add(method);
 }
 n=complete.size;
 $('progress').textContent=`已完成 ${n} / 3 種學習方式`+(new Set(names).size<names.length?'，請改選三種不同的學習方式。':n===3?'，三種學習方式已記錄。':'，每張請留下行動、收穫與佐證，其他資源請填名稱。');
}
function transaction(value,remove=false){return new Promise((resolve,reject)=>{const tx=db.transaction('records','readwrite');const store=tx.objectStore('records');if(remove)store.delete('current');else store.put(value,'current');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('儲存中止'));});}
async function save(){if(!db)throw Error('無法使用本機儲存，請匯出備份保存資料。');await transaction(capture());dirty=false;msg('已儲存在這台裝置，尚未傳送給老師。');}
$('book').addEventListener('input',()=>{dirty=true;update();msg('內容已修改，請儲存進度。');});
$('book').addEventListener('submit',e=>e.preventDefault());
$('save').onclick=async()=>{try{await save();}catch(e){msg('儲存失敗：'+e.message);}};
$('export').onclick=()=>{
 const blob=new Blob([JSON.stringify(capture())],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='學習存摺_備份.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);msg('已匯出備份檔（含附件），請妥善保存並依老師規定繳交。');
};
function validate(data){
 if(data.version!==1||!data.fields||typeof data.fields!=='object'||Array.isArray(data.fields)||!Array.isArray(data.files)||data.files.length!==3)throw Error('不是本版存摺的備份檔。');
 if(Object.values(data.fields).some(x=>typeof x!=='string'||x.length>100000))throw Error('備份欄位格式不正確。');
 let total=0;
 for(const group of data.files){if(!Array.isArray(group))throw Error('附件格式不正確');for(const f of group){if(!f||typeof f.name!=='string'||!['image/png','image/jpeg','image/webp','application/pdf'].includes(f.type)||typeof f.data!=='string'||!f.data.startsWith('data:'+f.type+';base64,')||!/^data:[^;]+;base64,[A-Za-z0-9+/]*={0,2}$/.test(f.data))throw Error('附件格式不正確');const size=atob(f.data.split(',')[1]).length;if(size>5*1024*1024)throw Error('附件太大');f.size=size;total+=size;}}
 if(total>15*1024*1024)throw Error('備份附件合計太大');
}
$('import').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>23*1024*1024)throw Error('備份檔太大');const data=JSON.parse(await f.text());validate(data);if(!confirm('匯入會取代目前這個簡化版的內容，是否繼續？'))return;if(!db)throw Error('本機儲存無法使用，請先匯出目前內容。');await transaction(data);apply(data);msg('已匯入並儲存備份，尚未傳送給老師。');}catch(err){msg('匯入失敗：'+err.message);}finally{e.target.value='';}};
$('clear').onclick=async()=>{if(!confirm('清除本版的所有紀錄與附件？舊版紀錄會保留。'))return;try{if(!db)throw Error('本機儲存無法使用');await transaction(null,true);apply({fields:{},files:[[],[],[]]});msg('已清除本版紀錄，舊版紀錄仍保留。');}catch(e){msg('清除失敗：'+e.message);}};
$('print').onclick=()=>{document.querySelectorAll('textarea').forEach(el=>{el.style.height='auto';el.style.height=el.scrollHeight+'px';});window.print();};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
const request=indexedDB.open('peipei-learning-simple',1);
request.onupgradeneeded=()=>request.result.createObjectStore('records');
request.onerror=()=>msg('本機儲存無法使用，請用匯出備份保存資料。');
request.onsuccess=()=>{db=request.result;const read=db.transaction('records').objectStore('records').get('current');read.onsuccess=()=>{try{if(read.result){validate(read.result);apply(read.result);msg('已載入這台裝置上的紀錄。');}else{update();msg('選三種方法開始記錄，完成後請儲存進度。');}}catch(e){msg('舊資料無法載入：'+e.message+'，未刪除原資料。');}};read.onerror=()=>msg('讀取失敗，請保留備份並重新載入。');};
