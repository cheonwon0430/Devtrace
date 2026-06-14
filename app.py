#!/usr/bin/env python3
# ~/devtrace/app.py

import subprocess
import os
import glob
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, Response, stream_with_context

app = Flask(__name__)

HOME = Path.home()
DEVTRACE_DIR = HOME / "devtrace"
JOURNAL_DIR = DEVTRACE_DIR / "journal"
PORTFOLIO_DIR = DEVTRACE_DIR / "portfolio"
DEVTRACE_SH = str(DEVTRACE_DIR / "devtrace.sh")

def get_journals(limit=20):
    journals = []
    seen = set()

    patterns = [
        str(JOURNAL_DIR / "20*.md"),
        str(JOURNAL_DIR / "weekly_*.md"),
        str(JOURNAL_DIR / "full_summary.md"),
        str(JOURNAL_DIR / "range_*.md"),
        str(JOURNAL_DIR / "project_*.md"),
        str(PORTFOLIO_DIR / "*_README.md"),
        str(PORTFOLIO_DIR / "*_interview.md"),
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    files = sorted(set(files), key=lambda f: Path(f).stat().st_mtime, reverse=True)[:limit]

    for f in files:
        p = Path(f)
        if str(p) not in seen:
            seen.add(str(p))
            journals.append({
                "name": p.stem,
                "path": str(p),
                "size": p.stat().st_size,
            })

    return journals

def get_projects():
    project_dir_env = os.popen(
        f"bash -c 'source {DEVTRACE_DIR}/config.env && echo $PROJECT_DIR'"
    ).read().strip()
    if not project_dir_env:
        project_dir_env = str(HOME / "projects")
    projects = []
    try:
        result = subprocess.run(
            ["find", project_dir_env, "-maxdepth", "3", "-name", ".git", "-type", "d"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                projects.append(Path(line).parent.name)
    except Exception:
        pass
    return projects

HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DevTrace</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

  :root {
    --bg:      #0d0d0d;
    --surface: #141414;
    --card:    #1a1a1a;
    --border:  #2a2a2a;
    --accent:  #e8441a;
    --accent2: #f5a623;
    --green:   #3ecf74;
    --text:    #e8e8e8;
    --muted:   #666;
    --mono:    'JetBrains Mono', monospace;
    --sans:    'Inter', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* HEADER */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    position: sticky;
    top: 0;
    z-index: 100;
    height: 58px;
  }

  .logo { display: flex; align-items: baseline; gap: 10px; }
  .logo-text { font-family: var(--mono); font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
  .logo-text span { color: var(--accent); }
  .logo-sub { font-size: 11px; color: var(--muted); font-family: var(--mono); }

  .header-right { display: flex; align-items: center; gap: 14px; }

  .status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--green); box-shadow: 0 0 6px var(--green);
    animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  .status-label { font-family: var(--mono); font-size: 11px; color: var(--muted); }

  .api-toggle {
    display: flex; background: var(--card);
    border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
  }
  .api-toggle button {
    padding: 5px 13px; border: none; background: transparent;
    color: var(--muted); cursor: pointer; font-family: var(--mono); font-size: 11px;
    transition: all 0.15s;
  }
  .api-toggle button.active { background: var(--accent); color: #fff; }

  /* LAYOUT */
  .layout {
    display: grid;
    grid-template-columns: 260px 1fr 300px;
    flex: 1;
    height: calc(100vh - 58px);
    overflow: hidden;
  }

  /* SIDEBAR */
  .sidebar {
    border-right: 1px solid var(--border);
    background: var(--surface);
    overflow-y: auto;
    padding: 16px 0;
    display: flex;
    flex-direction: column;
  }
  .sidebar::-webkit-scrollbar { width: 3px; }
  .sidebar::-webkit-scrollbar-thumb { background: var(--border); }

  .sidebar-label {
    font-family: var(--mono); font-size: 9px; letter-spacing: 0.15em;
    color: var(--muted); padding: 0 18px 6px; text-transform: uppercase;
  }
  .sidebar-section { margin-bottom: 6px; }

  .cmd-btn {
    display: flex; align-items: center; gap: 10px;
    width: 100%; padding: 10px 18px;
    background: transparent; border: none; color: var(--text);
    cursor: pointer; font-family: var(--sans); font-size: 13px;
    text-align: left; transition: background 0.1s;
    border-left: 2px solid transparent;
  }
  .cmd-btn:hover { background: var(--card); }
  .cmd-btn.active { background: var(--card); border-left-color: var(--accent); color: #fff; }

  .cmd-icon { font-size: 14px; width: 18px; text-align: center; flex-shrink: 0; }
  .cmd-info { flex: 1; min-width: 0; }
  .cmd-name { font-weight: 600; font-size: 13px; }
  .cmd-desc { font-size: 11px; color: var(--muted); margin-top: 1px; }

  .sidebar-divider { border: none; border-top: 1px solid var(--border); margin: 8px 18px; }

  /* MAIN */
  main {
    display: flex; flex-direction: column;
    overflow: hidden; background: var(--bg);
  }

  /* 상단 컨트롤 바 */
  .control-bar {
    padding: 14px 24px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center;
    justify-content: space-between; gap: 12px;
    background: var(--surface);
    flex-shrink: 0;
  }

  .control-left { display: flex; flex-direction: column; gap: 3px; }
  .main-title { font-size: 14px; font-weight: 600; }
  .main-cmd { font-size: 11px; color: var(--muted); font-family: var(--mono); }

  .control-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }

  .input-wrap { display: flex; align-items: center; gap: 6px; }
  .input-label { font-size: 11px; color: var(--muted); font-family: var(--mono); white-space: nowrap; }

  .cmd-input {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 6px; padding: 7px 11px; color: var(--text);
    font-family: var(--mono); font-size: 12px; width: 160px;
    outline: none; transition: border-color 0.15s;
  }
  .cmd-input.short { width: 120px; }
  .cmd-input:focus { border-color: var(--accent); }
  .cmd-input::placeholder { color: var(--muted); }

  .run-btn {
    display: flex; align-items: center; gap: 7px;
    padding: 8px 18px; background: var(--accent);
    border: none; border-radius: 6px; color: #fff;
    font-family: var(--sans); font-weight: 600; font-size: 13px;
    cursor: pointer; transition: opacity 0.15s; white-space: nowrap;
  }
  .run-btn:hover { opacity: 0.88; }
  .run-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .run-btn .spinner {
    width: 12px; height: 12px;
    border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
    border-radius: 50%; animation: spin 0.7s linear infinite; display: none;
  }
  .run-btn.running .spinner { display: block; }
  .run-btn.running .btn-text { display: none; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* 콘텐츠 영역: 위=로그, 아래=결과물 */
  .content-area {
    flex: 1; display: flex; flex-direction: column;
    overflow: hidden; gap: 0;
  }

  /* 로그 터미널 (위, 작게) */
  .log-wrap {
    height: 220px; flex-shrink: 0;
    display: flex; flex-direction: column;
    border-bottom: 1px solid var(--border);
    background: #0a0a0a;
  }

  .terminal-bar {
    display: flex; align-items: center; gap: 6px;
    padding: 8px 12px; background: var(--card);
    border-bottom: 1px solid var(--border); flex-shrink: 0;
  }
  .dot { width: 10px; height: 10px; border-radius: 50%; }
  .dot-r { background: #ff5f56; }
  .dot-y { background: #ffbd2e; }
  .dot-g { background: #27c93f; }
  .terminal-title { margin-left: 6px; font-family: var(--mono); font-size: 11px; color: var(--muted); }
  .clear-btn {
    margin-left: auto; background: none; border: none;
    color: var(--muted); font-size: 11px; font-family: var(--mono);
    cursor: pointer; padding: 2px 6px; border-radius: 3px;
  }
  .clear-btn:hover { color: var(--text); }

  #terminal {
    flex: 1; overflow-y: auto; padding: 10px 16px;
    font-family: var(--mono); font-size: 11.5px; line-height: 1.6;
    white-space: pre-wrap; word-break: break-all;
  }
  #terminal::-webkit-scrollbar { width: 3px; }
  #terminal::-webkit-scrollbar-thumb { background: var(--border); }

  .line-cmd   { color: var(--accent2); }
  .line-ok    { color: var(--green); }
  .line-err   { color: #ff6b6b; }
  .line-info  { color: #8eb8e8; }
  .line-plain { color: #b0b0b0; }

  /* 결과물 뷰어 (아래, 크게) */
  .result-wrap {
    flex: 1; display: flex; flex-direction: column;
    overflow: hidden; background: var(--bg);
  }

  .result-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 20px; border-bottom: 1px solid var(--border);
    background: var(--surface); flex-shrink: 0;
  }
  .result-title { font-family: var(--mono); font-size: 11px; color: var(--muted); letter-spacing: 0.08em; }
  .result-name { font-family: var(--mono); font-size: 12px; color: var(--accent2); }

  #result-view {
    flex: 1; overflow-y: auto; padding: 20px 28px;
    font-family: var(--mono); font-size: 12.5px; line-height: 1.8;
    white-space: pre-wrap; color: #ccc;
  }
  #result-view::-webkit-scrollbar { width: 4px; }
  #result-view::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  .result-empty {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    height: 100%; gap: 8px; color: var(--muted);
  }
  .result-empty .ei { font-size: 28px; opacity: 0.25; }
  .result-empty p { font-size: 12px; font-family: var(--mono); }

  /* RIGHT PANEL */
  .right-panel {
    border-left: 1px solid var(--border);
    background: var(--surface);
    display: flex; flex-direction: column; overflow: hidden;
  }
  .panel-header {
    padding: 14px 18px; border-bottom: 1px solid var(--border);
    font-size: 10px; font-family: var(--mono);
    letter-spacing: 0.12em; color: var(--muted); text-transform: uppercase;
    flex-shrink: 0;
  }
  .journal-list { flex: 1; overflow-y: auto; padding: 6px 0; }
  .journal-list::-webkit-scrollbar { width: 3px; }
  .journal-list::-webkit-scrollbar-thumb { background: var(--border); }

  .journal-item {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 18px; cursor: pointer;
    transition: background 0.1s; border-left: 2px solid transparent;
  }
  .journal-item:hover { background: var(--card); }
  .journal-item.active { background: var(--card); border-left-color: var(--accent2); }

  .journal-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--accent2); flex-shrink: 0; }
  .journal-date { font-family: var(--mono); font-size: 11.5px; font-weight: 600; color: var(--text); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .journal-size { font-family: var(--mono); font-size: 10px; color: var(--muted); flex-shrink: 0; }

  /* TOAST */
  .toast {
    position: fixed; bottom: 24px; right: 24px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px 16px;
    font-size: 12px; font-family: var(--mono);
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    opacity: 0; transform: translateY(6px);
    transition: all 0.2s; z-index: 999; pointer-events: none;
  }
  .toast.show { opacity: 1; transform: translateY(0); }
  .toast.success { border-color: var(--green); color: var(--green); }
  .toast.error   { border-color: #ff6b6b; color: #ff6b6b; }
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-text"><span>Dev</span>Trace</div>
    <div class="logo-sub">개발 과정 자동 기록 시스템</div>
  </div>
  <div class="header-right">
    <div class="api-toggle">
      <button id="btn-groq" class="active" onclick="setApi('groq')">Groq</button>
      <button id="btn-openai" onclick="setApi('openai')">OpenAI</button>
    </div>
    <div style="display:flex;align-items:center;gap:6px;">
      <div class="status-dot"></div>
      <span class="status-label">v2.11</span>
    </div>
  </div>
</header>

<div class="layout">

  <!-- SIDEBAR -->
  <nav class="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-label">일지</div>
      <button class="cmd-btn active" onclick="selectCmd(this,'daily')">
        <span class="cmd-icon">📅</span>
        <div class="cmd-info"><div class="cmd-name">daily</div><div class="cmd-desc">오늘 일지 생성</div></div>
      </button>
      <button class="cmd-btn" onclick="selectCmd(this,'weekly')">
        <span class="cmd-icon">📊</span>
        <div class="cmd-info"><div class="cmd-name">weekly</div><div class="cmd-desc">주간 리포트 생성</div></div>
      </button>
      <button class="cmd-btn" onclick="selectCmd(this,'full')">
        <span class="cmd-icon">📚</span>
        <div class="cmd-info"><div class="cmd-name">full</div><div class="cmd-desc">전체 히스토리 요약</div></div>
      </button>
      <button class="cmd-btn" onclick="selectCmd(this,'range')">
        <span class="cmd-icon">📅</span>
        <div class="cmd-info"><div class="cmd-name">range</div><div class="cmd-desc">날짜 범위 분석</div></div>
      </button>
      <button class="cmd-btn" onclick="selectCmd(this,'regenerate')">
        <span class="cmd-icon">🔄</span>
        <div class="cmd-info"><div class="cmd-name">regenerate</div><div class="cmd-desc">AI만 재호출</div></div>
      </button>
    </div>

    <hr class="sidebar-divider">

    <div class="sidebar-section">
      <div class="sidebar-label">프로젝트</div>
      <button class="cmd-btn" onclick="selectCmd(this,'project')">
        <span class="cmd-icon">🔍</span>
        <div class="cmd-info"><div class="cmd-name">project</div><div class="cmd-desc">프로젝트 단위 분석</div></div>
      </button>
      <button class="cmd-btn" onclick="selectCmd(this,'portfolio')">
        <span class="cmd-icon">🏗</span>
        <div class="cmd-info"><div class="cmd-name">portfolio</div><div class="cmd-desc">GitHub README 생성</div></div>
      </button>
      <button class="cmd-btn" onclick="selectCmd(this,'interview')">
        <span class="cmd-icon">🎤</span>
        <div class="cmd-info"><div class="cmd-name">interview</div><div class="cmd-desc">면접 질문 생성</div></div>
      </button>
    </div>

    <hr class="sidebar-divider">

    <div class="sidebar-section">
      <div class="sidebar-label">시스템</div>
      <button class="cmd-btn" onclick="selectCmd(this,'push')">
        <span class="cmd-icon">📤</span>
        <div class="cmd-info"><div class="cmd-name">push</div><div class="cmd-desc">GitHub push</div></div>
      </button>
      <button class="cmd-btn" onclick="selectCmd(this,'status')">
        <span class="cmd-icon">⚙️</span>
        <div class="cmd-info"><div class="cmd-name">status</div><div class="cmd-desc">데몬 상태 확인</div></div>
      </button>
    </div>
  </nav>

  <!-- MAIN -->
  <main>
    <!-- 컨트롤 바 -->
    <div class="control-bar">
      <div class="control-left">
        <div class="main-title" id="main-title">daily — 오늘 일지 생성</div>
        <div class="main-cmd" id="main-cmd">$ bash devtrace.sh daily</div>
      </div>
      <div class="control-right" id="control-right">
        <!-- 입력칸은 JS가 동적으로 렌더링 -->
        <button class="run-btn" id="run-btn" onclick="runCommand()">
          <div class="spinner"></div>
          <span class="btn-text">▶ 실행</span>
        </button>
      </div>
    </div>

    <!-- 콘텐츠 영역 -->
    <div class="content-area">

      <!-- 위: 실행 로그 -->
      <div class="log-wrap">
        <div class="terminal-bar">
          <div class="dot dot-r"></div>
          <div class="dot dot-y"></div>
          <div class="dot dot-g"></div>
          <span class="terminal-title" id="terminal-title">대기 중</span>
          <button class="clear-btn" onclick="clearLog()">clear</button>
        </div>
        <div id="terminal">
          <span style="color:#444;font-family:var(--mono);font-size:11px;">실행 로그가 여기에 표시됩니다</span>
        </div>
      </div>

      <!-- 아래: 결과물 뷰어 -->
      <div class="result-wrap">
        <div class="result-header">
          <span class="result-title">RESULT</span>
          <span class="result-name" id="result-name">—</span>
        </div>
        <div id="result-view">
          <div class="result-empty">
            <div class="ei">📄</div>
            <p>실행 후 결과물이 여기에 표시됩니다</p>
          </div>
        </div>
      </div>

    </div>
  </main>

  <!-- RIGHT PANEL: 파일 목록 -->
  <div class="right-panel">
    <div class="panel-header">저장된 파일</div>
    <div class="journal-list" id="journal-list">
      {% if journals %}
        {% for j in journals %}
        <div class="journal-item" onclick="loadJournal('{{ j.path }}', '{{ j.name }}', this)">
          <div class="journal-dot"></div>
          <div class="journal-date" title="{{ j.name }}">{{ j.name }}</div>
          <div class="journal-size">{{ (j.size / 1024) | round(1) }}KB</div>
        </div>
        {% endfor %}
      {% else %}
        <div style="padding:16px 18px;font-size:11px;color:var(--muted);font-family:var(--mono);">파일 없음</div>
      {% endif %}
    </div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
let currentCmd = 'daily';
let currentApi = 'groq';
let isRunning = false;
let lastResultPath = null;

const CMD_META = {
  daily:      { title: 'daily — 오늘 일지 생성',        cmd: '$ bash devtrace.sh daily',             inputs: [] },
  weekly:     { title: 'weekly — 주간 리포트',           cmd: '$ bash devtrace.sh weekly',            inputs: [] },
  full:       { title: 'full — 전체 히스토리 요약',      cmd: '$ bash devtrace.sh full',              inputs: [] },
  range:      { title: 'range — 날짜 범위 분석',         cmd: '$ bash devtrace.sh range <from> <to>', inputs: ['from','to'] },
  regenerate: { title: 'regenerate — AI 재호출',         cmd: '$ bash devtrace.sh regenerate <날짜>', inputs: ['date'] },
  project:    { title: 'project — 프로젝트 분석',        cmd: '$ bash devtrace.sh project <이름>',    inputs: ['project'] },
  portfolio:  { title: 'portfolio — GitHub README 생성', cmd: '$ bash devtrace.sh portfolio <이름>',  inputs: ['project'] },
  interview:  { title: 'interview — 면접 질문 생성',     cmd: '$ bash devtrace.sh interview <이름>',  inputs: ['project'] },
  push:       { title: 'push — GitHub push',             cmd: '$ bash devtrace.sh push',              inputs: [] },
  status:     { title: 'status — 데몬 상태 확인',        cmd: '$ bash devtrace.sh status',            inputs: [] },
};

const INPUT_CONFIG = {
  project: { label: '프로젝트', placeholder: '프로젝트 이름', type: 'project', cls: '' },
  from:    { label: 'from',     placeholder: '2026-06-01',    type: 'date',    cls: 'short' },
  to:      { label: 'to',       placeholder: '2026-06-14',    type: 'date',    cls: 'short' },
  date:    { label: '날짜',     placeholder: '2026-06-14',    type: 'date',    cls: 'short' },
};

const PROJECTS = {{ projects | tojson }};

function setApi(api) {
  currentApi = api;
  document.getElementById('btn-groq').classList.toggle('active', api === 'groq');
  document.getElementById('btn-openai').classList.toggle('active', api === 'openai');
  showToast(api === 'groq' ? 'Groq (llama-3.3-70b)' : 'OpenAI (gpt-4o-mini)', 'success');
}

function renderInputs(inputs) {
  const cr = document.getElementById('control-right');
  // 기존 입력칸 제거 (run-btn 앞까지)
  const btn = document.getElementById('run-btn');
  while (cr.firstChild && cr.firstChild !== btn) cr.removeChild(cr.firstChild);

  inputs.forEach(key => {
    const cfg = INPUT_CONFIG[key];
    const wrap = document.createElement('div');
    wrap.className = 'input-wrap';

    const label = document.createElement('span');
    label.className = 'input-label';
    label.textContent = cfg.label + ':';

    const inp = document.createElement('input');
    inp.type = 'text';
    inp.className = 'cmd-input ' + cfg.cls;
    inp.placeholder = cfg.placeholder;
    inp.id = 'input-' + key;
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') runCommand(); });

    if (cfg.type === 'project' && PROJECTS.length > 0) {
      const dl = document.createElement('datalist');
      dl.id = 'dl-project';
      PROJECTS.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        dl.appendChild(opt);
      });
      document.body.appendChild(dl);
      inp.setAttribute('list', 'dl-project');
    }

    if (cfg.type === 'date') {
      // 오늘 날짜 기본값
      inp.value = new Date().toISOString().slice(0, 10);
    }

    wrap.appendChild(label);
    wrap.appendChild(inp);
    cr.insertBefore(wrap, btn);
  });
}

function selectCmd(el, cmd) {
  document.querySelectorAll('.cmd-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  currentCmd = cmd;
  const m = CMD_META[cmd];
  document.getElementById('main-title').textContent = m.title;
  document.getElementById('main-cmd').textContent = m.cmd;
  renderInputs(m.inputs);
}

function getInputVal(key) {
  const el = document.getElementById('input-' + key);
  return el ? el.value.trim() : '';
}

function clearLog() {
  document.getElementById('terminal').innerHTML =
    '<span style="color:#444;font-family:var(--mono);font-size:11px;">실행 로그가 여기에 표시됩니다</span>';
  document.getElementById('terminal-title').textContent = '대기 중';
}

function appendLine(text, cls) {
  const t = document.getElementById('terminal');
  if (t.querySelector('span')) t.innerHTML = '';
  const div = document.createElement('div');
  div.className = cls || 'line-plain';
  div.textContent = text;
  t.appendChild(div);
  t.scrollTop = t.scrollHeight;
}

function classifyLine(line) {
  if (!line) return 'line-plain';
  if (line.startsWith('✅') || line.startsWith('📖') || line.startsWith('📊')) return 'line-ok';
  if (line.startsWith('❌') || line.startsWith('⚠️')) return 'line-err';
  if (line.match(/^[📡🔄📝🗓📚🏗🎤📤🔍⏳\[]/)) return 'line-info';
  if (line.startsWith('$')) return 'line-cmd';
  return 'line-plain';
}

function showResult(content, name) {
  const rv = document.getElementById('result-view');
  rv.innerHTML = '';
  rv.textContent = content;
  document.getElementById('result-name').textContent = name || '—';
}

async function loadResultFile(path, name) {
  if (!path) return;
  try {
    const res = await fetch('/journal?path=' + encodeURIComponent(path));
    if (!res.ok) return;
    const text = await res.text();
    showResult(text, name);
  } catch(e) {}
}

async function runCommand() {
  if (isRunning) return;
  const m = CMD_META[currentCmd];

  // 입력값 검증
  for (const key of m.inputs) {
    const val = getInputVal(key);
    if (!val) {
      showToast(INPUT_CONFIG[key].label + ' 값을 입력하세요', 'error');
      document.getElementById('input-' + key).focus();
      return;
    }
  }

  isRunning = true;
  const btn = document.getElementById('run-btn');
  btn.classList.add('running');
  btn.disabled = true;

  document.getElementById('terminal').innerHTML = '';
  const now = new Date().toLocaleTimeString('ko-KR');
  document.getElementById('terminal-title').textContent = currentCmd + ' — ' + now;
  document.getElementById('result-view').innerHTML =
    '<div class="result-empty"><div class="ei">⏳</div><p>생성 중...</p></div>';
  document.getElementById('result-name').textContent = '생성 중...';

  // 커맨드 표시
  let cmdDisplay = '$ bash devtrace.sh ' + currentCmd;
  m.inputs.forEach(k => { cmdDisplay += ' ' + getInputVal(k); });
  if (['daily','project','portfolio','interview','full','range','regenerate'].includes(currentCmd)) {
    cmdDisplay += currentApi !== 'groq' ? ' --api ' + currentApi : '';
  }
  appendLine(cmdDisplay, 'line-cmd');
  appendLine('', 'line-plain');

  // params
  const params = new URLSearchParams({ cmd: currentCmd, api: currentApi });
  m.inputs.forEach(k => params.set(k, getInputVal(k)));

  try {
    const res = await fetch('/run?' + params);
    if (!res.ok) throw new Error('서버 오류: ' + res.status);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\\n');
      buf = lines.pop();
      lines.forEach(line => appendLine(line, classifyLine(line)));
    }
    if (buf) appendLine(buf, classifyLine(buf));

  } catch(e) {
    appendLine('❌ 오류: ' + e.message, 'line-err');
  } finally {
    isRunning = false;
    btn.classList.remove('running');
    btn.disabled = false;
    appendLine('', 'line-plain');
    appendLine('─'.repeat(40), 'line-plain');

    // 결과 파일 자동 로드
    await autoLoadResult();
    // 파일 목록 갱신
    refreshJournals();
  }
}

async function autoLoadResult() {
  const today = new Date().toISOString().slice(0, 10);
  let path = null;
  let name = null;

  const proj = getInputVal('project');

  if (currentCmd === 'daily') {
    path = '{{ journal_dir }}/' + today + '.md';
    name = today;
  } else if (currentCmd === 'weekly') {
    // weekly_YYYY-WNN.md
    const now = new Date();
    const week = String(Math.ceil(now.getDate() / 7)).padStart(2, '0');
    name = 'weekly_' + now.getFullYear() + '-W' + week;
    path = '{{ journal_dir }}/' + name + '.md';
  } else if (currentCmd === 'full') {
    path = '{{ journal_dir }}/full_summary.md';
    name = 'full_summary';
  } else if (currentCmd === 'range') {
    const f = getInputVal('from'), t = getInputVal('to');
    name = 'range_' + f + '_' + t;
    path = '{{ journal_dir }}/' + name + '.md';
  } else if (currentCmd === 'regenerate') {
    const d = getInputVal('date');
    path = '{{ journal_dir }}/' + d + '.md';
    name = d;
  } else if (currentCmd === 'project') {
    path = '{{ journal_dir }}/project_' + proj + '.md';
    name = 'project_' + proj;
  } else if (currentCmd === 'portfolio') {
    path = '{{ portfolio_dir }}/' + proj + '_README.md';
    name = proj + '_README';
  } else if (currentCmd === 'interview') {
    path = '{{ portfolio_dir }}/' + proj + '_interview.md';
    name = proj + '_interview';
  }

  if (path) await loadResultFile(path, name);
}

async function refreshJournals() {
  try {
    const res = await fetch('/journals');
    const data = await res.json();
    const list = document.getElementById('journal-list');
    list.innerHTML = '';
    data.forEach(j => {
      const div = document.createElement('div');
      div.className = 'journal-item';
      div.onclick = () => loadJournal(j.path, j.name, div);
      div.innerHTML = `
        <div class="journal-dot"></div>
        <div class="journal-date" title="${j.name}">${j.name}</div>
        <div class="journal-size">${(j.size/1024).toFixed(1)}KB</div>
      `;
      list.appendChild(div);
    });
  } catch(e) {}
}

async function loadJournal(path, name, el) {
  document.querySelectorAll('.journal-item').forEach(i => i.classList.remove('active'));
  if (el) el.classList.add('active');
  try {
    const res = await fetch('/journal?path=' + encodeURIComponent(path));
    if (!res.ok) { showToast('파일 불러오기 실패', 'error'); return; }
    const text = await res.text();
    showResult(text, name);
  } catch(e) {
    showToast('오류: ' + e.message, 'error');
  }
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + (type || '');
  setTimeout(() => { t.className = 'toast'; }, 2200);
}

// 초기 입력칸 렌더링
renderInputs([]);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(
        HTML,
        journals=get_journals(),
        projects=get_projects(),
        journal_dir=str(JOURNAL_DIR),
        portfolio_dir=str(PORTFOLIO_DIR),
    )


@app.route("/run")
def run():
    cmd = request.args.get("cmd", "daily")
    api = request.args.get("api", "groq")
    project = request.args.get("project", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    date = request.args.get("date", "").strip()

    allowed = {"daily","weekly","full","range","regenerate","project","portfolio","interview","push","status"}
    if cmd not in allowed:
        return Response("허용되지 않는 명령어", status=400)

    args = ["bash", DEVTRACE_SH, cmd]

    if cmd == "range":
        if date_from: args.append(date_from)
        if date_to:   args.append(date_to)
    elif cmd == "regenerate":
        if date: args.append(date)
    elif cmd in ("project", "portfolio", "interview") and project:
        args.append(project)

    if api in ("groq", "openai") and cmd in ("daily","project","portfolio","interview","full","range","regenerate"):
        args += ["--api", api]

    def generate():
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(DEVTRACE_DIR),
            )
            for line in iter(proc.stdout.readline, ""):
                yield line
            proc.wait()
            if proc.returncode == 0:
                yield "\n✅ 완료\n"
            else:
                yield f"\n⚠️  종료 코드: {proc.returncode}\n"
        except Exception as e:
            yield f"❌ 실행 오류: {e}\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain",
        headers={"X-Accel-Buffering": "no"},
    )


@app.route("/journals")
def journals():
    return jsonify(get_journals())


@app.route("/journal")
def journal():
    path = request.args.get("path", "")
    p = Path(path)
    allowed_dirs = [str(JOURNAL_DIR), str(PORTFOLIO_DIR)]
    if not p.exists() or not any(str(p).startswith(d) for d in allowed_dirs):
        return "파일 없음", 404
    return p.read_text(encoding="utf-8"), 200, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    print("╔══════════════════════════════════╗")
    print("║     DevTrace Web Dashboard       ║")
    print("║   http://localhost:5000          ║")
    print("╚══════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
