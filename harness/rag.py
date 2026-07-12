"""
Inspiration corpus retrieval (RAG).

Users drop sample games / reference docs into <project>/inspiration/<source>/.
This module chunks text files, embeds each chunk via Ollama's embeddings API,
stores vectors in .harness/cache/inspiration_index.json, and retrieves the
top-k most relevant chunks for a given query at generate time.

Image files (.png/.jpg/.jpeg/.webp/.gif) are indexed via their filename and an
optional sidecar .caption.txt or .txt with the same stem — the caption text is
what gets embedded. The harness never opens binary image data.

Design choices:
  - Plain JSON index keeps everything local + grep-able + git-friendly (cache
    is gitignored anyway).
  - Cosine similarity in numpy-free pure python — fine for <10k chunks.
  - One round-trip per chunk during indexing. Use a small embed model
    (nomic-embed-text @ 137M params, ~80MB) so indexing 200 chunks stays under
    20 seconds on CPU.
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from typing import Any

import httpx

from .models import HarnessConfig
from .project import ProjectPaths


# ── Constants ─────────────────────────────────────────────────────────────────

TEXT_EXTENSIONS = {".tw", ".twee", ".md", ".txt", ".rst"}
JSON_EXTENSIONS = {".json"}   # parsed-sugarcube reports from the html-parser sister project
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
CAPTION_EXTENSIONS = {".caption.txt", ".txt"}

DEFAULT_EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 800             # characters per chunk
CHUNK_OVERLAP = 100          # characters of overlap between chunks
MAX_CHUNKS_PER_FILE = 200    # safety cap; massive files get truncated


# ── Paths ─────────────────────────────────────────────────────────────────────

def inspiration_dir(p: ProjectPaths) -> Path:
    return p.root / "inspiration"


def index_path(p: ProjectPaths) -> Path:
    return p.cache_dir / "inspiration_index.json"


def story_index_path(p: ProjectPaths) -> Path:
    return p.cache_dir / "story_index.json"


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Naive sliding-window chunker. Splits on paragraph boundaries when possible."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n and len(chunks) < MAX_CHUNKS_PER_FILE:
        end = min(start + size, n)
        # back off to the nearest paragraph or sentence boundary
        if end < n:
            window = text[start:end]
            split = max(
                window.rfind("\n\n"),
                window.rfind(". "),
                window.rfind("! "),
                window.rfind("? "),
            )
            if split > size // 2:
                end = start + split + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _strip_twee_syntax(text: str) -> str:
    """Light cleanup for .tw/.twee files: drop SugarCube macros + link markup."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'<<[^>]+>>', '', text)
    text = re.sub(r'\[\[([^\|\]]+)\|[^\]]+\]\]', r'\1', text)  # keep choice text
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    return text


# Frontmatter: tolerate missing trailing newline after the closing `---`.
_FRONTMATTER_RE = re.compile(r'^---\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)', re.DOTALL)
_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.MULTILINE)
_TWEE_PASSAGE_RE = re.compile(r'^::\s*([^\[\n]+?)(?:\s*\[([^\]]*)\])?\s*$', re.MULTILINE)

# Frontmatter fields whose bracketed value should be parsed as a YAML list.
# Anything else with `[…]` is kept as a literal string (e.g. an arc id).
_LIST_VALUED_FM_KEYS = frozenset({"tags", "keywords", "aliases", "alts", "labels"})


