#!/usr/bin/env python3
import os
import sys
import ast
import networkx as nx
import matplotlib.pyplot as plt

def build_module_map(base_dir):
    module_map = {}
    for root, dirs, files in os.walk(base_dir):
        for fname in files:
            if fname.endswith('.py'):
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, base_dir)
                mod_name = rel_path[:-3].replace(os.path.sep, '.')
                module_map[mod_name] = full_path
    return module_map

def parse_imports(file_path):
    imports = set()
    try:
        src = open(file_path, 'r', encoding='utf-8').read()
        tree = ast.parse(src, filename=file_path)
    except Exception as e:
        print(f"⚠️  Could not parse {file_path}: {e}", file=sys.stderr)
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports

def resolve_and_dfs(start_mod, module_map):
    visited = set()
    edges = []
    def _dfs(mod):
        if mod in visited: return
        visited.add(mod)
        path = module_map.get(mod)
        if not path: return

        for imp in parse_imports(path):
            if imp in module_map:
                edges.append((mod, imp))
                _dfs(imp)
            else:
                root = imp.split('.')[0]
                if root in module_map:
                    edges.append((mod, root))
                    _dfs(root)
    _dfs(start_mod)
    return visited, edges

def render_with_networkx(edges, output_png="file_map.png"):
    G = nx.DiGraph()
    G.add_edges_from(edges)

    # choose layout (spring gives a force-directed layout)
    pos = nx.spring_layout(G, k=0.5, iterations=50)

    plt.figure(figsize=(12, 8))
    nx.draw_networkx_nodes(G, pos, node_size=800, node_color='lightblue')
    nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=12, edge_color='gray')
    nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')

    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_png, dpi=200)
    plt.close()
    print(f"📊 Graph rendered to: {output_png}")

def main():
    base_dir = os.getcwd()
    start = input("▶️  Enter relative path to the starting .py file: ").strip()
    full_start = os.path.abspath(start)

    if not full_start.startswith(base_dir) or not os.path.isfile(full_start):
        print("❌  Invalid file. Must exist inside this directory or its subdirs.")
        sys.exit(1)

    modules = build_module_map(base_dir)
    rel = os.path.relpath(full_start, base_dir)
    start_mod = rel[:-3].replace(os.path.sep, '.')
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

if __name__ == "__main__":
    main()
