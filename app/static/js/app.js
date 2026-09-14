const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

let selectedPdfs = [];
let selectedImage = null;
let tradingStyles = [];
let selectedStyle = "hlz";

// Elements
const pdfDrop = $('#pdfDrop');
const pdfInput = $('#pdfInput');
const pdfList = $('#pdfList');
const uploadPdfBtn = $('#uploadPdfBtn');
const pdfProgress = $('#pdfProgress');
const pdfProgressBar = $('#pdfProgressBar');
const pdfProgressText = $('#pdfProgressText');

const imageDrop = $('#imageDrop');
const imageInput = $('#imageInput');
const imagePreviewWrap = $('#imagePreviewWrap');
const imagePreview = $('#imagePreview');
const removeImageBtn = $('#removeImageBtn');
const analyzeBtn = $('#analyzeBtn');
const analyzeProgress = $('#analyzeProgress');
const analyzeBar = $('#analyzeBar');
const analyzeStep = $('#analyzeStep');
const resultsWrap = $('#resultsWrap');
const emptyState = $('#emptyState');

// Init
document.addEventListener('DOMContentLoaded', () => {
  loadStatus();
  loadStyles();
  setupEvents();
  setupTabs();
});

function setupEvents() {
  // PDF drag & drop
  pdfDrop.addEventListener('click', () => pdfInput.click());
  pdfDrop.addEventListener('dragover', e => { e.preventDefault(); pdfDrop.classList.add('border-violet-500'); });
  pdfDrop.addEventListener('dragleave', () => pdfDrop.classList.remove('border-violet-500'));
  pdfDrop.addEventListener('drop', e => {
    e.preventDefault();
    pdfDrop.classList.remove('border-violet-500');
    handlePdfFiles(e.dataTransfer.files);
  });
  pdfInput.addEventListener('change', e => handlePdfFiles(e.target.files));
  uploadPdfBtn.addEventListener('click', uploadPdfs);
  $('#clearBtn').addEventListener('click', clearKnowledge);

  // Image drag & drop
  imageDrop.addEventListener('click', () => imageInput.click());
  imageDrop.addEventListener('dragover', e => { e.preventDefault(); imageDrop.classList.add('border-emerald-500'); });
  imageDrop.addEventListener('dragleave', () => imageDrop.classList.remove('border-emerald-500'));
  imageDrop.addEventListener('drop', e => {
    e.preventDefault();
    imageDrop.classList.remove('border-emerald-500');
    if (e.dataTransfer.files[0]) handleImageFile(e.dataTransfer.files[0]);
  });
  imageInput.addEventListener('change', e => { if (e.target.files[0]) handleImageFile(e.target.files[0]); });
  removeImageBtn.addEventListener('click', clearImage);
  analyzeBtn.addEventListener('click', analyzeImage);

  // Style select
  const styleSelect = $('#styleSelect');
  if (styleSelect) {
    styleSelect.addEventListener('change', e => {
      selectedStyle = e.target.value;
      updateStyleDesc(selectedStyle);
    });
  }
}

function setupTabs() {
  $$('.tabBtn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      $$('.tabBtn').forEach(b => { b.classList.remove('active'); b.classList.add('text-[#8b9bb0]','border-transparent'); b.classList.remove('border-violet-500','text-white'); });
      btn.classList.add('active'); btn.classList.remove('text-[#8b9bb0]','border-transparent');
      $$('.tabContent').forEach(c => c.classList.add('hidden'));
      $(`#tab-${tab}`).classList.remove('hidden');
    });
  });
}

