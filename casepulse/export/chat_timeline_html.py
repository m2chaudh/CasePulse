"""Chat Timeline HTML export — WhatsApp + AppClose with inline images, printable."""
from __future__ import annotations

import html
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from casepulse.storage.database import Database


def build_chat_timeline_html(db: Database, output_dir: str,
                              case_name: str = "",
                              date_start: str = "", date_end: str = "",
                              include_images: bool = True,
                              progress_cb=None) -> dict:
    """Build an HTML chat timeline with inline images.

    Creates:
    - chat_timeline.html — self-contained printable HTML
    - images/ — copied chat media files
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / "images"
    img_dir.mkdir(exist_ok=True)

    # Get all chat messages
    messages = db.get_chat_messages(
        date_start=date_start, date_end=date_end,
        include_system=False, limit=500000,
    )

    if progress_cb:
        progress_cb(f"Found {len(messages):,} chat messages")

    # Group by chat/platform
    chats = {}
    for m in messages:
        key = f"{m.get('platform', 'chat')}_{m.get('chat_name', 'unknown')}"
        if key not in chats:
            chats[key] = {
                "platform": m.get("platform", ""),
                "chat_name": m.get("chat_name", ""),
                "messages": [],
            }
        chats[key]["messages"].append(m)

    # Copy images and build path map
    img_count = 0
    img_map = {}  # original path → relative path in export
    if include_images:
        if progress_cb:
            progress_cb("Copying images...")
        for m in messages:
            media_path = m.get("media_path", "")
            if media_path and Path(media_path).exists():
                ext = Path(media_path).suffix.lower()
                if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                    dst_name = f"img_{m['id']}{ext}"
                    dst = img_dir / dst_name
                    if not dst.exists():
                        try:
                            shutil.copy2(media_path, str(dst))
                            img_count += 1
                        except Exception:
                            pass
                    img_map[media_path] = f"images/{dst_name}"

    if progress_cb:
        progress_cb(f"Copied {img_count} images")

    # Build HTML
    total_msgs = len(messages)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chat Timeline — {html.escape(case_name)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f5f5; color: #222; line-height: 1.5; }}

  .header {{ background: #1a1a2e; color: #fff; padding: 20px 30px; }}
  .header h1 {{ font-size: 1.4rem; font-weight: 600; }}
  .header .meta {{ color: #adb5bd; font-size: 0.85rem; margin-top: 5px; }}

  .nav {{ background: #fff; border-bottom: 2px solid #dee2e6; padding: 10px 30px;
          position: sticky; top: 0; z-index: 100; }}
  .nav a {{ margin-right: 15px; color: #0d6efd; text-decoration: none; font-size: 0.85rem; }}
  .nav a:hover {{ text-decoration: underline; }}

  .content {{ max-width: 900px; margin: 0 auto; padding: 20px; }}

  .date-header {{ background: #e9ecef; padding: 8px 15px; border-radius: 8px;
                  font-weight: 600; font-size: 0.9rem; margin: 20px 0 10px; color: #495057;
                  position: sticky; top: 45px; z-index: 50; }}

  .chat-section {{ margin-bottom: 30px; }}
  .chat-title {{ font-size: 1.1rem; font-weight: 700; padding: 12px 15px;
                 background: #d1ecf1; border-radius: 8px; margin-bottom: 15px; }}

  .msg {{ display: flex; margin-bottom: 8px; gap: 10px; }}
  .msg-time {{ font-size: 0.7rem; color: #6c757d; min-width: 45px; padding-top: 4px; }}
  .msg-bubble {{ max-width: 80%; padding: 8px 12px; border-radius: 12px; font-size: 0.85rem; }}

  .msg-sent .msg-bubble {{ background: #d4edda; margin-left: auto; border-bottom-right-radius: 4px; }}
  .msg-recv .msg-bubble {{ background: #fff; border: 1px solid #dee2e6; border-bottom-left-radius: 4px; }}
  .msg-system .msg-bubble {{ background: #fff3cd; margin: 0 auto; text-align: center;
                             font-size: 0.75rem; color: #856404; }}

  .msg-sender {{ font-weight: 600; font-size: 0.75rem; color: #0d6efd; margin-bottom: 2px; }}
  .msg-media {{ max-width: 300px; border-radius: 8px; margin-top: 5px; cursor: pointer; }}
  .msg-media:hover {{ opacity: 0.9; }}

  .stats {{ display: flex; gap: 15px; flex-wrap: wrap; padding: 15px 0; }}
  .stat {{ background: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 10px 18px; }}
  .stat-num {{ font-size: 1.3rem; font-weight: 700; color: #0d6efd; }}
  .stat-label {{ font-size: 0.7rem; color: #6c757d; text-transform: uppercase; }}

  @media print {{
    .nav {{ display: none; }}
    .date-header {{ position: static; }}
    .msg-media {{ max-width: 200px; }}
    body {{ background: #fff; }}
    .content {{ max-width: 100%; }}
  }}

  @media (max-width: 600px) {{
    .msg-bubble {{ max-width: 90%; }}
    .content {{ padding: 10px; }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>Chat Timeline — {html.escape(case_name)}</h1>
  <div class="meta">
    Date Range: {date_start} to {date_end} |
    Messages: {total_msgs:,} |
    Chats: {len(chats)} |
    Images: {img_count} |
    Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
  </div>
</div>

<div class="nav" id="top">
  <strong>Jump to:</strong>
"""

    # Navigation links — one per chat
    for key, chat in chats.items():
        anchor = key.replace(" ", "_").replace("@", "_")
        page += f'  <a href="#{anchor}">{html.escape(chat["chat_name"])} ({chat["platform"]})</a>\n'

    page += '</div>\n<div class="content">\n'

    # Stats
    page += '<div class="stats">\n'
    page += f'  <div class="stat"><div class="stat-num">{total_msgs:,}</div><div class="stat-label">Messages</div></div>\n'
    page += f'  <div class="stat"><div class="stat-num">{len(chats)}</div><div class="stat-label">Conversations</div></div>\n'
    page += f'  <div class="stat"><div class="stat-num">{img_count}</div><div class="stat-label">Images</div></div>\n'

    # Count unique senders
    unique_senders = set(m.get("sender", "") for m in messages if m.get("sender"))
    page += f'  <div class="stat"><div class="stat-num">{len(unique_senders)}</div><div class="stat-label">Participants</div></div>\n'
    page += '</div>\n'

    # Determine which senders are "me"
    my_accounts = set(a["email"].lower() for a in db.get_accounts())
    my_names = {"Manish Chaudhary", "Mani Chaudhary", "Manish", "Mani",
                "manish chaudhary", "mani chaudhary"}

    # Render each chat
    for key, chat in chats.items():
        anchor = key.replace(" ", "_").replace("@", "_")
        if progress_cb:
            progress_cb(f"Rendering {chat['chat_name']} ({len(chat['messages']):,} messages)...")

        page += f'<div class="chat-section" id="{anchor}">\n'
        page += f'<div class="chat-title">{html.escape(chat["chat_name"])} — {html.escape(chat["platform"])} ({len(chat["messages"]):,} messages)</div>\n'

        current_date = ""

        for m in chat["messages"]:
            ts = m.get("timestamp", "") or ""
            msg_date = ts[:10]
            msg_time = ts[11:16] if len(ts) > 11 else ""
            sender = m.get("sender", "")
            text = m.get("message_text", "") or ""
            media_path = m.get("media_path", "")

            # Date separator
            if msg_date and msg_date != current_date:
                current_date = msg_date
                try:
                    date_label = datetime.strptime(msg_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")
                except ValueError:
                    date_label = msg_date
                page += f'<div class="date-header">{date_label}</div>\n'

            # Determine if sent or received
            is_me = sender.lower() in my_accounts or sender in my_names or sender.lower() in {n.lower() for n in my_names}
            css_class = "msg-sent" if is_me else "msg-recv"
            if m.get("is_system"):
                css_class = "msg-system"

            page += f'<div class="msg {css_class}">\n'
            page += f'  <div class="msg-time">{msg_time}</div>\n'
            page += f'  <div class="msg-bubble">\n'

            if not m.get("is_system"):
                page += f'    <div class="msg-sender">{html.escape(sender)}</div>\n'

            # Message text
            if text:
                escaped_text = html.escape(text).replace("\n", "<br>")
                page += f'    <div>{escaped_text}</div>\n'

            # Inline image
            if media_path and media_path in img_map:
                rel_path = img_map[media_path]
                page += f'    <img class="msg-media" src="{rel_path}" alt="Media" onclick="window.open(this.src)">\n'
            elif m.get("has_media") and not text:
                page += '    <div style="color:#6c757d;font-style:italic;">[Media omitted]</div>\n'

            page += '  </div>\n</div>\n'

        page += '</div>\n'
        page += '<div style="text-align:center;margin:20px;"><a href="#top">Back to top</a></div>\n'

    page += '</div>\n'

    # Footer
    page += f"""
<div style="text-align:center;padding:30px;color:#6c757d;font-size:0.8rem;border-top:1px solid #dee2e6;margin-top:30px;">
  Generated by CasePulse — {datetime.now().strftime('%Y-%m-%d %H:%M')} — {total_msgs:,} messages
</div>
</body>
</html>"""

    # Write HTML
    html_path = out / "chat_timeline.html"
    html_path.write_text(page, encoding="utf-8")

    if progress_cb:
        progress_cb(f"Done! {total_msgs:,} messages, {img_count} images → {html_path}")

    return {
        "total_messages": total_msgs,
        "total_images": img_count,
        "total_chats": len(chats),
        "html_path": str(html_path),
        "output_dir": output_dir,
    }
