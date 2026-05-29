(function() {
  'use strict';

  const $ = (s, p) => (p || document).querySelector(s);
  const $$ = (s, p) => Array.from((p || document).querySelectorAll(s));

  let outlineData = [];
  let selectedNode = null;
  let dirty = false;
  let originalData = null;

  function toast(msg, type) {
    const container = $('#toasts');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }

  function numberize(node, parentNum) {
    if (node.level === 1) {
      const nums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
        '十一', '十二', '十三', '十四', '十五'];
      node.number = nums[node._idx + 1] || String(node._idx + 1);
      node.number += '、';
    } else if (node.level === 2 && parentNum) {
      node.number = `${parentNum}.${node._idx + 1}`;
    } else if (node.level === 3 && parentNum) {
      node.number = `(${node._idx + 1})`;
    } else {
      node.number = '';
    }
    (node.children || []).forEach((child, i) => {
      child._idx = i;
      numberize(child, node.level === 1 ? node._idx + 1 : (parentNum || ''));
    });
  }

  function renumberAll() {
    outlineData.forEach((node, i) => {
      node._idx = i;
      numberize(node, null);
    });
  }

  function renderOutline() {
    const area = $('#contentArea');
    area.innerHTML = '';

    if (!outlineData.length) {
      area.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">📝</div>
        <div class="empty-state-title">大纲为空</div>
        <div class="empty-state-desc">点击左侧"+ 添加一级标题"开始构建大纲</div>
      </div>`;
      return;
    }

    const tree = document.createElement('div');
    tree.className = 'outline-tree';
    outlineData.forEach(node => renderNode(node, tree));
    area.appendChild(tree);
  }

  function renderNode(node, parent) {
    const wrapper = document.createElement('div');
    wrapper.className = 'outline-node';
    wrapper.setAttribute('data-id', node.id);

    const header = document.createElement('div');
    header.className = 'outline-node-header';
    header.setAttribute('draggable', 'true');
    header.addEventListener('click', (e) => {
      e.stopPropagation();
      selectNode(node, header);
    });
    header.addEventListener('dragstart', (e) => handleDragStart(e, node));
    header.addEventListener('dragover', (e) => handleDragOver(e, node, header));
    header.addEventListener('dragleave', (e) => header.classList.remove('drag-over'));
    header.addEventListener('drop', (e) => handleDrop(e, node, header));

    const expandBtn = document.createElement('button');
    expandBtn.className = 'outline-node-expand';
    expandBtn.innerHTML = '▶';
    if (node._expanded !== false) {
      expandBtn.classList.add('expanded');
    }
    expandBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      node._expanded = !node._expanded;
      renderOutline();
    });

    const numberEl = document.createElement('span');
    numberEl.className = 'outline-node-number';
    numberEl.textContent = node.number || '';

    const textInput = document.createElement('input');
    textInput.className = 'outline-node-text';
    textInput.value = node.text || '';
    if (node.placeholder) {
      textInput.className += ' outline-node-placeholder';
    }
    textInput.addEventListener('input', () => {
      node.text = textInput.value;
      node.placeholder = !textInput.value;
      markDirty();
    });
    textInput.addEventListener('click', (e) => {
      e.stopPropagation();
      selectNode(node, header);
    });
    textInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        textInput.blur();
      }
    });

    const actions = document.createElement('div');
    actions.className = 'outline-node-actions';

    const addChildBtn = document.createElement('button');
    addChildBtn.className = 'outline-node-action';
    addChildBtn.innerHTML = '＋';
    addChildBtn.title = '添加子级';
    addChildBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      addChild(node);
    });

    const addSiblingBtn = document.createElement('button');
    addSiblingBtn.className = 'outline-node-action';
    addSiblingBtn.innerHTML = '↓';
    addSiblingBtn.title = '添加同级';
    addSiblingBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      addSibling(node);
    });

    const delBtn = document.createElement('button');
    delBtn.className = 'outline-node-action danger';
    delBtn.innerHTML = '✕';
    delBtn.title = '删除';
    delBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeNode(node);
    });

    actions.appendChild(addSiblingBtn);
    if (node.level < 3) actions.appendChild(addChildBtn);
    actions.appendChild(delBtn);

    if (node.children && node.children.length) {
      header.appendChild(expandBtn);
    } else {
      const spacer = document.createElement('span');
      spacer.style.cssText = 'width:16px;flex-shrink:0;';
      header.appendChild(spacer);
    }
    header.appendChild(numberEl);
    header.appendChild(textInput);
    header.appendChild(actions);
    wrapper.appendChild(header);

    if (node.children && node.children.length && node._expanded !== false) {
      const childrenDiv = document.createElement('div');
      childrenDiv.className = 'outline-node-children';
      node.children.forEach(child => renderNode(child, childrenDiv));
      wrapper.appendChild(childrenDiv);
    }

    parent.appendChild(wrapper);
  }

  function selectNode(node, headerEl) {
    selectedNode = node;
    $$('.outline-node-header').forEach(h => h.style.background = '');
    if (headerEl) headerEl.style.background = 'var(--accent-dim)';

    const info = $('#nodeInfo');
    info.innerHTML = `
      <div style="margin-bottom:12px;">
        <label style="font-size:11px;color:var(--text-muted);">ID</label>
        <div style="font-size:12px;color:var(--text-primary);font-family:monospace;">${node.id}</div>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:11px;color:var(--text-muted);">层级</label>
        <div style="font-size:13px;color:var(--text-primary);">${node.level} 级标题</div>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:11px;color:var(--text-muted);">编号</label>
        <input type="text" style="width:100%;margin-top:4px;" value="${node.number || ''}"
          onchange="window.App.updateNode('${node.id}', 'number', this.value)">
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:11px;color:var(--text-muted);">标题</label>
        <input type="text" style="width:100%;margin-top:4px;" value="${node.text || ''}"
          onchange="window.App.updateNode('${node.id}', 'text', this.value)">
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:11px;color:var(--text-muted);">子级数量</label>
        <div style="font-size:13px;color:var(--text-primary);">${(node.children || []).length}</div>
      </div>
    `;
  }

  function findNode(id, nodes) {
    for (const n of nodes || outlineData) {
      if (n.id === id) return n;
      if (n.children) {
        const found = findNode(id, n.children);
        if (found) return found;
      }
    }
    return null;
  }

  function findParent(id, nodes, parent) {
    for (const n of nodes || outlineData) {
      if (n.id === id) return { parent, siblings: nodes };
      if (n.children) {
        const found = findParent(id, n.children, n);
        if (found) return found;
      }
    }
    return null;
  }

  function addChild(node) {
    if (!node.children) node.children = [];
    const child = {
      id: `node_${Date.now()}`,
      level: Math.min(node.level + 1, 3),
      number: '',
      text: '',
      children: [],
      placeholder: true
    };
    node.children.push(child);
    node._expanded = true;
    renumberAll();
    renderOutline();
    markDirty();
  }

  function addSibling(node) {
    const result = findParent(node.id, outlineData);
    if (result) {
      const siblings = result.siblings;
      const idx = siblings.indexOf(node);
      const sibling = {
        id: `node_${Date.now()}`,
        level: node.level,
        number: '',
        text: '',
        children: [],
        placeholder: true
      };
      siblings.splice(idx + 1, 0, sibling);
      renumberAll();
      renderOutline();
      markDirty();
    }
  }

  function removeNode(node) {
    const confirmed = true;
    const result = findParent(node.id, outlineData);
    if (result) {
      const siblings = result.siblings;
      const idx = siblings.indexOf(node);
      if (idx >= 0) siblings.splice(idx, 1);
      renumberAll();
      renderOutline();
      markDirty();
      if (selectedNode === node) selectedNode = null;
      toast('已删除章节', 'success');
    }
  }

  function addTopLevel() {
    const node = {
      id: `node_${Date.now()}`,
      level: 1,
      number: '',
      text: '',
      children: [],
      placeholder: true
    };
    outlineData.push(node);
    renumberAll();
    renderOutline();
    markDirty();
  }

  let dragNode = null;

  function handleDragStart(e, node) {
    dragNode = node;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', node.id);
  }

  function handleDragOver(e, node, header) {
    e.preventDefault();
    if (dragNode && dragNode.id !== node.id) {
      header.classList.add('drag-over');
    }
  }

  function handleDrop(e, node, header) {
    e.preventDefault();
    header.classList.remove('drag-over');
    if (!dragNode || dragNode.id === node.id) return;

    const srcResult = findParent(dragNode.id, outlineData);
    const destResult = findParent(node.id, outlineData);

    if (srcResult && destResult) {
      const srcIdx = srcResult.siblings.indexOf(dragNode);
      if (srcIdx >= 0) srcResult.siblings.splice(srcIdx, 1);
      const destIdx = destResult.siblings.indexOf(node);
      destResult.siblings.splice(destIdx, 0, dragNode);
      renumberAll();
      renderOutline();
      markDirty();
    }
    dragNode = null;
  }

  async function save() {
    try {
      const resp = await fetch('/api/outline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(outlineData)
      });
      if (resp.ok) {
        dirty = false;
        originalData = JSON.parse(JSON.stringify(outlineData));
        const bar = $('#btnSave');
        bar.textContent = '已保存 ✓';
        bar.style.background = '#16a34a';
        bar.style.borderColor = '#16a34a';
        bar.style.color = '#fff';
        bar.disabled = true;
        $('#btnReset').disabled = true;
        toast('大纲已保存', 'success');
      }
    } catch (err) {
      toast('保存失败: ' + err.message, 'error');
    }
  }

  async function saveOutline() {
    if (!dirty) { toast('大纲无修改', 'success'); return; }
    if (!confirm('确认保存当前大纲？\n\n保存后可从页面顶栏切换到图表页查看效果。')) return;
    await save();
  }

  function closePreview() {
    if (dirty) {
      if (!confirm('大纲有未保存的修改。确定要关闭预览吗？\n\n未保存的修改将会丢失。')) return;
    }
    fetch('/api/shutdown', { method: 'POST' }).catch(() => {});
  }

  function markDirty() {
    if (dirty) return;
    dirty = true;
    const bar = $('#btnSave');
    bar.textContent = '保存大纲 *';
    bar.style.background = 'var(--accent)';
    bar.style.borderColor = 'var(--accent)';
    bar.style.color = '#000';
    bar.disabled = false;
    $('#btnReset').disabled = false;
  }

  function expandAll() {
    walk(outlineData, n => n._expanded = true);
    renderOutline();
  }

  function collapseAll() {
    walk(outlineData, n => n._expanded = false);
    renderOutline();
  }

  function walk(nodes, fn) {
    for (const n of nodes) {
      fn(n);
      if (n.children) walk(n.children, fn);
    }
  }

  async function load() {
    try {
      const resp = await fetch('/api/outline');
      if (resp.ok) {
        const data = await resp.json();
        outlineData = data || [];
        originalData = JSON.parse(JSON.stringify(outlineData));
        walk(outlineData, n => n._expanded = n.level <= 2);
        renumberAll();
        renderOutline();
        toast(`已加载 ${outlineData.length} 个一级章节`, 'success');
      }
    } catch (err) {
      toast('加载失败: ' + err.message, 'error');
    }
  }

  async function save() {
    try {
      const resp = await fetch('/api/outline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(outlineData)
      });
      if (resp.ok) {
        dirty = false;
        originalData = JSON.parse(JSON.stringify(outlineData));
        const bar = $('.confirm-bar .btn-primary');
        if (bar) bar.textContent = '保存并继续';
        toast('大纲已保存', 'success');
      }
    } catch (err) {
      toast('保存失败: ' + err.message, 'error');
    }
  }

  async function saveAndContinue() {
    await save();
    try {
      await fetch('/api/shutdown', { method: 'POST' });
    } catch (e) {}
  }

  async function saveAndContinue() { await save(); if (confirm('大纲已保存。关闭预览并返回？')) { try { await fetch('/api/shutdown', { method: 'POST' }); } catch (e) {} } }

  function discard() {
    if (dirty && !confirm('放弃修改并恢复原始大纲？')) return;
    if (originalData) {
      outlineData = JSON.parse(JSON.stringify(originalData));
      renumberAll();
      renderOutline();
      dirty = false;
      const bar = $('#btnSave');
      bar.textContent = '保存大纲';
      bar.style.background = 'var(--accent)';
      bar.style.borderColor = 'var(--accent)';
      bar.style.color = '#000';
      bar.disabled = false;
      $('#btnReset').disabled = true;
      toast('已恢复原始大纲', 'success');
    }
  }

  function updateNode(id, field, value) {
    const node = findNode(id, outlineData);
    if (node) {
      node[field] = value;
      if (field === 'text') node.placeholder = !value;
      renderOutline();
      markDirty();
    }
  }

  function importOutline(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        outlineData = JSON.parse(e.target.result);
        walk(outlineData, n => n._expanded = n.level <= 2);
        renumberAll();
        renderOutline();
        markDirty();
        toast('大纲已导入', 'success');
      } catch (err) {
        toast('导入失败: JSON 格式错误', 'error');
      }
    };
    reader.readAsText(file);
  }

  window.App = {
    addTopLevel, expandAll, collapseAll,
    saveAndContinue, saveOutline, closePreview,
    discard, updateNode, importOutline, load
  };

  document.addEventListener('DOMContentLoaded', load);
})();