async function loadStyles() {
  try {
    const res = await fetch('/api/styles');
    const data = await res.json();
    tradingStyles = data.styles || [];
    
    const grid = $('#styleGrid');
    const select = $('#styleSelect');
    if (!grid) return;

    grid.innerHTML = tradingStyles.map(s => {
      const isHLZ = s.key === 'hlz';
      const isSelected = s.key === selectedStyle;
      return `
        <button data-style="${s.key}" class="styleBtn text-left p-3 rounded-xl border transition flex items-center gap-3 ${isSelected ? 'bg-gradient-to-r '+s.color+' border-transparent text-white' : 'bg-[#0f141c] border-[#1e2a3a] hover:border-[#2a3a52] text-[#8b9bb0] hover:text-white'}">
          <div class="w-8 h-8 rounded-lg ${isSelected ? 'bg-white/20' : 'bg-[#1a2332]'} flex items-center justify-center flex-shrink-0">
            <i class="fas ${s.icon} text-sm"></i>
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-xs ${isSelected ? 'text-white' : 'text-white'}">${s.name} ${isHLZ ? '🔥' : ''}</div>
            <div class="text-[11px] truncate ${isSelected ? 'text-white/80' : 'text-[#5a6b80]'}">${s.description}</div>
          </div>
          ${isSelected ? '<i class="fas fa-check text-xs"></i>' : ''}
        </button>
      `;
    }).join('');

    // Add click handlers
    $$('.styleBtn').forEach(btn => {
      btn.addEventListener('click', () => {
        selectedStyle = btn.dataset.style;
        if (select) select.value = selectedStyle;
        // Re-render grid
        loadStyles();
        updateStyleDesc(selectedStyle);
      });
    });

    // Populate select if empty
    if (select && select.options.length <= 1) {
      select.innerHTML = tradingStyles.map(s => `<option value="${s.key}" ${s.key===selectedStyle?'selected':''}>${s.name}</option>`).join('');
    }

    updateStyleDesc(selectedStyle);
  } catch (e) {
    console.error('Failed to load styles', e);
  }
}

function updateStyleDesc(key) {
  const descEl = $('#styleDesc');
  if (!descEl) return;
  const style = tradingStyles.find(s => s.key === key);
  if (!style) return;
  descEl.classList.remove('hidden');
  descEl.innerHTML = `
    <div class="flex items-center gap-2 mb-1"><i class="fas ${style.icon}"></i><b class="text-white">${style.name}</b></div>
    <p class="text-[11px]">${style.description}</p>
    ${style.key==='hlz' ? '<p class="mt-2 text-[11px] text-orange-200">💡 HLZ = Structure + Liquidité + OB + FVG + Premium/Discount. Uploade tes PDFs découpés par concept pour que le RAG cite exactement ta méthode HLZ.</p>' : ''}
  `;
}

async function loadStatus() {
  try {
    const res = await fetch('/api/knowledge/status');
    const data = await res.json();
    $('#docCount').textContent = data.total_documents;
    $('#chunkCount').textContent = data.total_chunks;
    $('#embeddingMode').textContent = data.embedding_mode;
    
    const providers = data.llm_providers;
    setProviderDot('openai', providers.openai);
    setProviderDot('claude', providers.anthropic);
    setProviderDot('gemini', providers.google);
    
    const healthRes = await fetch('/api/health');
    const health = await healthRes.json();
    $('#healthText').textContent = `API ${health.status} • ${data.embedding_mode} • Style: ${selectedStyle.toUpperCase()}`;
  } catch (e) {
    $('#healthText').textContent = 'Hors ligne';
  }
}

function setProviderDot(name, active) {
  const el = $(`#${name}Status`);
  if (!el) return;
  el.className = `w-2 h-2 rounded-full ${active ? 'bg-emerald-400' : 'bg-gray-600'}`;
}

function handlePdfFiles(files) {
  selectedPdfs = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
  if (selectedPdfs.length === 0) return;
  
  pdfList.classList.remove('hidden');
  pdfList.innerHTML = selectedPdfs.map(f => `
    <div class="flex items-center gap-2 text-xs p-2 rounded-lg bg-[#0f141c] border border-[#1e2a3a]">
      <i class="fas fa-file-pdf text-violet-400"></i>
      <span class="flex-1 truncate">${f.name}</span>
      <span class="text-[#5a6b80] mono">${(f.size/1024/1024).toFixed(2)} MB</span>
    </div>
  `).join('');
  uploadPdfBtn.disabled = false;
}

