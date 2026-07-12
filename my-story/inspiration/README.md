# Inspiration corpus

Drop reference material here. The RAG indexer scans this folder and
retrieves the most relevant chunks at generate time.

## Supported file types
- `.tw` / `.twee` — raw Twee passages (macros stripped before embed)
- `.md` / `.txt` / `.rst` — prose notes, world bibles, etc.
- `.json` — parsed SugarCube reports from the html-parser project
  (one chunk per passage, media refs preserved)
- `.png`/`.jpg`/`.webp`/... — indexed only if a sidecar caption file
  exists next to it (`scene.jpg` + `scene.caption.txt`)

## Rebuild index
POST `/api/rag/reindex` from the UI, or call:
  `harness rag-reindex`

Indexed vectors are stored in `.harness/cache/inspiration_index.json`
(gitignored). Inspiration files themselves are NOT compiled into your game.
