"""
Static verification — no third-party packages required. Checks:
1. Syntax (compile)
2. Every `from app.X.Y import Z` / `import app.X.Y` resolves to a real
   file/package on disk
3. Every local (app./tests.) name imported is actually defined in the
   target module (function/class/variable exists at module level)
4. Missing __init__.py in any directory containing .py files
5. A directed graph of local-module imports, checked for cycles
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KNOWN_THIRD_PARTY = {
    "fastapi", "starlette", "pydantic", "pydantic_settings", "sqlalchemy",
    "alembic", "argon2", "jwt", "redis", "google", "email_validator",
    "httpx", "pytest", "uvicorn", "smtplib", "email",
}

STDLIB_HINTS = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()


def find_py_files(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in ("venv", "__pycache__", ".git", "keys")]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def module_path_to_file(mod_name: str):
    """app.core.config -> app/core/config.py or app/core/config/__init__.py"""
    parts = mod_name.split(".")
    candidate_file = os.path.join(ROOT, *parts) + ".py"
    candidate_pkg = os.path.join(ROOT, *parts, "__init__.py")
    if os.path.isfile(candidate_file):
        return candidate_file
    if os.path.isfile(candidate_pkg):
        return candidate_pkg
    return None


def get_module_top_level_names(filepath: str) -> set[str]:
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # re-exported names count too
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def main():
    errors = []
    warnings = []
    import_graph = {}  # file -> set of local files it imports

    py_files = sorted(find_py_files(ROOT))
    print(f"Scanning {len(py_files)} Python files under {ROOT}\n")

    # --- 1. Syntax check ---
    trees = {}
    for fp in py_files:
        rel = os.path.relpath(fp, ROOT)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                src = f.read()
            trees[fp] = ast.parse(src, filename=fp)
        except SyntaxError as e:
            errors.append(f"SYNTAX ERROR in {rel}: {e}")

    # --- 2 & 3. Import resolution + name existence ---
    for fp, tree in trees.items():
        rel = os.path.relpath(fp, ROOT)
        local_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    warnings.append(f"{rel}: relative import found (level={node.level}) — project uses absolute imports elsewhere, verify intentional")
                    continue
                if node.module is None:
                    continue
                mod = node.module
                if not (mod == "app" or mod.startswith("app.") or mod == "tests" or mod.startswith("tests.")):
                    continue  # third-party or stdlib, skip resolution
                target_file = module_path_to_file(mod)
                if target_file is None:
                    errors.append(f"{rel}: `from {mod} import ...` — module '{mod}' does not resolve to any file")
                    continue
                local_imports.add(target_file)
                try:
                    defined_names = get_module_top_level_names(target_file)
                except SyntaxError:
                    continue
                target_dir = os.path.dirname(target_file) if os.path.basename(target_file) == "__init__.py" else None
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if alias.name in defined_names:
                        continue
                    # Valid case: `from package import submodule` where
                    # submodule.py or submodule/__init__.py exists on disk —
                    # Python resolves this via the import system even if
                    # __init__.py never re-exports the name.
                    if target_dir and (
                        os.path.isfile(os.path.join(target_dir, alias.name + ".py"))
                        or os.path.isfile(os.path.join(target_dir, alias.name, "__init__.py"))
                    ):
                        continue
                    errors.append(
                        f"{rel}: `from {mod} import {alias.name}` — "
                        f"'{alias.name}' not found at top level of {os.path.relpath(target_file, ROOT)}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    if not (mod == "app" or mod.startswith("app.") or mod == "tests" or mod.startswith("tests.")):
                        continue
                    target_file = module_path_to_file(mod)
                    if target_file is None:
                        errors.append(f"{rel}: `import {mod}` — module '{mod}' does not resolve to any file")
                    else:
                        local_imports.add(target_file)
        import_graph[fp] = local_imports

    # --- 4. Missing __init__.py ---
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in ("venv", "__pycache__", ".git", "keys", "alembic", "tests")]
        if dirpath == ROOT:
            continue
        if not any(f.endswith(".py") for f in filenames):
            continue
        rel = os.path.relpath(dirpath, ROOT)
        if rel.startswith("app") and "__init__.py" not in filenames:
            errors.append(f"MISSING __init__.py in {rel}/")

    # --- 5. Cycle detection (DFS) ---
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {f: WHITE for f in import_graph}
    cycle_found = []

    def dfs(node, stack):
        color[node] = GRAY
        stack.append(node)
        for neighbor in import_graph.get(node, ()):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                cyc = stack[stack.index(neighbor):] + [neighbor]
                cycle_found.append(" -> ".join(os.path.relpath(x, ROOT) for x in cyc))
            elif color[neighbor] == WHITE:
                dfs(neighbor, stack)
        stack.pop()
        color[node] = BLACK

    for f in list(import_graph):
        if color[f] == WHITE:
            dfs(f, [])

    for c in cycle_found:
        errors.append(f"CIRCULAR IMPORT: {c}")

    # --- Report ---
    print(f"=== ERRORS ({len(errors)}) ===")
    for e in errors:
        print("  -", e)
    print(f"\n=== WARNINGS ({len(warnings)}) ===")
    for w in warnings:
        print("  -", w)

    print(f"\n=== SUMMARY ===")
    print(f"Files scanned: {len(py_files)}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
