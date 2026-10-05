"""Detects imports that are never referenced elsewhere in the same file.
Conservative: only flags a name if it appears exactly once (the import
line itself) anywhere in the file's source text."""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_py_files(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in ("venv", "__pycache__", ".git", "keys")]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def main():
    issues = []
    for fp in sorted(find_py_files(ROOT)):
        rel = os.path.relpath(fp, ROOT)
        with open(fp, "r", encoding="utf-8") as f:
            src = f.read()
        try:
            tree = ast.parse(src, filename=fp)
        except SyntaxError:
            continue

        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names.append((name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imported_names.append((name, node.lineno))

        lines = src.splitlines()
        for name, lineno in imported_names:
            # Count occurrences of the name as a whole word anywhere in the file,
            # excluding the import statement's own line.
            occurrences = 0
            for i, line in enumerate(lines, start=1):
                if i == lineno:
                    continue
                # crude word-boundary check
                idx = 0
                while True:
                    idx = line.find(name, idx)
                    if idx == -1:
                        break
                    before_ok = idx == 0 or not (line[idx - 1].isalnum() or line[idx - 1] == "_")
                    after_idx = idx + len(name)
                    after_ok = after_idx >= len(line) or not (line[after_idx].isalnum() or line[after_idx] == "_")
                    if before_ok and after_ok:
                        occurrences += 1
                    idx = after_idx
            if occurrences == 0:
                issues.append(f"{rel}:{lineno}: '{name}' imported but never used")

    print(f"=== UNUSED IMPORTS ({len(issues)}) ===")
    for i in issues:
        print(" -", i)
    return 1 if issues else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
