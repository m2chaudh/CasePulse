# CasePulse Resume Note — after ChatVault overhaul

**Written:** 2026-05-03 (during a long ChatVault session that started in CasePulse and pivoted)

## TL;DR

ChatVault was massively upgraded today — it now handles AppClose end-to-end (PDF parser, image extraction, corporate skin, CLI + GUI) on top of its existing WhatsApp support. That **obsoletes some previously-deferred CasePulse work** and **shifts priorities** for the next CasePulse session.

## What's NEW about ChatVault you should know

The ChatVault repo at `/Users/mani/Dev/Mobile Apps/ChatVault` (now on `main`, 30 commits past the pre-session state):

- ✅ AppClose PDF support: `chatvault appclose ./Conversations.pdf -o ./out` produces a clean HTML viewer with all 139 images inlined chronologically
- ✅ Same v2 sender-normalisation logic that was prototyped in CasePulse — ported and improved
- ✅ Corporate "Legal Brief" skin (white bg, serif, monospace metadata, per-bubble Sent + Viewed-by + SRC: page footer)
- ✅ GUI wizard 4th branch for AppClose
- ✅ Multi-attachment messages render all images (the legacy single-attachment limitation is fixed)
- ✅ Fresh macOS DMG built and bundles the new modules + static/ correctly
- ✅ 48/48 tests pass; sender-bleed regression assertion in place

## CasePulse — current state

Branch: `feat/case-binder-phase-a` (still active; not yet merged to main)

Most recent commits (from this session + earlier):
- `4b2416e` fix(binder): inline PDF viewer for documents + Blob URL for large PDFs (this session)
- `1e82e5f` fix(binder): attachment dates + SQL date format mismatch
- `3f96997` feat(binder): chat messages render as inline bubble cluster, not pop-out rows
- `8a7c8da` fix(binder): re-render calendar when month/week changes
- `6c08f37` fix(appclose-parser): single-line header regex + two-pass sender normalisation
- `2dd36db` feat(repairs): AppClose v2 parser + dry-run preview UI
- `0d62570` feat(repairs): Data Repairs page with sample preview + Apply for chat migrations
- `8b57d77` feat(chats): repair migration for AppClose PDF-export boilerplate

Tests: 256/256 pass.

## What's deferred / pending for CasePulse

### Pre-built but not yet applied (just need user clicks)

1. **WhatsApp bundle repair migration** — Data Repairs page has the Apply button. Splits 90 bundle parents into 122 sub-message rows. Idempotent.
2. **AppClose boilerplate cleanup migration** — Data Repairs page Apply button. Strips page footers, repeated timestamps, attachment listings from 134 chat rows. Idempotent.

Both are low-risk, self-rollback-able (the page offers a "Backup DB first" checkbox).

### Not yet built — DECISION POINT

3. **AppClose v2-apply migration** — would rewrite `chat_messages` rows from the v2 parser output (cleaning the May 4, 2025 sender-bleed mess at the data level). 

   **This was deferred earlier; now there's a question.** Given ChatVault now handles AppClose viewing end-to-end with much higher fidelity, do we still need to clean the data in CasePulse's `chat_messages`?

   **Pros of applying it in CasePulse:**
   - Calendar / timeline / RAG / search indexes `chat_messages` directly. Dirty senders ('2025 Manish Chaudhary' etc.) break those features even if the Open dialog points elsewhere.
   - The data is legal evidence. Court-grade accuracy matters.
   - Migration logic is small and idempotent.

   **Cons:**
   - The user can already get a clean view via ChatVault.
   - The migration writes to `chat_messages` — slightly destructive (with backup).
   - Depends on which features matter: if calendar/timeline/RAG correctness is required, apply; if not, skip.

   **My recommendation:** apply. The bad senders show up in the calendar's day drawer, year-view counts, RAG search results, and chip filters — not just the message Open dialog. ChatVault is for VIEWING; CasePulse needs the underlying data clean too.

### Originally planned, NOW PARTIALLY OBSOLETED by ChatVault

4. **Spec A — ChatVault HTML integration (originally WA-only)**
   - Setup-page section: register N ChatVault exports (folder with `index.html` + `media/`)
   - Symlink each into `./static/chatvault/<name>/` so Streamlit serves them
   - One-time indexer: parse the HTML, match each `msg-N` anchor to `chat_messages` by (timestamp, sender, body prefix), store anchor in a sidecar table
   - Day-drawer bubble cluster gets a "View in ChatVault →" header link + per-message "↗" anchor links
   - Re-index button when an export is regenerated

   **What changed:** This was previously WhatsApp-only. Now it should support BOTH WhatsApp and AppClose ChatVault exports — same registration UI, same indexer, same deep-link mechanism. The user produces ChatVault output for either platform via `chatvault appclose <pdf>` or the WhatsApp pipeline, then registers the output in CasePulse.

5. **Spec B — AppClose corporate viewer in CasePulse — OBSOLETED**
   - The plan was to build an AppClose-specific HTML viewer inside CasePulse with the corporate skin.
   - **ChatVault now does this.** Spec B is no longer needed; CasePulse should just integrate via Spec A and let ChatVault handle the rendering.

6. **Backfill `parent_email_id` via Message-ID/In-Reply-To headers** — mentioned earlier, never built. Independent of ChatVault. Lower priority.

## Recommended priority order for next session

1. **Apply the two pre-built data repair migrations** (5 min, just clicks on Data Repairs page) — this is free quality wins.
2. **Decide on AppClose v2-apply migration** — if yes, build it (~half day work).
3. **Build Spec A (ChatVault integration), expanded to BOTH platforms** (~1 day):
   - Setup-page UI
   - Symlink + index logic
   - Day-drawer "View in ChatVault →" buttons
   - Test on both Manisha (WhatsApp) and AppClose Conversations exports
4. Consider merging `feat/case-binder-phase-a` to main once these settle. Phase A has been live for weeks; the branch is unhealthy long-running.

## Copy-pastable resume prompt

When you start a new CasePulse session, paste this:

```
Resume CasePulse work after the 2026-05-03 ChatVault overhaul.

Read the full state notes in docs/superpowers/RESUME-2026-05-03-after-chatvault-overhaul.md.

Current branch: feat/case-binder-phase-a (256/256 tests pass, last commit 4b2416e).
ChatVault upstream is at /Users/mani/Dev/Mobile Apps/ChatVault on `main` (tags step1-complete, step2-complete) with full WhatsApp + AppClose support.

Three things to consider, in this order:
  1. Apply the WhatsApp bundle repair + AppClose boilerplate cleanup migrations (Data Repairs page, both ready to click; backup-first checkbox available)
  2. Decide whether to build the AppClose v2-apply migration (rewrites chat_messages from v2 parser output — cleans the May 4 sender bleed and others). My recommendation: yes, because calendar/timeline/RAG read chat_messages directly.
  3. Build the ChatVault HTML integration (Spec A from earlier brainstorm), but expand scope to handle both WhatsApp AND AppClose ChatVault exports — Spec B (in-CasePulse AppClose viewer) is now obsolete since ChatVault does this.

Don't pre-suppose any of those. Ask which I want to tackle first.
```

## Things NOT to do without re-discussing

- **Don't blindly apply the AppClose v2-apply migration** — it rewrites `chat_messages` rows. Backup-first checkbox available; user should review the dry-run preview before clicking.
- **Don't merge `feat/case-binder-phase-a` to main** without a final review pass and the user's explicit nod. The branch has been ahead for many sessions.
- **Don't re-build Spec B (in-CasePulse AppClose viewer)** — it's obsolete. ChatVault handles it. If anything, the integration is the right path.
