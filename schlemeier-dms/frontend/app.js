const state={documents:[],selected:null};
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function loadDocuments(){
  const params=new URLSearchParams();
  if($('statusFilter').value)params.set('status',$('statusFilter').value);
  if($('entityFilter').value)params.set('entity',$('entityFilter').value);
  if($('search').value.trim())params.set('q',$('search').value.trim());
  const res=await fetch('/api/documents?'+params.toString());
  state.documents=await res.json();
  $('count').textContent=state.documents.length;
  const review=state.documents.filter(d=>d.status==='Pruefen').length;
  $('stats').textContent=`${review} zu prüfen · ${state.documents.length-review} abgelegt`;
  renderList();
  if(state.selected){
    const updated=state.documents.find(d=>d.id===state.selected.id);
    if(updated)selectDocument(updated);else clearDetail();
  }
}

function renderList(){
  $('documentList').innerHTML=state.documents.length?state.documents.map(d=>{
    const preview=d.is_pdf?`<object data="${esc(d.file_url)}#toolbar=0&navpanes=0&page=1" type="application/pdf"></object>`:`<img src="${esc(d.file_url)}" alt="">`;
    return `<article class="card ${state.selected?.id===d.id?'selected':''}" data-id="${esc(d.id)}">
      <div class="thumb">${preview}</div>
      <div><div class="card-title">${esc(d.title||d.original_filename)}</div>
      <div class="card-meta">${esc(d.original_filename)}</div>
      <div class="chips"><span class="chip ${d.status==='Pruefen'?'review':'done'}">${d.status==='Pruefen'?'Prüfen':d.status}</span><span class="chip">${esc(d.entity)}</span><span class="chip">${esc(d.document_type)}</span></div></div>
    </article>`;
  }).join(''):'<div class="muted">Keine passenden Belege.</div>';
  document.querySelectorAll('.card').forEach(el=>el.addEventListener('click',()=>selectDocument(state.documents.find(d=>d.id===el.dataset.id))));
}

function fillForm(d){
  $('documentType').value=d.document_type||'Sonstiges';
  $('entity').value=d.entity||'Unklar';
  $('privatePerson').value=d.private_person||'Unklar';
  $('correspondent').value=d.correspondent||'Unklar';
  $('documentDate').value=d.document_date||'';
  $('invoiceNumber').value=d.invoice_number||'';
  $('grossAmount').value=d.gross_amount||'';
  $('title').value=d.title||'';
  $('targetPath').textContent=d.target_path||'Wird beim Speichern aus der Auswahl berechnet.';
  togglePrivate();
}

function selectDocument(d){
  state.selected=d;
  renderList();
  $('emptyState').classList.add('hidden');
  $('detailContent').classList.remove('hidden');
  $('detailTitle').textContent=d.title||d.original_filename;
  $('detailFilename').textContent=d.original_filename;
  $('statusBadge').textContent=d.status==='Pruefen'?'Prüfen':d.status;
  $('statusBadge').className='badge '+(d.status==='Pruefen'?'review':'done');
  $('confidence').textContent=d.confidence?`Finora-Sicherheit: ${Math.round(d.confidence*100)} %`:'';
  $('preview').innerHTML=d.is_pdf?`<object data="${esc(d.file_url)}#toolbar=0" type="application/pdf"></object>`:`<img src="${esc(d.file_url)}" alt="Dokumentvorschau">`;
  if(d.status==='Pruefen'){
    $('decisionForm').classList.remove('hidden');$('archivedInfo').classList.add('hidden');
    fillForm(d);
    const s=d.finora_suggestion;
    if(s){$('suggestionBox').classList.remove('hidden');$('suggestionBox').innerHTML=`<strong>Finora-Vorschlag:</strong> ${esc(s.document_type)} · ${esc(s.entity)}${s.private_person?' / '+esc(s.private_person):''} · ${esc(s.correspondent)}${s.learning_note?`<br><span class="muted">${esc(s.learning_note)}</span>`:''}`;}
    else $('suggestionBox').classList.add('hidden');
  }else{
    $('decisionForm').classList.add('hidden');$('suggestionBox').classList.add('hidden');$('archivedInfo').classList.remove('hidden');
    $('archivedInfo').innerHTML=`<strong>Abgelegt</strong><br>${esc(d.target_path||'Kein Zielpfad gespeichert')}<br><span class="muted">${esc(d.entity)} · ${esc(d.document_type)} · ${esc(d.correspondent)}</span>`;
  }
}

function clearDetail(){state.selected=null;$('detailContent').classList.add('hidden');$('emptyState').classList.remove('hidden');renderList();}
function togglePrivate(){$('privateWrap').classList.toggle('hidden',$('entity').value!=='Privat');}
function toast(msg,error=false){$('toast').textContent=msg;$('toast').className='toast'+(error?' error':'');setTimeout(()=>$('toast').classList.add('hidden'),3200);}

$('decisionForm').addEventListener('submit',async e=>{
  e.preventDefault(); if(!state.selected)return;
  const payload={document_type:$('documentType').value,entity:$('entity').value,private_person:$('entity').value==='Privat'?$('privatePerson').value:'',correspondent:$('correspondent').value.trim()||'Unklar',document_date:$('documentDate').value.trim(),invoice_number:$('invoiceNumber').value.trim(),gross_amount:$('grossAmount').value.trim(),title:$('title').value.trim()||'Dokument'};
  const res=await fetch(`/api/documents/${encodeURIComponent(state.selected.id)}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(!res.ok){const data=await res.json().catch(()=>({}));toast(data.detail||'Ablage fehlgeschlagen',true);return;}
  const data=await res.json();toast(`Abgelegt: ${data.target_path}`);state.selected=null;await loadDocuments();clearDetail();
});

$('entity').addEventListener('change',togglePrivate);
$('refreshBtn').addEventListener('click',loadDocuments);
$('statusFilter').addEventListener('change',loadDocuments);
$('entityFilter').addEventListener('change',loadDocuments);
let timer;$('search').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(loadDocuments,250);});
loadDocuments().catch(()=>toast('DMS-Backend ist nicht erreichbar.',true));