def _extract_text_metadata(raw: str, source_rel: str) -> tuple[str, dict, str]:
    """
    Return (body_after_frontmatter, metadata_dict, header_line).
    metadata_dict carries title/tags/arc/passages — all optional.
    header_line is prepended to each chunk's embed text for richer semantics.
    """
    body = raw
    meta: dict = {}

    fm = _FRONTMATTER_RE.match(raw)
    if fm:
        fm_text = fm.group(1)
        body = raw[fm.end():]
        # Lightweight YAML parse — only top-level scalars and simple lists.
        for line in fm_text.splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if not key:
                continue
            if key in _LIST_VALUED_FM_KEYS and val.startswith("[") and val.endswith("]"):
                meta[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            elif val:
                meta[key] = val.strip("'\"")

    if "title" not in meta:
        head = _HEADING_RE.search(body)
        if head:
            meta["title"] = head.group(2)

    # Arc inferred from filename path components when not declared.
    if "arc" not in meta:
        parts = source_rel.replace("\\", "/").split("/")
        if "arcs" in parts:
            idx = parts.index("arcs")
            if idx + 1 < len(parts):
                meta["arc"] = parts[idx + 1]
        elif "inspiration" in parts:
            idx = parts.index("inspiration")
            if idx + 1 < len(parts) and idx + 2 < len(parts):
                meta["arc"] = parts[idx + 1]

    # .tw / .twee: harvest :: passage names so each chunk can surface them.
    passages: list[str] = []
    if source_rel.endswith((".tw", ".twee")):
        passages = [m.group(1).strip() for m in _TWEE_PASSAGE_RE.finditer(raw)]
        if passages:
            meta["passages"] = passages[:20]

    # Header prepended to embed text. Empty when no metadata recovered.
    bits: list[str] = []
    if meta.get("title"):
        bits.append(f"[{meta['title']}]")
    if meta.get("arc"):
        bits.append(f"arc:{meta['arc']}")
    if meta.get("tags"):
        tags = meta["tags"] if isinstance(meta["tags"], list) else [meta["tags"]]
        bits.append("tags:" + ",".join(tags[:6]))
    header_line = " ".join(bits)
    return body.strip(), meta, header_line


# ── Embeddings ────────────────────────────────────────────────────────────────

async def _embed(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    text: str,
) -> list[float]:
    url = f"{base_url.rstrip('/')}/api/embeddings"
    resp = await client.post(url, json={"model": model, "prompt": text})
    resp.raise_for_status()
    data = resp.json()
    return data.get("embedding") or data.get("embeddings", [[]])[0]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── Discovery ─────────────────────────────────────────────────────────────────

def _discover_files(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Return (text_files, json_reports, image_files) under inspiration root."""
    text_files: list[Path] = []
    json_reports: list[Path] = []
    image_files: list[Path] = []
    if not root.exists():
        return text_files, json_reports, image_files
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        # Skip caption sidecars — they're loaded via _caption_for_image, not indexed alone.
        if f.name.endswith(".caption.txt"):
            continue
        suffix = f.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            text_files.append(f)
        elif suffix in JSON_EXTENSIONS:
            json_reports.append(f)
        elif suffix in IMAGE_EXTENSIONS:
            image_files.append(f)
    return text_files, json_reports, image_files


def _passages_from_report(report: dict) -> list[dict]:
    """
    Detect the html-parser sister project's report schema and yield per-passage
    chunks. Returns [] if the JSON doesn't look like that schema.
    Schema: {"passages": [{"name", "tags", "text", "media": [{"type","src","alt"}]}]}
    """
    if not isinstance(report, dict) or not isinstance(report.get("passages"), list):
        return []
    title = str(report.get("title") or "")
    out: list[dict] = []
    for p in report["passages"]:
        if not isinstance(p, dict):
            continue
        text = (p.get("text") or "").strip()
        if not text:
            continue
        media = p.get("media") or []
        media_summary = []
        for m in media:
            if not isinstance(m, dict):
                continue
            kind = m.get("type") or m.get("tag") or "media"
            src = m.get("src") or m.get("poster") or ""
            alt = m.get("alt") or m.get("title") or ""
            media_summary.append(f"[{kind}] {alt or src}".strip())
        name = p.get("name") or "passage"
        tags = " ".join(p.get("tags") or [])
        # Prepend context so embeddings carry passage-level metadata.
        header = f"[{title} :: {name}]"
        if tags:
            header += f" tags: {tags}"
        if media_summary:
            header += " | media: " + "; ".join(media_summary[:4])
        out.append({
            "name": name,
            "title": title,
            "text": f"{header}\n\n{text}",
            "media": media_summary,
        })
    return out


def _caption_for_image(img: Path) -> str:
    """Look for a sidecar caption file next to the image."""
    for ext in (".caption.txt", ".txt", ".md"):
        sidecar = img.with_suffix(ext)
        if sidecar.exists():
            try:
                return sidecar.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return ""


# ── Index build ───────────────────────────────────────────────────────────────

async def build_index(
    p: ProjectPaths,
    cfg: HarnessConfig,
    embed_model: str | None = None,
) -> dict[str, Any]:
    """
    Walk inspiration/, chunk + embed everything, write a fresh index.
    Returns {indexed_files, indexed_chunks, model, errors}.
    """
    model = embed_model or getattr(cfg, "embed_model", "") or DEFAULT_EMBED_MODEL
    root = inspiration_dir(p)
    root.mkdir(parents=True, exist_ok=True)

    text_files, json_reports, image_files = _discover_files(root)
    chunks: list[dict] = []
    errors: list[str] = []
    skipped_json: list[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for tf in text_files:
            try:
                raw = tf.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                errors.append(f"{tf}: read failed — {e}")
                continue
            source_rel = tf.relative_to(p.root).as_posix()
            body, meta, header = _extract_text_metadata(raw, source_rel)
            text = _strip_twee_syntax(body) if tf.suffix.lower() in (".tw", ".twee") else body
            for i, chunk in enumerate(_chunk_text(text)):
                # Prepend the metadata header so embeddings carry source context.
                embed_text = f"{header}\n\n{chunk}" if header else chunk
                try:
                    vec = await _embed(client, cfg.ollama_base_url, model, embed_text)
                except Exception as e:
                    errors.append(f"{source_rel}#{i}: embed failed — {e}")
                    continue
                chunk_record: dict = {
                    "id": f"{source_rel}#{i}",
                    "source": source_rel,
                    "kind": "text",
                    "text": chunk,
                    "vec": vec,
                }
                if meta.get("title"):
                    chunk_record["title"] = meta["title"]
                if meta.get("arc"):
                    chunk_record["arc"] = meta["arc"]
                if meta.get("tags"):
                    chunk_record["tags"] = meta["tags"]
                if meta.get("passages"):
                    chunk_record["passages"] = meta["passages"]
                chunks.append(chunk_record)

        # Parsed-sugarcube JSON reports from the html-parser sister project:
        # one chunk per passage, media references preserved in metadata.
        for jf in json_reports:
            source_rel = jf.relative_to(p.root).as_posix()
            try:
                report = json.loads(jf.read_text(encoding="utf-8", errors="ignore"))
            except Exception as e:
                errors.append(f"{source_rel}: json parse failed — {e}")
                continue
            passages = _passages_from_report(report)
            if not passages:
                skipped_json.append(source_rel)
                continue
            for i, passage in enumerate(passages):
                try:
                    vec = await _embed(client, cfg.ollama_base_url, model, passage["text"])
                except Exception as e:
                    errors.append(f"{source_rel}#{i}: embed failed — {e}")
                    continue
                chunks.append({
                    "id": f"{source_rel}#{passage['name']}",
                    "source": source_rel,
                    "kind": "passage",
                    "passage_name": passage["name"],
                    "story_title": passage["title"],
                    "media": passage["media"],
                    "text": passage["text"],
                    "vec": vec,
                })

        for img in image_files:
            caption = _caption_for_image(img)
            if not caption:
                # No caption → skip; binary embedding not supported here.
                continue
            source_rel = img.relative_to(p.root).as_posix()
            try:
                vec = await _embed(client, cfg.ollama_base_url, model, caption)
            except Exception as e:
                errors.append(f"{source_rel}: embed failed — {e}")
                continue
            chunks.append({
                "id": source_rel,
                "source": source_rel,
                "kind": "image",
                "text": caption,
                "vec": vec,
            })

    index = {
        "model": model,
        "version": 1,
        "chunks": chunks,
    }
    idx_path = index_path(p)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "indexed_files": (
            len(text_files)
            + (len(json_reports) - len(skipped_json))
            + len([i for i in image_files if _caption_for_image(i)])
        ),
        "indexed_chunks": len(chunks),
        "skipped_uncaptioned_images": len([i for i in image_files if not _caption_for_image(i)]),
        "skipped_unknown_json": skipped_json,
        "model": model,
        "errors": errors,
    }


# ── Index load + retrieve ─────────────────────────────────────────────────────

def load_index(p: ProjectPaths) -> dict | None:
    ip = index_path(p)
    if not ip.exists():
        return None
    try:
        return json.loads(ip.read_text(encoding="utf-8"))
    except Exception:
        return None


async def retrieve(
    p: ProjectPaths,
    cfg: HarnessConfig,
    query: str,
    k: int = 3,
    min_score: float = 0.3,
    sources: set[str] | None = None,
) -> list[dict]:
    """
    Return top-k chunks (highest cosine) for the given query.
    Empty list if no index, no chunks, or no results above min_score.

    ``sources`` (a set of source-relative paths) restricts the search to chunks
    from those files — used when the human pins specific inspiration files for a
    generation instead of letting the whole corpus compete.
    """
    if not query or not query.strip():
        return []
    index = load_index(p)
    if not index or not index.get("chunks"):
        return []

    model = index.get("model", DEFAULT_EMBED_MODEL)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            qvec = await _embed(client, cfg.ollama_base_url, model, query)
    except Exception:
        return []

    scored: list[tuple[float, dict]] = []
    for chunk in index["chunks"]:
        if sources is not None and chunk.get("source") not in sources:
            continue
        score = _cosine(qvec, chunk.get("vec", []))
        if score >= min_score:
            scored.append((score, chunk))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"score": s, **{k_: v for k_, v in c.items() if k_ != "vec"}} for s, c in scored[:k]]


def retrieve_sync(
    p: ProjectPaths,
    cfg: HarnessConfig,
    query: str,
    k: int = 3,
    min_score: float = 0.3,
) -> list[dict]:
    """Sync wrapper for CLI / non-async callers."""
    import asyncio
    return asyncio.run(retrieve(p, cfg, query, k=k, min_score=min_score))


# ── Stats ─────────────────────────────────────────────────────────────────────

def index_stats(p: ProjectPaths) -> dict:
    index = load_index(p)
    if not index:
        return {"exists": False, "chunks": 0, "sources": 0, "model": ""}
    sources = {c.get("source") for c in index.get("chunks", [])}
    return {
        "exists": True,
        "chunks": len(index.get("chunks", [])),
        "sources": len(sources),
        "model": index.get("model", ""),
    }


# ── Self-story index ──────────────────────────────────────────────────────────

async def build_story_index(
    p: ProjectPaths,
    cfg: HarnessConfig,
    embed_model: str | None = None,
) -> dict[str, Any]:
    """
    Walk committed passages in story.json + their .tw files, build a vector
    index of summary/beats/prose chunks. Lets RAG surface continuity from
    earlier passages, not just from the inspiration corpus.
    """
    from .project import load_story
    model = embed_model or getattr(cfg, "embed_model", "") or DEFAULT_EMBED_MODEL

    graph = load_story(p)
    chunks: list[dict] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for pid, entry in graph.passages.items():
            tw_path = p.root / entry.file
            prose = ""
            if tw_path.exists():
                raw = tw_path.read_text(encoding="utf-8", errors="ignore")
                # Strip metadata comment + macros + links so embedding sees prose only.
                stripped = re.sub(r'<!--.*?-->', '', raw, flags=re.DOTALL)
                stripped = _strip_twee_syntax(stripped)
                stripped = re.sub(r'^::.*?$', '', stripped, count=1, flags=re.MULTILINE)
                prose = stripped.strip()

            header_bits = [f"[{pid}]", f"arc:{entry.arc}"]
            if entry.summary:
                header_bits.append(f"summary: {entry.summary}")
            header = " ".join(header_bits)

            beats_block = ""
            if entry.beats:
                beats_block = "BEATS:\n" + "\n".join(f"- {b}" for b in entry.beats)

            embed_text_parts = [header]
            if beats_block:
                embed_text_parts.append(beats_block)
            if prose:
                embed_text_parts.append(prose[:1800])
            embed_text = "\n\n".join(embed_text_parts)

            try:
                vec = await _embed(client, cfg.ollama_base_url, model, embed_text)
            except Exception as e:
                errors.append(f"{pid}: embed failed — {e}")
                continue

            chunks.append({
                "id": pid,
                "source": pid,
                "kind": "story_passage",
                "arc": entry.arc,
                "summary": entry.summary,
                "beats": list(entry.beats),
                "text": embed_text,
                "vec": vec,
            })

    index = {"model": model, "version": 1, "chunks": chunks}
    idx_path = story_index_path(p)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "indexed_passages": len(graph.passages),
        "indexed_chunks": len(chunks),
        "model": model,
        "errors": errors,
    }


def load_story_index(p: ProjectPaths) -> dict | None:
    ip = story_index_path(p)
    if not ip.exists():
        return None
    try:
        return json.loads(ip.read_text(encoding="utf-8"))
    except Exception:
        return None


async def retrieve_story(
    p: ProjectPaths,
    cfg: HarnessConfig,
    query: str,
    k: int = 3,
    min_score: float = 0.3,
    exclude_ids: list[str] | None = None,
) -> list[dict]:
    """Top-k passages from the self-story index. Empty list if no index."""
    if not query or not query.strip():
        return []
    index = load_story_index(p)
    if not index or not index.get("chunks"):
        return []

    model = index.get("model", DEFAULT_EMBED_MODEL)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            qvec = await _embed(client, cfg.ollama_base_url, model, query)
    except Exception:
        return []

    skip = set(exclude_ids or [])
    scored: list[tuple[float, dict]] = []
    for chunk in index["chunks"]:
        if chunk.get("id") in skip:
            continue
        score = _cosine(qvec, chunk.get("vec", []))
        if score >= min_score:
            scored.append((score, chunk))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"score": s, **{k_: v for k_, v in c.items() if k_ != "vec"}} for s, c in scored[:k]]


def story_index_stats(p: ProjectPaths) -> dict:
    index = load_story_index(p)
    if not index:
        return {"exists": False, "chunks": 0, "model": ""}
    return {
        "exists": True,
        "chunks": len(index.get("chunks", [])),
        "model": index.get("model", ""),
    }


# ── Prompt-ready retrieval formatters ────────────────────────────────────────
# These wrap the raw retrieve()/retrieve_story() functions, returning a single
# formatted string ready to drop into a prompt. Callers in the API layer use
# these directly so the prompt-shape stays close to the retrieval logic.

async def retrieve_inspiration(
    p: ProjectPaths,
    cfg: HarnessConfig,
    query: str,
    sources: set[str] | None = None,
) -> str:
    """Top-k inspiration chunks formatted as a prompt-ready block. Empty when disabled or no index.

    ``sources`` pins retrieval to specific inspiration files. When pinning, the
    min-score floor is dropped so the chosen files always surface, and k is
    widened a little so multiple chunks from the pinned files can appear.
    """
    if not getattr(cfg, "rag_enabled", False):
        return ""
    pinned = sources is not None and len(sources) > 0
    try:
        hits = await retrieve(
            p, cfg, query,
            k=getattr(cfg, "rag_top_k", 3) + (3 if pinned else 0),
            min_score=0.0 if pinned else getattr(cfg, "rag_min_score", 0.3),
            sources=sources if pinned else None,
        )
    except Exception:
        return ""
    if not hits:
        return ""
    parts: list[str] = []
    for h in hits:
        src = h.get("source", "?")
        score = h.get("score", 0)
        body = h.get("text", "")[:600]
        parts.append(f"--- inspiration: {src} (score {score:.2f}) ---\n{body}")
    return "\n\n".join(parts)


async def retrieve_story_recall(
    p: ProjectPaths,
    cfg: HarnessConfig,
    query: str,
    exclude_ids: list[str] | None = None,
) -> str:
    """Top-k earlier-passage chunks formatted as a prompt-ready block."""
    if not getattr(cfg, "rag_enabled", False):
        return ""
    try:
        hits = await retrieve_story(
            p, cfg, query,
            k=getattr(cfg, "rag_top_k", 3),
            min_score=getattr(cfg, "rag_min_score", 0.3),
            exclude_ids=exclude_ids,
        )
    except Exception:
        return ""
    if not hits:
        return ""
    parts: list[str] = []
    for h in hits:
        pid = h.get("id", "?")
        score = h.get("score", 0)
        summary = h.get("summary", "")
        beats = h.get("beats") or []
        beats_str = "\n".join(f"  - {b}" for b in beats)
        body = f"summary: {summary}" if summary else ""
        if beats_str:
            body += ("\n" if body else "") + "beats:\n" + beats_str
        parts.append(f"--- earlier: {pid} (score {score:.2f}) ---\n{body}")
    return "\n\n".join(parts)
