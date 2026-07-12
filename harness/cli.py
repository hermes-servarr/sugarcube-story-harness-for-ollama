"""CLI entry point — harness init | serve | compile | validate."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


def cmd_init(args):
    from .project import init_project
    root = Path(args.path).resolve()
    p = init_project(root, title=args.title)
    print(f"Initialized story project at {root}")
    print(f"  Edit {p.premise_md} to set your premise.")
    print(f"  Edit {p.config_yaml} to configure Ollama and Tweego paths.")


def cmd_serve(args):
    import os
    import uvicorn
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Error: {root} does not exist. Run 'harness init {root}' first.")
        sys.exit(1)
    os.environ["HARNESS_PROJECT"] = str(root)
    print(f"Starting harness server at http://localhost:{args.port}")
    print(f"Project: {root}")
    uvicorn.run(
        "harness.server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def cmd_compile(args):
    from .project import ProjectPaths, load_config
    from .compile import compile_story
    root = Path(args.path).resolve()
    p = ProjectPaths(root)
    cfg = load_config(p)
    ok, msg = compile_story(p, cfg)
    if ok:
        print(f"OK Compiled: {msg}")
    else:
        print(f"FAIL Compile failed:\n{msg}")
        sys.exit(1)


def cmd_rag_reindex(args):
    import asyncio
    from .project import ProjectPaths, load_config
    from .rag import build_index
    root = Path(args.path).resolve()
    p = ProjectPaths(root)
    cfg = load_config(p)
    result = asyncio.run(build_index(p, cfg))
    print(f"Indexed {result['indexed_chunks']} chunks from {result['indexed_files']} files "
          f"using model {result['model']}.")
    if result.get("skipped_uncaptioned_images"):
        print(f"  Skipped {result['skipped_uncaptioned_images']} images without captions.")
    if result.get("skipped_unknown_json"):
        print(f"  Skipped {len(result['skipped_unknown_json'])} JSON files (unknown schema).")
    for err in result.get("errors", [])[:10]:
        print(f"  ERROR: {err}")


def cmd_rag_status(args):
    from .project import ProjectPaths
    from .rag import index_stats
    root = Path(args.path).resolve()
    p = ProjectPaths(root)
    stats = index_stats(p)
    if not stats["exists"]:
        print("No inspiration index built yet. Run: harness rag-reindex")
        return
    print(f"Index model: {stats['model']}")
    print(f"Sources:     {stats['sources']}")
    print(f"Chunks:      {stats['chunks']}")


def cmd_rebuild(args):
    from .project import ProjectPaths
    from .passage import rebuild_and_save
    root = Path(args.path).resolve()
    p = ProjectPaths(root)
    if not p.story_json.exists() and not args.force:
        print(f"No story.json at {root}. Use --force to build one from disk anyway.")
        sys.exit(1)
    report = rebuild_and_save(p)
    print("Rebuilt story.json from disk.")
    if report:
        print(f"  {len(report)} note(s):")
        for line in report:
            print(f"  - {line}")
    else:
        print("  No issues — graph was already consistent with disk.")


def cmd_generations(args):
    from .project import ProjectPaths
    from .audit import list_generations, read_generation
    root = Path(args.path).resolve()
    p = ProjectPaths(root)
    if args.id:
        rec = read_generation(p, args.id)
        if rec is None:
            print(f"No generation {args.id!r}.")
            sys.exit(1)
        print(f"# {rec.get('id')}  [{rec.get('kind')}]  {rec.get('ts')}")
        print(f"# model={rec.get('model','')}  passage={rec.get('passage_id') or rec.get('passage_slug','')}")
        print("\n--- RAW OUTPUT ---")
        print(rec.get("raw_output", ""))
        return
    rows = list_generations(p, limit=args.limit)
    if not rows:
        print("No generations recorded yet.")
        return
    for r in rows:
        tag = r["passage_id"] or r["passage_slug"] or "-"
        print(f"{r['id']}  [{r['kind']:<6}] {r['model']:<22} {tag}")
    print(f"\n{len(rows)} shown. View one: harness generations {root} --id <ID>")


def cmd_validate(args):
    from .project import ProjectPaths
    from .validation import run_validation
    root = Path(args.path).resolve()
    p = ProjectPaths(root)
    result = run_validation(p)
    if result.errors:
        print("ERRORS:")
        for e in result.errors:
            loc = f" [{e.passage}]" if e.passage else ""
            print(f"  [{e.code}]{loc} {e.message}")
    if result.warnings:
        print("WARNINGS:")
        for w in result.warnings:
            loc = f" [{w.passage}]" if w.passage else ""
            print(f"  [{w.code}]{loc} {w.message}")
    if result.ok and not result.warnings:
        print("OK No issues.")
    sys.exit(0 if result.ok else 1)


def main():
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Sugarcube Agentic Story Harness",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize a new story project")
    p_init.add_argument("path", nargs="?", default=".", help="Project directory")
    p_init.add_argument("--title", default="Untitled Story")
    p_init.set_defaults(func=cmd_init)

    # serve
    p_serve = sub.add_parser("serve", help="Start the web UI")
    p_serve.add_argument("path", nargs="?", default=".", help="Project directory")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    # compile
    p_compile = sub.add_parser("compile", help="Compile story to HTML via Tweego")
    p_compile.add_argument("path", nargs="?", default=".", help="Project directory")
    p_compile.set_defaults(func=cmd_compile)

    # validate
    p_validate = sub.add_parser("validate", help="Run validation checks")
    p_validate.add_argument("path", nargs="?", default=".", help="Project directory")
    p_validate.set_defaults(func=cmd_validate)

    # rebuild
    p_rebuild = sub.add_parser(
        "rebuild", help="Reconstruct story.json from the .tw files on disk (repairs drift)")
    p_rebuild.add_argument("path", nargs="?", default=".", help="Project directory")
    p_rebuild.add_argument("--force", action="store_true",
                           help="Build even when story.json is missing")
    p_rebuild.set_defaults(func=cmd_rebuild)

    # generations
    p_gen = sub.add_parser(
        "generations", help="List / view persisted model generations (audit + recovery)")
    p_gen.add_argument("path", nargs="?", default=".", help="Project directory")
    p_gen.add_argument("--id", default="", help="Print full raw output for one generation id")
    p_gen.add_argument("--limit", type=int, default=30, help="How many to list")
    p_gen.set_defaults(func=cmd_generations)

    # rag-reindex
    p_rag = sub.add_parser("rag-reindex", help="Build / rebuild inspiration vector index")
    p_rag.add_argument("path", nargs="?", default=".", help="Project directory")
    p_rag.set_defaults(func=cmd_rag_reindex)

    # rag-status
    p_rs = sub.add_parser("rag-status", help="Show inspiration index stats")
    p_rs.add_argument("path", nargs="?", default=".", help="Project directory")
    p_rs.set_defaults(func=cmd_rag_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
