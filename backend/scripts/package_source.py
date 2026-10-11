"""Package only explicit source paths. Does not read environment values or deploy."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[2]
folders = [
    "backend/app",
    "backend/sql",
    "backend/google",
    "backend/scripts",
    "backend/tests",
    "frontend/src",
    "frontend/public",
    "frontend/scripts",
    "frontend/tests",
    "ref",
    "advanced_reference",
]
files = [
    "README.md",
    "OWNER_SETUP.md",
    "VERIFICATION.md",
    "CHANGE_REPORT.md",
    "deployment/DATABASE_REVIEW.md",
    ".gitignore",
    ".env.example",
    "render.yaml",
    "backend/pyproject.toml",
    "backend/requirements.txt",
    "backend/requirements-dev.txt",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "frontend/eslint.config.js",
    "frontend/index.html",
    "frontend/.env.example",
]
selected = [root / name for name in files]
for folder in folders:
    selected.extend(p for p in (root / folder).rglob("*") if p.is_file())
# Generate provider routing in the extracted source once the real Render URL is known.
# Intentionally omit arbitrary local/generated provider configuration from this archive.
safe = []
for path in selected:
    if path.is_symlink() or "__pycache__" in path.parts or path.suffix == ".pyc":
        continue
    if path.name.startswith(".env") and path.name != ".env.example":
        raise RuntimeError("Environment file unexpectedly selected.")
    path.resolve().relative_to(root.resolve())
    if path.is_file():
        safe.append(path)
target = root / "deployment/artifacts/chronohunt-source.zip"
target.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for path in sorted(set(safe)):
        archive.write(path, path.relative_to(root).as_posix())
with ZipFile(target) as archive:
    assert all(not name.endswith("/.env") and name != ".env" for name in archive.namelist())
print(
    f"Source package created: {target}; {len(safe)} source files. No environment secrets/dependencies included."
)
