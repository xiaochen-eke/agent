import os
import json
from typing import Dict, List, Tuple

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif")


def index_images(base_dir: str) -> Dict[str, List[str]]:
    """Scan `base_dir` and return a mapping label -> list of image file paths.

    Assumes images are organized in subfolders named by label (the same layout
    produced by `image_agent.py`)."""
    index = {}
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"base_dir not found: {base_dir}")

    for root, dirs, files in os.walk(base_dir):
        # If root is the base_dir itself, treat each immediate subdir as a label
        # Otherwise, derive label from the relative path to base_dir
        rel = os.path.relpath(root, base_dir)
        if rel == ".":
            # top-level folder; skip files directly under base_dir
            continue
        label = rel.replace(os.sep, "/")
        imgs = [os.path.join(root, f) for f in files if f.lower().endswith(SUPPORTED_EXTS)]
        if imgs:
            index[label] = imgs

    return index


def search_by_label(index: Dict[str, List[str]], query: str) -> List[Tuple[str, str]]:
    """Return (label, path) for labels matching query (case-insensitive substring)."""
    q = query.lower()
    results = []
    for label, paths in index.items():
        if q in label.lower():
            for p in paths:
                results.append((label, p))
    return results


def search_by_filename(index: Dict[str, List[str]], query: str) -> List[Tuple[str, str]]:
    q = query.lower()
    results = []
    for label, paths in index.items():
        for p in paths:
            if q in os.path.basename(p).lower():
                results.append((label, p))
    return results


def search(index: Dict[str, List[str]], query: str) -> List[Tuple[str, str]]:
    """General search: matches labels and filenames; de-duplicates results."""
    res_label = search_by_label(index, query)
    res_file = search_by_filename(index, query)
    seen = set()
    out = []
    for t in res_label + res_file:
        if t[1] not in seen:
            seen.add(t[1])
            out.append(t)
    return out


def interactive_loop(base_dir: str):
    try:
        index = index_images(base_dir)
    except Exception as e:
        print(f"Error: {e}")
        return

    print(f"Indexed {sum(len(v) for v in index.values())} images across {len(index)} labels.")
    print("Commands: list_labels | search <query> | search_label <label> | search_file <name> | dump_json <out.json> | exit")

    last_results = []
    while True:
        try:
            line = input("search-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "exit":
            break
        elif cmd == "list_labels":
            for lbl in sorted(index.keys()):
                print(lbl)
        elif cmd == "search":
            last_results = search(index, arg)
            for lbl, p in last_results[:200]:
                print(f"[{lbl}] {p}")
            print(f"Total: {len(last_results)} results")
        elif cmd == "search_label":
            last_results = search_by_label(index, arg)
            for lbl, p in last_results:
                print(f"[{lbl}] {p}")
            print(f"Total: {len(last_results)} results")
        elif cmd == "search_file":
            last_results = search_by_filename(index, arg)
            for lbl, p in last_results:
                print(f"[{lbl}] {p}")
            print(f"Total: {len(last_results)} results")
        elif cmd == "dump_json":
            out = arg or "search_results.json"
            try:
                with open(out, "w", encoding="utf-8") as f:
                    json.dump([{"label": l, "path": p} for l, p in last_results], f, ensure_ascii=False, indent=2)
                print(f"Wrote {len(last_results)} results to {out}")
            except Exception as e:
                print(f"Failed to write JSON: {e}")
        else:
            print("Unknown command")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Image search agent for classified images")
    parser.add_argument("base_dir", nargs="?", default=r"C:\\DLdata\\git\\PH\\1", help="根分类文件夹（默认与 Agent/image_agent.py 的 SAVE_BASE_DIR 一致）")
    args = parser.parse_args()
    interactive_loop(args.base_dir)
