(function() {
  'use strict';

  const $ = (s, p) => (p || document).querySelector(s);
  const $$ = (s, p) => Array.from((p || document).querySelectorAll(s));

  let diagrams = [];
  let currentIdx = -1;
  let currentData = null;
  let selectedElements = new Set();
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let zoomLevel = 1;

  function toast(msg, type) {
    const container = $('#toasts');
    const el = document.createElement('div');
    el.className = `toast ${type || ''}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }

  async function loadDiagrams() {
    try {
      const resp = await fetch('/api/diagrams');
      if (resp.ok) {
        diagrams = await resp.json();
        renderDiagramList();
        if (diagrams.length && currentIdx < 0) {
          selectDiagram(0);
        }
      }
    } catch (err) {
      toast('加载图表列表失败', 'error');
    }
  }

  function renderDiagramList() {
    const list = $('#diagramList');
    if (!diagrams.length) {
      list.innerHTML = `<div class="empty-state" style="padding:20px;">
        <div class="empty-state-icon">📭</div>
        <div class="empty-state-title">暂无图表</div>
      </div>`;
      return;
    }
    list.innerHTML = diagrams.map((d, i) => `
      <div class="sidebar-item ${i === currentIdx ? 'active' : ''}" onclick="window.App.selectDiagram(${i})">
        <span>📄 ${d.name}</span>
        ${d.annotation_count ? `<span class="sidebar-item-badge">${d.annotation_count}</span>` : ''}
      </div>
    `).join('');
  }

  async function selectDiagram(idx) {
    currentIdx = idx;
    selectedElements.clear();
    updatePanel();
    renderDiagramList();
    updateNav();

    const area = $('#diagramArea');
    area.innerHTML = '<div class="loading"><div class="spinner"></div>加载中...</div>';

    try {
      const resp = await fetch(`/api/diagrams/${diagrams[idx].name}/svg`);
      if (resp.ok) {
        currentData = await resp.json();
        renderDiagram(currentData);
      } else {
        area.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠</div><div class="empty-state-title">加载失败</div></div>';
      }
    } catch (err) {
      toast('加载图表失败', 'error');
    }
  }

  function renderDiagram(data) {
    const area = $('#diagramArea');
    const wrapper = document.createElement('div');
    wrapper.className = 'diagram-preview';
    wrapper.id = 'svgWrapper';

    const sanitized = sanitizeSVG(data.svg);
    wrapper.innerHTML = sanitized;

    const svg = wrapper.querySelector('svg');
    if (svg) {
      svg.style.maxWidth = 'none';
      svg.style.height = 'auto';

      const annotatedIds = new Set((data.annotations || []).map(a => a.element_id));

      data.elements.forEach(elem => {
        const el = svg.querySelector(`[id="${CSS.escape(elem.id)}"]`);
        if (el) {
          el.classList.add('svg-element');
          if (annotatedIds.has(elem.id)) {
            el.classList.add('annotated');
          }
          el.addEventListener('click', (e) => handleElementClick(e, el, elem.id));
        }
      });

      svg.addEventListener('mousedown', handleMouseDown);
      svg.addEventListener('mousemove', handleMouseMove);
      svg.addEventListener('mouseup', handleMouseUp);
      document.addEventListener('keydown', handleKeyDown);
    }

    area.innerHTML = '';
    area.appendChild(wrapper);
    zoomLevel = 1;
    applyZoom();
    updatePanel();
  }

  function sanitizeSVG(svgText) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgText, 'image/svg+xml');
    const errorNode = doc.querySelector('parsererror');
    if (errorNode) return svgText;

    const remove = ['script', 'foreignObject'];
    remove.forEach(tag => {
      doc.querySelectorAll(tag).forEach(el => el.remove());
    });

    doc.querySelectorAll('*').forEach(el => {
      Array.from(el.attributes).forEach(attr => {
        const name = attr.name.toLowerCase();
        if (name.startsWith('on') || (name === 'href' && attr.value.startsWith('javascript:'))) {
          el.removeAttribute(name);
        }
      });
    });

    return new XMLSerializer().serializeToString(doc.documentElement);
  }

  function handleElementClick(e, el, elemId) {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      if (selectedElements.has(elemId)) {
        selectedElements.delete(elemId);
        el.classList.remove('selected');
      } else {
        selectedElements.add(elemId);
        el.classList.add('selected');
      }
    } else {
      $$('.svg-element.selected').forEach(s => s.classList.remove('selected'));
      selectedElements.clear();
      selectedElements.add(elemId);
      el.classList.add('selected');
    }
    updatePanel();
  }

  function handleMouseDown(e) {
    if (e.target === e.currentTarget || e.target.tagName === 'svg') {
      isDragging = true;
      dragStart = { x: e.clientX, y: e.clientY };
      const band = $('#rubberBand');
      band.style.display = 'block';
      band.style.left = dragStart.x + 'px';
      band.style.top = dragStart.y + 'px';
      band.style.width = '0px';
      band.style.height = '0px';
    }
  }

  function handleMouseMove(e) {
    if (!isDragging) return;
    const band = $('#rubberBand');
    const w = e.clientX - dragStart.x;
    const h = e.clientY - dragStart.y;
    band.style.left = (w > 0 ? dragStart.x : e.clientX) + 'px';
    band.style.top = (h > 0 ? dragStart.y : e.clientY) + 'px';
    band.style.width = Math.abs(w) + 'px';
    band.style.height = Math.abs(h) + 'px';
  }

  function handleMouseUp(e) {
    if (!isDragging) return;
    isDragging = false;
    const band = $('#rubberBand');
    band.style.display = 'none';
    if (Math.abs(e.clientX - dragStart.x) < 10 && Math.abs(e.clientY - dragStart.y) < 10) return;

    const bandRect = {
      left: Math.min(dragStart.x, e.clientX),
      top: Math.min(dragStart.y, e.clientY),
      right: Math.max(dragStart.x, e.clientX),
      bottom: Math.max(dragStart.y, e.clientY)
    };

    $$('.svg-element').forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.left < bandRect.right && rect.right > bandRect.left &&
          rect.top < bandRect.bottom && rect.bottom > bandRect.top) {
        if (!e.ctrlKey && !e.metaKey) {
          el.classList.add('selected');
          const elemId = el.getAttribute('id');
          if (elemId) selectedElements.add(elemId);
        }
      }
    });
    updatePanel();
  }

  function handleKeyDown(e) {
    if (e.key === 'Escape') {
      selectedElements.clear();
      $$('.svg-element.selected').forEach(s => s.classList.remove('selected'));
      updatePanel();
    }
  }

  function updatePanel() {
    const panel = $('#annotPanel');

    const annotationBlock = [];
    if (selectedElements.size > 0) {
      annotationBlock.push(`<div style="margin-bottom:14px;">
        <label style="font-size:11px;color:var(--text-muted);">已选中 ${selectedElements.size} 个元素</label>
        <div style="margin-top:4px;font-size:11px;color:var(--text-muted);word-break:break-all;">${[...selectedElements].join(', ')}</div>
      </div>`);
      annotationBlock.push(`<div style="margin-bottom:14px;">
        <label style="font-size:11px;color:var(--text-muted);">添加批注</label>
        <textarea id="annotText" rows="3" placeholder="在此输入批注内容..." style="margin-top:4px;"></textarea>
      </div>`);
      annotationBlock.push(`<button class="btn btn-primary btn-sm" style="width:100%;" onclick="window.App.submitAnnotations()">提交批注</button>`);
    } else {
      annotationBlock.push(`<div class="empty-state" style="padding:12px;">
        <div class="empty-state-icon">👆</div>
        <div class="empty-state-title">选择元素批注</div>
        <div class="empty-state-desc">点击图表中的元素开始批注</div>
      </div>`);
    }

    annotationBlock.push(`<div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border);">`);
    annotationBlock.push(`<label style="font-size:11px;color:var(--text-muted);">批注历史 (${(currentData?.annotations || []).length})</label>`);

    (currentData?.annotations || []).slice().reverse().forEach(ann => {
      annotationBlock.push(`
        <div class="annotation-card">
          <div class="annotation-card-header">
            <span class="annotation-card-id">${ann.element_id || '全局'}</span>
            <button class="annotation-card-remove" onclick="window.App.deleteAnnotation('${ann.id}')" title="删除">✕</button>
          </div>
          <div class="annotation-card-text">${escapeHtml(ann.text)}</div>
          <div class="annotation-card-time">${ann.created_at || ''}</div>
        </div>
      `);
    });
    annotationBlock.push(`</div>`);

    panel.innerHTML = annotationBlock.join('');
  }

  async function submitAnnotations() {
    const textarea = $('#annotText');
    if (!textarea || !textarea.value.trim()) {
      toast('请输入批注内容', 'error');
      return;
    }
    const text = textarea.value.trim();

    for (const elemId of selectedElements) {
      try {
        await fetch(`/api/diagrams/${currentData.name}/annotations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ element_id: elemId, text })
        });
      } catch (e) {}
    }

    if (selectedElements.size === 0) {
      try {
        await fetch(`/api/diagrams/${currentData.name}/annotations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ element_id: '', text })
        });
      } catch (e) {}
    }

    toast(`批注已提交: "${text.substring(0, 40)}..."`, 'success');
    toast('AI 正在读取批注并准备修改...', 'success');

    selectedElements.clear();
    $$('.svg-element.selected').forEach(s => s.classList.remove('selected'));

    const resp = await fetch(`/api/diagrams/${currentData.name}/svg`);
    if (resp.ok) currentData = await resp.json();

    renderDiagramList();
    updatePanel();
    $('#annotText').value = '';
  }

  async function deleteAnnotation(annId) {
    try {
      await fetch(`/api/diagrams/${currentData.name}/annotations/${annId}`, { method: 'DELETE' });
      const resp = await fetch(`/api/diagrams/${currentData.name}/svg`);
      if (resp.ok) currentData = await resp.json();
      renderDiagramList();
      updatePanel();
      toast('批注已删除', 'success');
    } catch (e) {
      toast('删除失败', 'error');
    }
  }

  function updateNav() {
    $('#diagramNav').textContent = `${currentIdx + 1} / ${diagrams.length}`;
    $('#btnPrev').disabled = currentIdx <= 0;
    $('#btnNext').disabled = currentIdx >= diagrams.length - 1;
  }

  function applyZoom() {
    const scale = Math.round(zoomLevel * 100);
    $('#zoomLevel').textContent = scale + '%';
    const svg = document.querySelector('#svgWrapper svg');
    if (svg) {
      const baseW = parseFloat(svg.getAttribute('width') || svg.viewBox?.baseVal?.width || 960);
      const baseH = parseFloat(svg.getAttribute('height') || svg.viewBox?.baseVal?.height || 640);
      svg.style.width = (baseW * zoomLevel) + 'px';
      svg.style.height = (baseH * zoomLevel) + 'px';
      svg.style.maxWidth = 'none';
      svg.style.transform = '';
    }
  }

  function zoomIn() {
    zoomLevel = Math.min(zoomLevel * 1.3, 5);
    applyZoom();
  }

  function zoomOut() {
    zoomLevel = Math.max(zoomLevel / 1.3, 0.2);
    applyZoom();
  }

  function zoomReset() {
    zoomLevel = 1;
    applyZoom();
  }

  async function prevDiagram() {
    if (currentIdx > 0) await selectDiagram(currentIdx - 1);
  }

  async function nextDiagram() {
    if (currentIdx < diagrams.length - 1) await selectDiagram(currentIdx + 1);
  }

  async function confirmAndExit() {
    if (!confirm('确认所有图表？\n\n确认后 AI 将读取批注并修改图表，随后继续撰写文档。')) return;

    try {
      const resp = await fetch('/api/diagrams');
      if (resp.ok) {
        const all = await resp.json();
        const unannotated = all.filter(d => d.annotation_count === 0);
        if (unannotated.length > 0) {
          const ok = confirm(`还有 ${unannotated.length} 张图表未批注 (${unannotated.map(d=>d.name).join(', ')})。\n\n确定要继续吗？`);
          if (!ok) return;
        }
      }
    } catch (e) {}

    try {
      await fetch('/api/checkpoint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phase: 'phase4', diagrams_confirmed: true })
      });
    } catch(e) {}

    const bar = $('#btnSave');
    bar.textContent = '已确认 ✓';
    bar.style.background = '#16a34a';
    bar.style.borderColor = '#16a34a';
    bar.style.color = '#fff';
    bar.disabled = true;
    toast('图表已确认，AI 将继续处理', 'success');
  }

  function closePreview() {
    if (confirm('关闭预览？')) {
      fetch('/api/shutdown', { method: 'POST' }).catch(() => {});
    }
  }

  async function exitPreview() { closePreview(); }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft' && !e.target.closest('input,textarea')) prevDiagram();
    if (e.key === 'ArrowRight' && !e.target.closest('input,textarea')) nextDiagram();
  });

  // Wheel zoom on diagram area
  document.getElementById('diagramArea').addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      if (e.deltaY < 0) zoomIn();
      else zoomOut();
    }
  }, { passive: false });

  window.App = {
    selectDiagram, submitAnnotations, deleteAnnotation,
    prevDiagram, nextDiagram,
    confirmAndExit, exitPreview, closePreview,
    zoomIn, zoomOut, zoomReset
  };

  loadDiagrams();
})();
