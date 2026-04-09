"""Ask page — RAG-powered chat interface for querying emails."""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Ask", page_icon="CP", layout="wide")

st.markdown("## Ask CasePulse")
st.markdown("Query your emails with AI. Answers include exact citations — zero hallucination.")


from components.page_init import init_page
db, config = init_page()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "index_built" not in st.session_state:
    st.session_state.index_built = False

stats = db.get_stats()
if stats["total_emails"] == 0:
    st.info("No emails collected yet. Go to **Fetch Emails** first.")
    st.stop()

# ── Sidebar: Index Status & Controls ──
with st.sidebar:
    st.markdown("### RAG Index")

    from casepulse.rag.vectorstore import VectorStore
    vs = VectorStore()
    chunk_count = 0
    try:
        chunk_count = vs.get_count()
    except Exception:
        pass

    if chunk_count > 0:
        st.success(f"Index ready: {chunk_count:,} chunks")
        st.session_state.index_built = True
    else:
        st.warning("Index not built yet")

    if st.button("Build / Rebuild Index", type="primary"):
        with st.status("Building RAG index...", expanded=True) as status:
            try:
                from casepulse.rag.embedder import LocalEmbedder
                from casepulse.rag.query_engine import build_index

                embedder = LocalEmbedder(model_name=config.get("embedding.model", "all-MiniLM-L6-v2"))

                total = build_index(
                    db, embedder, vs,
                    chunk_size=config.get("rag.chunk_size", 500),
                    chunk_overlap=config.get("rag.chunk_overlap", 50),
                    progress_cb=lambda msg: st.write(msg),
                )

                status.update(label=f"Index built: {total} chunks", state="complete")
                st.session_state.index_built = True

            except Exception as e:
                status.update(label="Index build failed", state="error")
                st.error(f"Error building index: {str(e)}")

    st.divider()

    st.markdown("### LLM Provider")
    provider = config.llm_provider
    model = config.llm_model

    if provider == "ollama":
        st.markdown(f"**Ollama** — `{model}`")
        # Check if Ollama is running
        from casepulse.llm.ollama_provider import OllamaProvider
        ollama_prov = OllamaProvider(model=model)
        if ollama_prov.is_available():
            st.success("Ollama is running")
            models = ollama_prov.list_models()
            if models:
                selected_model = st.selectbox("Model", models, index=models.index(model) if model in models else 0)
                if selected_model != model:
                    config.set("llm.model", selected_model)
        else:
            st.error("Ollama is not running")
            st.markdown("Start it with: `ollama serve`")
            st.markdown("Then pull a model: `ollama pull llama3.1:8b`")
    else:
        st.markdown(f"**{provider.title()}** — `{model}`")
        if config.llm_api_key:
            st.success("API key configured")
        else:
            st.error("No API key set — configure in Home > Settings")

    st.divider()
    st.markdown("### Query Options")
    top_k = st.slider("Chunks to retrieve", 5, 30, 10, key="ask_top_k")

    # Sender filter for queries
    senders = db.get_senders(selected_only=True)
    sender_options = ["All senders"] + [s["email"] for s in senders]
    query_sender = st.selectbox("Filter by sender", sender_options, key="ask_sender")

    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()

# ── Main Chat Area ──
if not st.session_state.index_built:
    st.warning("Build the RAG index first (button in sidebar) to start querying.")
    st.stop()

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show sources for assistant messages
        if msg["role"] == "assistant" and "sources" in msg:
            with st.expander(f"Sources ({len(msg['sources'])} chunks used)"):
                for i, source in enumerate(msg["sources"]):
                    meta = source.get("metadata", {})
                    relevance = source.get("relevance_score", 0)
                    st.markdown(
                        f"**[{i+1}]** {meta.get('sender', '?')} — "
                        f"{meta.get('date', '?')[:10]} — "
                        f"\"{meta.get('subject', '?')}\" "
                        f"(relevance: {relevance:.2f})"
                    )
                    source_type = meta.get("type", "email")
                    if source_type == "attachment":
                        st.caption(f"From attachment: {meta.get('filename', '?')}")

# Check for pending query from Quick Query buttons
pending_query = st.session_state.pop("pending_query", None)

# Chat input
prompt = st.chat_input("Ask about your emails... (e.g., 'What settlement offers were discussed?')")

# Use pending query if no direct input
if not prompt and pending_query:
    prompt = pending_query

if prompt:
    # Add user message if not already in history (pending queries are pre-added)
    if not pending_query:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Searching emails and generating answer..."):
            try:
                from casepulse.rag.embedder import LocalEmbedder
                from casepulse.rag.query_engine import QueryEngine
                from casepulse.llm.api_provider import create_provider

                embedder = LocalEmbedder(
                    model_name=config.get("embedding.model", "all-MiniLM-L6-v2")
                )

                llm = create_provider(
                    config.llm_provider,
                    model=config.llm_model,
                    api_key=config.llm_api_key,
                    base_url=config.llm_base_url,
                )

                engine = QueryEngine(llm, embedder, vs)

                sender_filter = None if query_sender == "All senders" else query_sender

                result = engine.query(
                    question=prompt,
                    top_k=top_k,
                    sender_filter=sender_filter,
                )

                answer = result["answer"]
                sources = result["sources"]

                st.markdown(answer)

                # Show sources
                if sources:
                    with st.expander(f"Sources ({len(sources)} chunks used)"):
                        for i, source in enumerate(sources):
                            meta = source.get("metadata", {})
                            relevance = source.get("relevance_score", 0)
                            st.markdown(
                                f"**[{i+1}]** {meta.get('sender', '?')} — "
                                f"{meta.get('date', '?')[:10]} — "
                                f"\"{meta.get('subject', '?')}\" "
                                f"(relevance: {relevance:.2f})"
                            )

                # Save to history
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })

            except Exception as e:
                error_msg = f"Error generating answer: {str(e)}"
                st.error(error_msg)

                # Helpful error messages
                if "ollama" in str(e).lower() or "connection" in str(e).lower():
                    st.info("Is Ollama running? Start it with: `ollama serve`")
                elif "api_key" in str(e).lower() or "authentication" in str(e).lower():
                    st.info("Check your API key in Home > Settings")

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": error_msg,
                })

# ── Quick Query Templates ──
st.divider()
st.markdown("### Quick Queries")
st.markdown("Click a template to start:")

col1, col2 = st.columns(2)
with col1:
    templates_left = [
        "Create a timeline of all settlement discussions",
        "What agreements were reached and when?",
        "Summarize all communication from opposing counsel",
        "List all mentions of custody or visitation",
        "What financial matters were discussed?",
    ]
    for t in templates_left:
        if st.button(t, key=f"tmpl_{t[:20]}"):
            st.session_state.chat_history.append({"role": "user", "content": t})
            st.session_state["pending_query"] = t
            st.rerun()

with col2:
    templates_right = [
        "What deadlines or court dates were mentioned?",
        "Summarize communication from CAS/child services",
        "List all attached documents and their contents",
        "What did the therapist report?",
        "Find any contradictions between parties' statements",
    ]
    for t in templates_right:
        if st.button(t, key=f"tmpl_{t[:20]}"):
            st.session_state.chat_history.append({"role": "user", "content": t})
            st.session_state["pending_query"] = t
            st.rerun()
