"""Interactive HTML Timeline — ChatVault-style email + chat viewer with search, bookmarks, lightbox."""
from __future__ import annotations

import base64
import html
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from casepulse.storage.database import Database


def build_interactive_timeline(db: Database, output_dir: str,
                                case_name: str = "",
                                date_start: str = "", date_end: str = "",
                                include_chats: bool = True,
                                include_images_inline: bool = False,
                                case_id: int = None,
                                progress_cb=None) -> dict:
    """Build an interactive HTML timeline with search, bookmarks, and inline media.

    Creates:
    - timeline.html — self-contained interactive viewer
    - media/ — attachment images (referenced or embedded)
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    media_dir = out / "media"
    media_dir.mkdir(exist_ok=True)

    # ── Gather data ──
    if progress_cb:
        progress_cb("Gathering emails...")

    emails = db.get_emails(date_start=date_start, date_end=date_end, limit=50000)
    account_map = {a["id"]: a["email"] for a in db.get_accounts()}

    chats = []
    if include_chats:
        chats = db.get_chat_messages(date_start=date_start, date_end=date_end,
                                      include_system=False, limit=100000)
        if progress_cb:
            progress_cb(f"Found {len(emails)} emails + {len(chats)} chats")

    # Get evidence tags
    tag_map = {}
    if case_id:
        cases = db.get_cases()
        for case in cases:
            for t in db.get_evidence_tags_for_case(case["id"]):
                key = f"{t['item_type']}_{t['item_id']}"
                tag_map[key] = t

    # Get sender categories
    from casepulse.storage.database import Database as _DB
    sender_cats = {}
    for s in db.get_senders():
        cats = _DB.parse_categories(s.get("category"))
        if cats:
            sender_cats[s["email"]] = cats

    # ── Build unified items ──
    items = []
    img_count = 0

    for e in emails:
        sender = e.get("sender_email", "")
        tag_key = f"email_{e['id']}"
        tag = tag_map.get(tag_key)

        # Get attachments
        attachments = db.get_attachments_for_email(e["id"])
        att_data = []
        for att in attachments:
            att_info = {
                "filename": att["filename"],
                "size": att.get("size_bytes", 0),
                "type": att.get("content_type", ""),
                "text": (att.get("extracted_text") or "")[:2000],
                "is_duplicate": bool(att.get("is_duplicate")),
            }
            # Copy images to media folder
            fpath = att.get("file_path", "")
            if fpath and Path(fpath).exists():
                ext = Path(fpath).suffix.lower()
                if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                    media_name = f"att_{e['id']}_{att['id']}{ext}"
                    dst = media_dir / media_name
                    if not dst.exists():
                        try:
                            shutil.copy2(fpath, str(dst))
                            img_count += 1
                        except Exception:
                            pass
                    att_info["image"] = f"media/{media_name}"
            att_data.append(att_info)

        cats = sender_cats.get(sender, [])

        items.append({
            "type": "email",
            "id": e["id"],
            "timestamp": e.get("date_received", ""),
            "sender": sender,
            "sender_name": e.get("sender_name", ""),
            "subject": e.get("subject", ""),
            "body": e.get("body_text", "") or "",
            "direction": e.get("direction", ""),
            "is_forwarded": bool(e.get("is_forwarded")),
            "original_sender": e.get("original_sender", ""),
            "mailbox": account_map.get(e.get("account_id"), ""),
            "exhibit": tag.get("exhibit_label", "") if tag else "",
            "flag": tag.get("flag", "") if tag else "",
            "categories": cats,
            "attachments": att_data,
            "has_attachments": bool(att_data),
        })

    for m in chats:
        items.append({
            "type": "chat",
            "id": m["id"],
            "timestamp": m.get("timestamp", ""),
            "sender": m.get("sender", ""),
            "sender_name": m.get("sender", ""),
            "subject": m.get("chat_name", ""),
            "body": m.get("message_text", "") or "",
            "direction": "",
            "is_forwarded": False,
            "original_sender": "",
            "mailbox": m.get("platform", ""),
            "exhibit": "",
            "flag": "",
            "categories": [],
            "attachments": [],
            "has_attachments": bool(m.get("has_media")),
        })

    items.sort(key=lambda x: x["timestamp"] or "")

    if progress_cb:
        progress_cb(f"Building HTML for {len(items)} items...")

    # ── Build search index ──
    search_index = []
    for idx, item in enumerate(items):
        search_index.append({
            "i": idx,
            "t": (item.get("body", "")[:500] + " " + item.get("subject", "")).lower(),
            "s": item.get("sender", "").lower(),
            "d": (item.get("timestamp") or "")[:10],
            "type": item["type"],
            "dir": item.get("direction", ""),
            "att": item.get("has_attachments", False),
        })

    # ── Build HTML ──
    total = len(items)
    email_count = sum(1 for i in items if i["type"] == "email")
    chat_count = sum(1 for i in items if i["type"] == "chat")

    # Escape items for JSON embedding
    items_json = json.dumps(items, default=str, ensure_ascii=False)
    index_json = json.dumps(search_index, ensure_ascii=False)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CasePulse Timeline — {html.escape(case_name)}</title>
<style>
:root {{
  --bg: #f8f9fa; --card: #fff; --border: #dee2e6; --text: #212529;
  --muted: #6c757d; --accent: #0d6efd; --sent-bg: #d4edda; --recv-bg: #fff;
  --highlight: #fff3cd; --danger: #dc3545; --success: #198754;
}}
[data-theme="dark"] {{
  --bg: #1a1a2e; --card: #16213e; --border: #333; --text: #e9edef;
  --muted: #8696a0; --accent: #4da3ff; --sent-bg: #005c4b; --recv-bg: #202c33;
  --highlight: #3d3100; --danger: #ff6b6b; --success: #51cf66;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: var(--bg); color: var(--text); line-height: 1.5; }}

/* Header */
.header {{ background: #1a1a2e; color: #fff; padding: 15px 20px; display: flex;
           justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
           position: sticky; top: 0; z-index: 200; }}
.header h1 {{ font-size: 1.2rem; font-weight: 600; }}
.header .meta {{ color: #adb5bd; font-size: 0.8rem; }}
.header-actions {{ display: flex; gap: 8px; }}
.header-actions button {{ padding: 5px 12px; border: 1px solid rgba(255,255,255,0.3);
  background: transparent; color: #fff; border-radius: 6px; cursor: pointer; font-size: 0.75rem; }}
.header-actions button:hover {{ background: rgba(255,255,255,0.15); }}
.header-actions button.active {{ background: var(--accent); border-color: var(--accent); }}

/* Search bar */
.search-bar {{ background: var(--card); border-bottom: 1px solid var(--border); padding: 10px 20px;
               position: sticky; top: 52px; z-index: 190; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
.search-bar input {{ flex: 1; min-width: 200px; padding: 8px 12px; border: 1px solid var(--border);
                     border-radius: 6px; font-size: 0.85rem; background: var(--bg); color: var(--text); }}
.filter-chips {{ display: flex; gap: 5px; flex-wrap: wrap; }}
.chip {{ padding: 4px 10px; border-radius: 12px; font-size: 0.7rem; cursor: pointer;
         border: 1px solid var(--border); background: var(--card); color: var(--text); }}
.chip.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.search-count {{ font-size: 0.75rem; color: var(--muted); min-width: 80px; }}

/* Content */
.content {{ max-width: 1000px; margin: 0 auto; padding: 10px 15px; }}
.date-header {{ background: var(--accent); color: #fff; padding: 8px 15px; border-radius: 8px;
                font-weight: 600; font-size: 0.85rem; margin: 15px 0 8px; position: sticky;
                top: 100px; z-index: 100; }}

/* Email card */
.item {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px;
         margin-bottom: 8px; overflow: hidden; transition: all 0.15s; }}
.item:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.item.bookmarked {{ border-left: 3px solid #f59e0b; }}
.item.highlighted {{ background: var(--highlight); }}
.item-header {{ padding: 10px 15px; cursor: pointer; display: flex; gap: 10px; align-items: flex-start; }}
.item-header:hover {{ background: rgba(0,0,0,0.02); }}
.item-time {{ font-size: 0.7rem; color: var(--muted); min-width: 45px; }}
.item-dir {{ font-size: 0.75rem; min-width: 20px; }}
.item-dir.sent {{ color: var(--success); }}
.item-dir.recv {{ color: var(--accent); }}
.item-sender {{ font-weight: 600; font-size: 0.8rem; }}
.item-subject {{ font-size: 0.8rem; color: var(--text); flex: 1; }}
.item-badges {{ display: flex; gap: 3px; flex-wrap: wrap; }}
.badge {{ padding: 1px 6px; border-radius: 4px; font-size: 0.6rem; font-weight: 600; text-transform: uppercase; }}
.badge-email {{ background: #cce5ff; color: #004085; }}
.badge-chat {{ background: #fff3cd; color: #856404; }}
.badge-fwd {{ background: #e2e3e5; color: #383d41; }}
.badge-att {{ background: #d4edda; color: #155724; }}
.badge-flag {{ background: #f8d7da; color: #721c24; }}
.badge-exhibit {{ background: #d1ecf1; color: #0c5460; }}
.badge-cat {{ background: #e8daef; color: #6f42c1; }}
.item-actions {{ display: flex; gap: 5px; margin-left: auto; }}
.item-actions button {{ background: none; border: none; cursor: pointer; font-size: 1rem; opacity: 0.4; }}
.item-actions button:hover {{ opacity: 1; }}
.item-actions button.starred {{ opacity: 1; color: #f59e0b; }}

/* Expanded content */
.item-body {{ display: none; padding: 0 15px 15px; border-top: 1px solid var(--border); }}
.item-body.open {{ display: block; }}
.item-meta {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 8px; }}
.item-text {{ font-size: 0.82rem; white-space: pre-wrap; word-break: break-word;
              max-height: 400px; overflow-y: auto; padding: 10px; background: var(--bg);
              border-radius: 6px; margin: 8px 0; }}
.item-attachments {{ margin-top: 10px; }}
.att-item {{ display: flex; align-items: center; gap: 10px; padding: 5px 0;
             border-bottom: 1px solid var(--border); }}
.att-img {{ max-width: 200px; max-height: 150px; border-radius: 6px; cursor: pointer; }}
.att-text {{ font-size: 0.7rem; color: var(--muted); max-height: 100px; overflow-y: auto;
             padding: 5px; background: var(--bg); border-radius: 4px; margin-top: 5px; }}
.note-input {{ width: 100%; padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px;
               font-size: 0.8rem; margin-top: 8px; background: var(--bg); color: var(--text); }}
.notes-list {{ margin-top: 5px; }}
.note {{ font-size: 0.75rem; color: var(--muted); padding: 3px 0; border-bottom: 1px solid var(--border); }}

/* Lightbox */
.lightbox {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 1000;
             justify-content: center; align-items: center; cursor: pointer; }}
.lightbox.open {{ display: flex; }}
.lightbox img {{ max-width: 90vw; max-height: 90vh; object-fit: contain; }}
.lightbox-close {{ position: fixed; top: 15px; right: 20px; color: #fff; font-size: 2rem;
                   cursor: pointer; z-index: 1001; }}

/* Side panel */
.side-panel {{ position: fixed; right: -350px; top: 52px; width: 340px; height: calc(100vh - 52px);
               background: var(--card); border-left: 1px solid var(--border); z-index: 180;
               transition: right 0.2s; overflow-y: auto; padding: 15px; }}
.side-panel.open {{ right: 0; }}
.side-panel h3 {{ font-size: 0.95rem; margin-bottom: 10px; }}
.panel-tabs {{ display: flex; gap: 0; margin-bottom: 15px; }}
.panel-tab {{ flex: 1; padding: 8px; text-align: center; cursor: pointer; font-size: 0.8rem;
              border-bottom: 2px solid transparent; color: var(--muted); }}
.panel-tab.active {{ border-bottom-color: var(--accent); color: var(--accent); font-weight: 600; }}
.panel-item {{ padding: 8px; border-bottom: 1px solid var(--border); cursor: pointer; font-size: 0.75rem; }}
.panel-item:hover {{ background: var(--bg); }}

/* Stats */
.stats {{ display: flex; gap: 10px; padding: 10px 20px; flex-wrap: wrap; background: var(--card);
          border-bottom: 1px solid var(--border); }}
.stat {{ text-align: center; min-width: 80px; }}
.stat-num {{ font-size: 1.1rem; font-weight: 700; color: var(--accent); }}
.stat-label {{ font-size: 0.65rem; color: var(--muted); text-transform: uppercase; }}

/* Print */
@media print {{
  .header, .search-bar, .side-panel, .lightbox, .item-actions, .stats {{ display: none !important; }}
  .item-body {{ display: block !important; }}
  .item {{ break-inside: avoid; border: 1px solid #ccc; }}
  .date-header {{ position: static; break-before: page; }}
  body {{ background: #fff; }}
}}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>CasePulse Timeline</h1>
    <div class="meta">{html.escape(case_name)} | {date_start} to {date_end} | {total:,} items | Generated {datetime.now().strftime('%b %d, %Y %I:%M %p')}</div>
  </div>
  <div class="header-actions">
    <button onclick="toggleTheme()" title="Toggle dark/light">Theme</button>
    <button onclick="togglePanel()" title="Bookmarks & Notes">Bookmarks</button>
    <button onclick="expandAll()" title="Expand all">Expand All</button>
    <button onclick="collapseAll()" title="Collapse all">Collapse All</button>
    <button onclick="window.print()" title="Print">Print</button>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-num">{total:,}</div><div class="stat-label">Total</div></div>
  <div class="stat"><div class="stat-num">{email_count:,}</div><div class="stat-label">Emails</div></div>
  <div class="stat"><div class="stat-num">{chat_count:,}</div><div class="stat-label">Chats</div></div>
  <div class="stat"><div class="stat-num">{img_count}</div><div class="stat-label">Images</div></div>
</div>

<div class="search-bar">
  <input type="text" id="searchBox" placeholder="Search emails, chats, senders... (from: name, 2025-01, photos)" oninput="debounceSearch()">
  <div class="filter-chips">
    <span class="chip active" data-filter="all" onclick="setFilter('all')">All</span>
    <span class="chip" data-filter="email" onclick="setFilter('email')">Emails</span>
    <span class="chip" data-filter="chat" onclick="setFilter('chat')">Chats</span>
    <span class="chip" data-filter="sent" onclick="setFilter('sent')">Sent</span>
    <span class="chip" data-filter="received" onclick="setFilter('received')">Received</span>
    <span class="chip" data-filter="att" onclick="setFilter('att')">Attachments</span>
    <span class="chip" data-filter="bookmarked" onclick="setFilter('bookmarked')">Bookmarked</span>
  </div>
  <div class="search-count" id="searchCount">{total:,} items</div>
</div>

<div class="content" id="content"></div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close" onclick="closeLightbox()">&times;</span>
  <img id="lightboxImg" src="" alt="">
</div>

<div class="side-panel" id="sidePanel">
  <div class="panel-tabs">
    <div class="panel-tab active" onclick="showPanelTab('bookmarks')">Bookmarks</div>
    <div class="panel-tab" onclick="showPanelTab('notes')">Notes</div>
  </div>
  <div id="panelBookmarks"></div>
  <div id="panelNotes" style="display:none"></div>
</div>

<script>
const ITEMS = {items_json};
const INDEX = {index_json};

let currentFilter = 'all';
let searchTimeout = null;
let bookmarks = {{}};
let notes = {{}};

// Load saved state
try {{
  bookmarks = JSON.parse(localStorage.getItem('cp_bookmarks') || '{{}}');
  notes = JSON.parse(localStorage.getItem('cp_notes') || '{{}}');
}} catch(e) {{}}

function saveState() {{
  localStorage.setItem('cp_bookmarks', JSON.stringify(bookmarks));
  localStorage.setItem('cp_notes', JSON.stringify(notes));
}}

// Render
function render() {{
  const query = document.getElementById('searchBox').value.toLowerCase().trim();
  const container = document.getElementById('content');
  let html = '';
  let currentDate = '';
  let visibleCount = 0;

  for (let idx = 0; idx < ITEMS.length; idx++) {{
    const item = ITEMS[idx];
    const ix = INDEX[idx];

    // Filter
    if (currentFilter === 'email' && item.type !== 'email') continue;
    if (currentFilter === 'chat' && item.type !== 'chat') continue;
    if (currentFilter === 'sent' && item.direction !== 'sent') continue;
    if (currentFilter === 'received' && item.direction !== 'received') continue;
    if (currentFilter === 'att' && !item.has_attachments) continue;
    if (currentFilter === 'bookmarked' && !bookmarks[item.type + '_' + item.id]) continue;

    // Search
    if (query) {{
      if (query.startsWith('from:')) {{
        const sender = query.slice(5).trim();
        if (!ix.s.includes(sender)) continue;
      }} else {{
        if (!ix.t.includes(query) && !ix.s.includes(query) && !ix.d.includes(query)) continue;
      }}
    }}

    // Date header
    const itemDate = (item.timestamp || '').slice(0, 10);
    if (itemDate && itemDate !== currentDate) {{
      currentDate = itemDate;
      try {{
        const d = new Date(itemDate + 'T00:00:00');
        const label = d.toLocaleDateString('en-US', {{ weekday:'long', year:'numeric', month:'long', day:'numeric' }});
        html += '<div class="date-header">' + label + '</div>';
      }} catch(e) {{
        html += '<div class="date-header">' + itemDate + '</div>';
      }}
    }}

    const key = item.type + '_' + item.id;
    const isBookmarked = bookmarks[key];
    const time = (item.timestamp || '').slice(11, 16);
    const dirClass = item.direction === 'sent' ? 'sent' : 'recv';
    const dirIcon = item.direction === 'sent' ? '&rarr;' : item.direction === 'received' ? '&larr;' : '';
    const sender = item.sender_name || item.sender || '';
    const subject = item.subject || '';
    const body = escapeHtml(item.body || '');

    let badges = '';
    badges += '<span class="badge badge-' + item.type + '">' + item.type + '</span>';
    if (item.is_forwarded) badges += '<span class="badge badge-fwd">FWD</span>';
    if (item.has_attachments) badges += '<span class="badge badge-att">ATT</span>';
    if (item.exhibit) badges += '<span class="badge badge-exhibit">' + escapeHtml(item.exhibit) + '</span>';
    if (item.flag && item.flag !== 'none') badges += '<span class="badge badge-flag">' + escapeHtml(item.flag) + '</span>';
    if (item.categories && item.categories.length) badges += '<span class="badge badge-cat">' + escapeHtml(item.categories[0]) + '</span>';

    // Attachments HTML
    let attHtml = '';
    if (item.attachments && item.attachments.length) {{
      attHtml = '<div class="item-attachments"><strong>Attachments (' + item.attachments.length + '):</strong>';
      for (const att of item.attachments) {{
        attHtml += '<div class="att-item">';
        if (att.image) {{
          attHtml += '<img class="att-img" src="' + att.image + '" onclick="openLightbox(\\'' + att.image + '\\')" alt="' + escapeHtml(att.filename) + '">';
        }}
        const sizeKb = Math.round((att.size || 0) / 1024);
        attHtml += '<div><strong>' + escapeHtml(att.filename) + '</strong> (' + sizeKb + ' KB)';
        if (att.is_duplicate) attHtml += ' <em>(duplicate)</em>';
        if (att.text) attHtml += '<div class="att-text">' + escapeHtml(att.text.slice(0, 500)) + '</div>';
        attHtml += '</div></div>';
      }}
      attHtml += '</div>';
    }}

    // Notes
    let notesHtml = '';
    const itemNotes = notes[key] || [];
    if (itemNotes.length) {{
      notesHtml = '<div class="notes-list">';
      for (const n of itemNotes) notesHtml += '<div class="note">' + escapeHtml(n) + '</div>';
      notesHtml += '</div>';
    }}

    html += '<div class="item' + (isBookmarked ? ' bookmarked' : '') + '" id="item-' + idx + '">' +
      '<div class="item-header" onclick="toggleBody(' + idx + ')">' +
        '<div class="item-time">' + time + '</div>' +
        '<div class="item-dir ' + dirClass + '">' + dirIcon + '</div>' +
        '<div style="flex:1;min-width:0">' +
          '<div class="item-sender">' + escapeHtml(sender) + '</div>' +
          '<div class="item-subject">' + escapeHtml(subject).slice(0, 80) + '</div>' +
        '</div>' +
        '<div class="item-badges">' + badges + '</div>' +
        '<div class="item-actions">' +
          '<button class="' + (isBookmarked ? 'starred' : '') + '" onclick="event.stopPropagation();toggleBookmark(\\'' + key + '\\',' + idx + ')" title="Bookmark">&#9733;</button>' +
        '</div>' +
      '</div>' +
      '<div class="item-body" id="body-' + idx + '">' +
        '<div class="item-meta">' +
          'From: ' + escapeHtml(item.sender) + ' | Mailbox: ' + escapeHtml(item.mailbox) +
          (item.original_sender ? ' | Originally from: ' + escapeHtml(item.original_sender) : '') +
        '</div>' +
        '<div class="item-text">' + body + '</div>' +
        attHtml + notesHtml +
        '<input class="note-input" placeholder="Add a note..." onkeydown="if(event.key===\\'Enter\\')addNote(\\'' + key + '\\',this,' + idx + ')">' +
      '</div>' +
    '</div>';

    visibleCount++;
  }}

  container.innerHTML = html || '<div style="text-align:center;padding:50px;color:var(--muted)">No items match your search.</div>';
  document.getElementById('searchCount').textContent = visibleCount.toLocaleString() + ' items';
}}

function toggleBody(idx) {{
  const el = document.getElementById('body-' + idx);
  if (el) el.classList.toggle('open');
}}

function expandAll() {{
  document.querySelectorAll('.item-body').forEach(el => el.classList.add('open'));
}}

function collapseAll() {{
  document.querySelectorAll('.item-body').forEach(el => el.classList.remove('open'));
}}

function toggleBookmark(key, idx) {{
  if (bookmarks[key]) delete bookmarks[key];
  else {{
    const item = ITEMS[idx];
    bookmarks[key] = {{ sender: item.sender, subject: item.subject, time: item.timestamp }};
  }}
  saveState();
  render();
  updatePanel();
}}

function addNote(key, input, idx) {{
  const text = input.value.trim();
  if (!text) return;
  if (!notes[key]) notes[key] = [];
  notes[key].push(text);
  input.value = '';
  saveState();
  render();
  updatePanel();
}}

function setFilter(f) {{
  currentFilter = f;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  document.querySelector('.chip[data-filter="' + f + '"]').classList.add('active');
  render();
}}

function debounceSearch() {{
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(render, 200);
}}

function openLightbox(src) {{
  document.getElementById('lightboxImg').src = src;
  document.getElementById('lightbox').classList.add('open');
}}

function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('open');
}}

function toggleTheme() {{
  const current = document.body.getAttribute('data-theme');
  document.body.setAttribute('data-theme', current === 'dark' ? '' : 'dark');
}}

function togglePanel() {{
  document.getElementById('sidePanel').classList.toggle('open');
  updatePanel();
}}

function showPanelTab(tab) {{
  document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('panelBookmarks').style.display = tab === 'bookmarks' ? 'block' : 'none';
  document.getElementById('panelNotes').style.display = tab === 'notes' ? 'block' : 'none';
}}

function updatePanel() {{
  let bHtml = '<h3>Bookmarks (' + Object.keys(bookmarks).length + ')</h3>';
  for (const [key, bm] of Object.entries(bookmarks)) {{
    bHtml += '<div class="panel-item" onclick="scrollToKey(\\'' + key + '\\')">' +
      '<strong>' + escapeHtml(bm.sender || '') + '</strong><br>' +
      escapeHtml((bm.subject || '').slice(0, 50)) + '<br>' +
      '<span style="color:var(--muted)">' + (bm.time || '').slice(0, 16) + '</span></div>';
  }}
  document.getElementById('panelBookmarks').innerHTML = bHtml;

  let nHtml = '<h3>Notes (' + Object.keys(notes).length + ')</h3>';
  for (const [key, noteList] of Object.entries(notes)) {{
    for (const n of noteList) {{
      nHtml += '<div class="panel-item" onclick="scrollToKey(\\'' + key + '\\')">' +
        escapeHtml(n) + '<br><span style="color:var(--muted)">' + key + '</span></div>';
    }}
  }}
  document.getElementById('panelNotes').innerHTML = nHtml;
}}

function scrollToKey(key) {{
  const parts = key.split('_');
  const type = parts[0];
  const id = parseInt(parts[1]);
  for (let i = 0; i < ITEMS.length; i++) {{
    if (ITEMS[i].type === type && ITEMS[i].id === id) {{
      const el = document.getElementById('item-' + i);
      if (el) {{
        el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        el.classList.add('highlighted');
        setTimeout(() => el.classList.remove('highlighted'), 2000);
        const body = document.getElementById('body-' + i);
        if (body) body.classList.add('open');
      }}
      break;
    }}
  }}
}}

function escapeHtml(str) {{
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
            .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

// Initial render
render();
updatePanel();
</script>
</body>
</html>"""

    html_path = out / "timeline.html"
    html_path.write_text(page, encoding="utf-8")

    if progress_cb:
        progress_cb(f"Done! {total:,} items, {img_count} images → {html_path}")

    return {
        "total_items": total,
        "total_emails": email_count,
        "total_chats": chat_count,
        "total_images": img_count,
        "html_path": str(html_path),
        "output_dir": output_dir,
        "file_size": html_path.stat().st_size,
    }
