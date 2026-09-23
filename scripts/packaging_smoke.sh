#!/usr/bin/env bash
# Build forge-scaffolder, install the wheel into a clean venv *outside* the repo,
# and prove generation uses packaged templates (not the source tree).
# Console script remains ``forge``; import package remains ``forge``.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Building distributions"
rm -rf dist
uv build

WHEEL="$(ls dist/forge_scaffolder-*.whl | head -n1)"
if [[ -z "${WHEEL}" ]]; then
  echo "ERROR: no wheel found in dist/" >&2
  exit 1
fi
echo "    wheel: ${WHEEL}"

echo "==> Verifying wheel contains templates"
python - <<PY
import sys
import zipfile
from pathlib import Path

wheel = Path("${WHEEL}")
with zipfile.ZipFile(wheel) as zf:
    names = zf.namelist()
    metadata = zf.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode()
assert "Name: forge-scaffolder" in metadata, metadata
assert "Version: 0.2.0" in metadata, metadata
assert (
    "License-Expression: GPL-3.0-only" in metadata
    or "License: GPL-3.0-only" in metadata
), metadata
templates = [n for n in names if n.startswith("forge/templates/python/")]
assert templates, "wheel missing forge/templates/python/"
# Spot-check frameworks
for frag in (
    "forge/templates/python/fastapi/",
    "forge/templates/python/django/",
    "forge/templates/python/flask/",
):
    assert any(n.startswith(frag) for n in templates), f"missing {frag}"
assert any(n.endswith("mongodb.py.j2") for n in templates), "missing mongodb templates"
assert any(n.endswith("redis_client.py.j2") for n in templates), "missing redis templates"
assert any(
    "/_shared/" in n and n.endswith("ci.yml.j2") for n in templates
), "missing shared GitHub Actions CI template"
# Must not ship tests or local smoke trees inside the package
assert not any(n.startswith("forge/tests/") for n in names)
assert not any(".smoke" in n for n in names)
assert not any(".cursor" in n for n in names)
print(f"    templates in wheel: {len(templates)}")
PY

WORK="$(mktemp -d "${TMPDIR:-/tmp}/forge-packaging-XXXXXX")"
cleanup() { rm -rf "${WORK}"; }
trap cleanup EXIT

echo "==> Clean venv at ${WORK}"
# Keep the workdir outside the repository so import/path fallbacks cannot
# accidentally use the checkout templates/.
case "${WORK}" in
  "${ROOT}"/*)
    echo "ERROR: work dir unexpectedly under repo" >&2
    exit 1
    ;;
esac

uv venv "${WORK}/venv"
# shellcheck disable=SC1091
source "${WORK}/venv/bin/activate"
uv pip install "${WHEEL}"

FORGE_BIN="$(command -v forge)"
echo "    forge executable: ${FORGE_BIN}"
python - <<PY
import forge
import forge.generator.render as render
from pathlib import Path

print(f"    forge package: {Path(forge.__file__).resolve()}")
print(f"    forge version: {forge.__version__}")
assert forge.__version__ == "0.2.0", forge.__version__
from importlib.metadata import metadata
meta = metadata("forge-scaffolder")
assert meta["Name"] == "forge-scaffolder"
root = render.templates_root()
print(f"    templates_root: {root}")
repo = Path("${ROOT}").resolve()
assert repo not in root.resolve().parents and root.resolve() != repo / "templates", (
    f"templates_root unexpectedly points at the source checkout: {root}"
)
assert (root / "python").is_dir()
assert "site-packages" in str(root) or "forge/templates" in str(root).replace("\\\\", "/")
PY

echo "==> CLI smoke"
forge --version | grep -F "forge 0.2.0"
forge --help >/dev/null
forge new --help >/dev/null
forge plan --preset fastapi-postgres >/dev/null
forge plan --preset fastapi-mongo >/dev/null

GEN="${WORK}/generated"
mkdir -p "${GEN}"
cd "${GEN}"

echo "==> Generate via preset (installed package)"
forge new pack-fa --preset fastapi-postgres
test -f pack-fa/pyproject.toml
test -d pack-fa/src/pack_fa
test -f pack-fa/alembic.ini

echo "==> Generate FastAPI sqlite modular (validation-friendly)"
cat > fastapi.yaml <<'EOF'
name: pack-fa-sqlite
type: rest-api
framework: fastapi
architecture: modular-monolith
database: sqlite
migrations: true
testing: true
linting: true
docker: false
EOF
forge new --config fastapi.yaml
test -f pack-fa-sqlite/pyproject.toml

echo "==> Generate Django (config)"
cat > django.yaml <<'EOF'
name: pack-dj
type: rest-api
framework: django
architecture: modular-monolith
database: sqlite
testing: true
linting: true
docker: false
EOF
forge new --config django.yaml
test -f pack-dj/manage.py

echo "==> Generate Flask (config)"
cat > flask.yaml <<'EOF'
name: pack-fl
type: rest-api
framework: flask
architecture: modular-monolith
database: sqlite
migrations: true
testing: true
linting: true
docker: false
EOF
forge new --config flask.yaml
test -f pack-fl/pyproject.toml

echo "==> Generate FastAPI MongoDB (config)"
cat > fastapi-mongo.yaml <<'EOF'
name: pack-fa-mongo
type: rest-api
framework: fastapi
architecture: modular-monolith
persistence:
  nosql: mongodb
testing: true
linting: true
docker: false
EOF
forge new --config fastapi-mongo.yaml
test -f pack-fa-mongo/pyproject.toml
grep -q pymongo pack-fa-mongo/pyproject.toml
test -f pack-fa-mongo/src/pack_fa_mongo/core/mongodb.py

echo "==> Validate FastAPI generated project"
cd "${GEN}/pack-fa-sqlite"
uv sync
uv run pytest
uv run ruff check .

echo "==> Validate FastAPI MongoDB generated project"
cd "${GEN}/pack-fa-mongo"
uv sync
uv run pytest
uv run ruff check .

echo "==> Validate Django generated project"
cd "${GEN}/pack-dj"
uv sync
uv run python manage.py check
uv run python manage.py migrate
uv run pytest
uv run ruff check .

echo "==> Validate Flask generated project"
cd "${GEN}/pack-fl"
uv sync
uv run pytest
uv run ruff check .

echo "==> Packaging smoke OK"
