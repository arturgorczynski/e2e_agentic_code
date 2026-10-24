"""Small browser interactions and layout rules for the learning UI."""

HISTORY_JS = """
element.addEventListener('submit', (event) => {
  const form = event.target.closest('form');
  if (!form) return;
  event.preventDefault();
  const parts = new URL(form.action).pathname.split('/');
  trigger('navigate', {thread: parts[2], action: parts[3],
    title: new FormData(form).get('title') || ''});
});
"""

GRAPH_JS = """
element.addEventListener('click', (event) => {
  const node = event.target.closest('button[data-run]');
  if (!node) return;
  element.querySelectorAll('[aria-pressed]').forEach(n => n.setAttribute('aria-pressed', 'false'));
  node.setAttribute('aria-pressed', 'true');
  trigger('pick', {run: node.dataset.run, step: node.dataset.step || ''});
});
"""

LAYOUT_CSS = """
#acme-sidebar { height:100dvh !important; overflow:visible !important; box-sizing:border-box; }
#acme-sidebar > .sidebar-content { height:100%; min-height:0; display:flex;
 flex-direction:column; gap:14px; overflow:hidden; }
#acme-sidebar > .sidebar-content > * { flex-shrink:0; }
#sidebar-stack { height:calc(100dvh - 40px); min-height:0; gap:14px; overflow:hidden;
 flex-wrap:nowrap; }
#sidebar-stack > * { flex-shrink:0; }
#history-panel { flex:1 1 180px !important; min-height:90px !important;
 height:auto !important; max-height:none !important; overflow:auto !important;
 contain:paint; border-block:1px solid var(--border-color-primary); padding-block:8px; }
#history-panel > div { min-height:0; overflow:visible; }
.chat-history { padding:0 4px; }
.history-empty { padding:12px; font-size:13px; opacity:.7; }
.chat-menu[open] { position:static; }
.history-row:has(.chat-menu[open]) { flex-wrap:wrap; padding-bottom:8px; }
.chat-menu[open] .chat-menu-panel { position:relative; top:auto; left:auto; right:auto;
 width:100%; box-sizing:border-box; box-shadow:none; }
.chat-menu[open] { flex:1 1 100%; }
#sidebar-settings { max-height:32dvh; overflow:auto; }
#company-tools-panel { max-height:27dvh; overflow:auto; }
#chat-review { max-height:35dvh; overflow:auto; flex-shrink:0; }
.acme-brand { margin-bottom:6px; }
#conversation .message-row { padding:8px clamp(14px,2.5vw,36px) !important;
 box-sizing:border-box; }
#conversation .message.user { margin-right:8px !important; max-width:85% !important; }
#conversation .message.bot { margin-left:8px !important; max-width:94% !important; }
#executions-tab,#tools-tab { padding:24px clamp(16px,3vw,42px) !important; }
#executions-tab > .column,#tools-tab > .column { gap:24px; }
#execution-conversation { min-height:320px; }
#execution-conversation .message-row { padding:8px 20px; }
#execution-conversation .message { cursor:pointer; line-height:1.65; padding:14px 18px; }
#execution-conversation .message:hover { outline:2px solid #0d9488; outline-offset:2px; }
#execution-details { padding:20px; border:1px solid var(--border-color-primary);
 border-radius:16px; margin-top:14px; }
.execution-graph { display:flex; flex-direction:column; align-items:stretch; gap:0;
 padding:20px; max-height:540px; overflow:auto;
 background:var(--background-fill-secondary); border-radius:16px; }
.graph-run { display:flex; flex-direction:column; align-items:center; }
.graph-node { border:1px solid var(--border-color-primary); border-left:5px solid #64748b;
 background:var(--background-fill-primary); color:var(--body-text-color);
 border-radius:12px; padding:14px 18px; text-align:left; cursor:pointer; width:min(100%,650px);
 box-shadow:0 2px 6px #0001; }
.graph-node small { display:block; opacity:.7; margin-top:4px; }
.graph-node.model { border-left-color:#8b5cf6; }
.graph-node.tool { border-left-color:#0891b2; }
.graph-node.context { border-left-color:#d97706; }
.graph-node.error { border-left-color:#dc2626; }
.graph-node.run { border-left-color:#0d9488; font-weight:600; }
.graph-node[aria-pressed=true] { outline:2px solid #0d9488; outline-offset:2px; }
.graph-edge { height:24px; border-left:2px solid #94a3b8; position:relative; }
.graph-edge::after { content:'▼'; position:absolute; bottom:-6px; left:-6px;
 color:#94a3b8; font-size:10px; }
.graph-legend { display:flex; flex-wrap:wrap; gap:18px; font-size:12px; padding:4px 0 16px; }
.tool-catalog { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; }
.tool-card { border:1px solid var(--border-color-primary); border-radius:14px; padding:18px;
 background:var(--background-fill-secondary); }
.tool-card h3 { margin:0 0 6px; font-size:15px; }
.tool-card p { font-size:13px; line-height:1.6; margin:8px 0; }
.tool-card code { font-size:11px; }
.tool-card small { color:var(--body-text-color-subdued); }
@media(max-width:700px) {
 #executions-tab,#tools-tab { padding:16px 10px !important; }
 #conversation .message-row { padding:8px 12px !important; }
 #execution-conversation .message-row { padding:6px 10px; }
 .execution-graph { padding:16px 10px; }
 #acme-sidebar { padding:16px 12px; }
}
@media(max-height:620px) {
 #sidebar-stack { overflow-y:auto; }
 #history-panel { flex:0 0 160px !important; }
}
"""