async function uploadPdfs() {
  if (selectedPdfs.length === 0) return;
  uploadPdfBtn.disabled = true;
  pdfProgress.classList.remove('hidden');
  pdfProgressBar.style.width = '30%';
  pdfProgressText.textContent = 'Extraction du texte...';

  const fd = new FormData();
  selectedPdfs.forEach(f => fd.append('files', f));

  try {
    pdfProgressBar.style.width = '60%';
    pdfProgressText.textContent = 'Chunking & embeddings...';
    const res = await fetch('/api/upload-pdfs', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erreur upload');

    pdfProgressBar.style.width = '100%';
    pdfProgressText.textContent = data.message;
    
    setTimeout(() => {
      pdfProgress.classList.add('hidden');
      pdfList.classList.add('hidden');
      selectedPdfs = [];
      pdfInput.value = '';
      loadStatus();
      toast(`✅ ${data.chunks_created} chunks indexés (${selectedStyle.toUpperCase()})`, 'success');
    }, 800);
  } catch (e) {
    toast(`❌ ${e.message}`, 'error');
    pdfProgress.classList.add('hidden');
  } finally {
    uploadPdfBtn.disabled = false;
  }
}

function handleImageFile(file) {
  if (!file.type.startsWith('image/')) {
    toast('Format image invalide', 'error');
    return;
  }
  selectedImage = file;
  const url = URL.createObjectURL(file);
  imagePreview.src = url;
  imagePreviewWrap.classList.remove('hidden');
  imageDrop.classList.add('hidden');
  emptyState.classList.add('hidden');
}

function clearImage() {
  selectedImage = null;
  imagePreview.src = '';
  imagePreviewWrap.classList.add('hidden');
  imageDrop.classList.remove('hidden');
  resultsWrap.classList.add('hidden');
  emptyState.classList.remove('hidden');
  imageInput.value = '';
}

async function analyzeImage() {
  if (!selectedImage) return;
  
  analyzeBtn.disabled = true;
  analyzeProgress.classList.remove('hidden');
  resultsWrap.classList.add('hidden');
  analyzeBar.style.width = '20%';
  analyzeStep.textContent = `Analyse vision LLM [${selectedStyle.toUpperCase()}]...`;

  const fd = new FormData();
  fd.append('file', selectedImage);
  fd.append('top_k', $('#topKSelect').value);
  fd.append('style', selectedStyle);

  // Simulate progress
  let progress = 20;
  const interval = setInterval(() => {
    progress = Math.min(progress + Math.random()*15, 90);
    analyzeBar.style.width = `${progress}%`;
    if (progress < 40) analyzeStep.textContent = `Vision LLM ${selectedStyle.toUpperCase()} → description du graphique...`;
    else if (progress < 70) analyzeStep.textContent = `Recherche RAG dans tes cours ${selectedStyle.toUpperCase()}...`;
    else analyzeStep.textContent = `Synthèse finale HLZ/SMC → prédiction...`;
  }, 600);

  try {
    const res = await fetch('/api/analyze', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erreur analyse');

    clearInterval(interval);
    analyzeBar.style.width = '100%';
    analyzeStep.textContent = 'Analyse terminée !';
    
    setTimeout(() => {
      analyzeProgress.classList.add('hidden');
      displayResults(data);
      analyzeBtn.disabled = false;
    }, 500);
  } catch (e) {
    clearInterval(interval);
    analyzeProgress.classList.add('hidden');
    analyzeBtn.disabled = false;
    toast(`❌ ${e.message}`, 'error');
  }
}

function displayResults(data) {
  resultsWrap.classList.remove('hidden');
  emptyState.classList.add('hidden');
  
  // Header
  $('#patternTitle').textContent = data.pattern_principal || 'Pattern détecté';
  const conf = Math.round((data.confiance||0)*100);
  $('#confidenceBadge').textContent = `${conf}% confiance`;
  $('#confidenceBadge').className = `px-2.5 py-1 rounded-full text-xs font-bold border ${conf>70 ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : conf>40 ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}`;
  
  const trend = data.vision?.trend || 'indecis';
  $('#trendBadge').textContent = `${trend} • ${data.vision?.style_used?.toUpperCase() || selectedStyle.toUpperCase()}`;
  const trendColor = trend==='haussier' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : trend==='baissier' ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-[#1a2332] border-[#243044]';
  $('#trendBadge').className = `px-2.5 py-1 rounded-full text-xs font-medium border ${trendColor}`;
  
  $('#modelUsed').textContent = `Modèle: ${data.model_utilise} • Vision: ${data.vision?.provider||'local'} • Style: ${data.vision?.style_used||selectedStyle} • ${data.sources_utilisees?.length||0} sources`;
  
  const predShort = (data.prediction||'').slice(0,80);
  $('#predictionShort').textContent = predShort;

  // Tabs content
  $('#analyseText').textContent = data.analyse_technique || 'Pas d\'analyse';
  $('#methodoText').textContent = data.explication_methodologie || 'Pas de méthodologie';
  $('#recoText').textContent = data.recommandation || '-';
  $('#predictionText').textContent = data.prediction || '-';
  $('#timeframeText').textContent = data.timeframe_suggere || '-';
  $('#risqueText').textContent = data.risques || '-';

  // Niveaux
  const niveaux = data.niveaux_cles || {};
  $('#niveauxGrid').innerHTML = Object.entries(niveaux).map(([k,v]) => `
    <div class="rounded-xl bg-[#0f141c] border border-[#1e2a3a] p-4">
      <div class="text-xs uppercase tracking-widest text-[#8b9bb0] mb-2">${k.replace('_',' ')}</div>
      <div class="space-y-1">
        ${(Array.isArray(v)?v:[v]).map(item => `<div class="text-sm flex gap-2"><span class="text-violet-400">•</span><span>${item}</span></div>`).join('')}
      </div>
    </div>
  `).join('');

  // RAG
  const ragDiv = $('#ragChunks');
  if (data.rag_chunks && data.rag_chunks.length>0) {
    ragDiv.innerHTML = data.rag_chunks.map((chunk,i) => `
      <div class="rounded-xl bg-[#0f141c] border border-[#1e2a3a] p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-bold text-violet-400">Source ${i+1}: ${chunk.source} ${chunk.page?`p.${chunk.page}`:''}</span>
          <span class="text-[10px] mono px-2 py-0.5 rounded bg-[#1a2332]">score ${(chunk.score||0).toFixed(3)}</span>
        </div>
        <p class="text-xs leading-relaxed text-[#a8b8d0]">${chunk.content.slice(0,600)}${chunk.content.length>600?'...':''}</p>
      </div>
    `).join('');
  } else {
    ragDiv.innerHTML = `<div class="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200">Aucun contexte de cours trouvé. Uploadez vos PDFs HLZ (BOS, OB, FVG, Liquidités...) pour que l'IA cite exactement ta méthode.</div>`;
  }

  // Vision
  $('#visionTrend').textContent = `${data.vision?.trend || '-'} (${data.vision?.style_used||''})`;
  $('#visionConf').textContent = `${Math.round((data.vision?.confidence||0)*100)}%`;
  $('#visionDesc').textContent = data.vision?.description || '-';
  $('#visionPatterns').innerHTML = (data.vision?.patterns_detected||[]).map(p => `<span class="px-2 py-1 rounded-full bg-violet-500/20 text-violet-300 text-[11px] border border-violet-500/20">${p}</span>`).join('') || '<span class="text-xs text-[#5a6b80]">Aucun</span>';
  $('#visionIndicators').innerHTML = (data.vision?.indicators||[]).map(p => `<span class="px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] border border-emerald-500/20">${p}</span>`).join('') || '<span class="text-xs text-[#5a6b80]">Aucun</span>';

  // Scroll to results
  resultsWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function clearKnowledge() {
  if (!confirm('Effacer toute la base de connaissances ?')) return;
  try {
    const res = await fetch('/api/knowledge/clear', { method: 'DELETE' });
    const data = await res.json();
    toast('Base effacée', 'success');
    loadStatus();
  } catch (e) {
    toast('Erreur suppression', 'error');
  }
}

function toast(msg, type='info') {
  const div = document.createElement('div');
  div.className = `fixed bottom-6 right-6 px-4 py-3 rounded-xl text-sm font-medium shadow-2xl z-50 transition-all ${type==='success'?'bg-emerald-600 text-white': type==='error'?'bg-red-600 text-white':'bg-[#1a2332] border border-[#243044] text-white'}`;
  div.textContent = msg;
  document.body.appendChild(div);
  setTimeout(() => { div.style.opacity='0'; div.style.transform='translateY(10px)'; setTimeout(()=>div.remove(),300); }, 3000);
}
