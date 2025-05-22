#!/usr/bin/env python3
"""
File-dependency mapper + maintenance helper.

• Builds an import graph from a chosen start-module.
• Renders the graph as file_map.png.
• Lists unused project modules.
• Optional actions:
   1. Move all unused modules to ./unused
   2. Detect & pip-install missing third-party packages
"""
import os
import sys
import ast
import shutil
import subprocess
import importlib.util
from typing import Set, Dict, Tuple, List

import networkx as nx
import matplotlib.pyplot as plt


# ────────────────────────────── Core mapping helpers ───────────────────────────
def build_module_map(base_dir: str) -> Dict[str, str]:
    module_map = {}
    for root, _, files in os.walk(base_dir):
        for fname in files:
            if fname.endswith(".py"):
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, base_dir)
                mod_name = rel_path[:-3].replace(os.path.sep, ".")
                module_map[mod_name] = full_path
    return module_map


def parse_imports(file_path: str) -> Set[str]:
    imports: Set[str] = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception as exc:
        print(f"⚠️  Could not parse {file_path}: {exc}", file=sys.stderr)
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def resolve_and_dfs(start_mod: str, module_map: Dict[str, str]) -> Tuple[Set[str], List[Tuple[str, str]]]:
    visited: Set[str] = set()
    edges: List[Tuple[str, str]] = []

    def _dfs(mod: str) -> None:
        if mod in visited:
            return
        visited.add(mod)
        path = module_map.get(mod)
        if not path:
            return

        for imp in parse_imports(path):
            root = imp.split(".")[0]
            # prefer fully-qualified match; fall back to the root
            target = imp if imp in module_map else root
            if target in module_map:
                edges.append((mod, target))
                _dfs(target)

    _dfs(start_mod)
    return visited, edges


def render_with_networkx(edges: List[Tuple[str, str]], output_png: str = "file_map.png") -> None:
    G = nx.DiGraph()
    G.add_edges_from(edges)
    pos = nx.spring_layout(G, k=0.5, iterations=50)

    plt.figure(figsize=(12, 8))
    nx.draw_networkx_nodes(G, pos, node_size=800, node_color="lightblue")
    nx.draw_networkx_edges(G, pos, arrowstyle="->", arrowsize=12, edge_color="gray")
    nx.draw_networkx_labels(G, pos, font_size=8, font_family="sans-serif")

    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_png, dpi=200)
    plt.close()
    print(f"📊 Graph rendered to: {output_png}")


# ─────────────────────────────── Maintenance tasks ─────────────────────────────
def move_unused_files(unused: Set[str], module_map: Dict[str, str], base_dir: str, out_dir: str = "unused") -> None:
    if not unused:
        print("👍 Nothing to move — no unused files.")
        return

    dest_root = os.path.join(base_dir, out_dir)
    os.makedirs(dest_root, exist_ok=True)

    for mod in unused:
        src_path = module_map[mod]
        rel_parts = mod.split(".")  # preserve sub-folders
        dest_path = os.path.join(dest_root, *rel_parts) + ".py"

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.move(src_path, dest_path)
        print(f"➡️  Moved {src_path}  →  {dest_path}")
    print(f"✅ Unused modules relocated to ./{out_dir}/")


def gather_all_import_roots(module_map: Dict[str, str]) -> Set[str]:
    all_imports: Set[str] = set()
    for path in module_map.values():
        for imp in parse_imports(path):
            all_imports.add(imp.split(".")[0])
    return all_imports


def install_missing_packages(import_roots: Set[str], module_map: Dict[str, str]) -> None:
    # Anything in project modules is internal; skip them
    internal_roots = {m.split(".")[0] for m in module_map}
    candidates = import_roots - internal_roots

    missing: List[str] = []
    for root in candidates:
        if importlib.util.find_spec(root) is None:
            missing.append(root)

    if not missing:
        print("🎉 No missing external packages detected.")
        return

    print("📦 The following packages appear to be missing:")
    for pkg in missing:
        print(f"   • {pkg}")

    ans = input("▶️  Install these now with pip? [y/N] ").strip().lower()
    if ans != "y":
        print("❌  Installation skipped.")
        return

    for pkg in missing:
        print(f"⏳ Installing {pkg} ...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            print(f"✅ {pkg} installed.")
        except subprocess.CalledProcessError as exc:
            print(f"⚠️  Failed to install {pkg}: {exc}")


# ─────────────────────────────────── main ──────────────────────────────────────
def main() -> None:
    base_dir = os.getcwd()
    start = input("▶️  Enter relative path to the starting .py file: ").strip()
    full_start = os.path.abspath(start)

    if not full_start.startswith(base_dir) or not os.path.isfile(full_start):
        print("❌  Invalid file. Must exist inside this directory or its subdirs.")
        sys.exit(1)

    modules = build_module_map(base_dir)
    rel = os.path.relpath(full_start, base_dir)
    start_mod = rel[:-3].replace(os.path.sep, ".")

    if start_mod not in modules:
        print("❌  Couldn’t map your start file to a module name.")
        sys.exit(1)

    print(f"🔍 Scanning imports from module: {start_mod}")
    visited, edges = resolve_and_dfs(start_mod, modules)

    render_with_networkx(edges, output_png="file_map.png")

    unused = set(modules) - visited
    if unused:
        print("\n📄 Unused files:")
        for mod in sorted(unused):
            print(f"- {modules[mod]}")
    else:
        print("\n🎉 No unused .py files detected!")

    # —— Action menu ——
    print(
        "\nWhat would you like to do?\n"
        "1  Move all unused files to ./unused\n"
        "2  Detect & install missing external dependencies\n"
        "q  Quit\n"
        "Enter one or more choices separated by commas (e.g., 1,2):"
    )
    choices = {c.strip() for c in input("▶️  ").split(",")}

    if "1" in choices:
        move_unused_files(unused, modules, base_dir)

    if "2" in choices:
        roots = gather_all_import_roots(modules)
        install_missing_packages(roots, modules)

    print("✅ Done.")


if __name__ == "__main__":
    main()
