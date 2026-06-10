#!/bin/bash
#
# Build a Python .orb package using the bin/lib layout.
# Source files land in bin/, Python dependencies in lib/.
#
# Usage (from workspace root, with orbit-os-sdk-python as submodule):
#   bash orbit-os-sdk-python/scripts/build_package.sh
#   bash orbit-os-sdk-python/scripts/build_package.sh arm64
#   bash orbit-os-sdk-python/scripts/build_package.sh arm64 3.13
#   bash orbit-os-sdk-python/scripts/build_package.sh arm64 3.13 --no-lib
#
# Arguments (all optional, positional):
#   arm64    if "arm64", cross-installs Python deps for aarch64
#   pyver    target Python minor for arm64 (e.g. 3.13); must match the device's python3
#   --no-lib skip pip dep install; lib/ will be empty in the .orb
#
# Version comes only from metadata.json "version" — not from CLI.
# ORB output: build/package/<entry_point>_v<version>.orb
#
# Prerequisites:
#   - api/ must already be generated:  python .vscode/gen_api.py
#   - zip must be installed:           sudo apt-get install zip
#

set -e

# ── Dependencies ─────────────────────────────────────────────────────────────

if ! command -v zip &>/dev/null; then
    echo -e "\033[0;31mError: 'zip' is required.\033[0m  Install: sudo apt-get install zip"
    exit 1
fi

# ── Colors ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

BUILD_DIR="$WORKSPACE_ROOT/build/orb_build"
OUTPUT_DIR="$WORKSPACE_ROOT/build/package"

# ── Argument parsing ─────────────────────────────────────────────────────────

INCLUDE_LIB=true
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --no-lib) INCLUDE_LIB=false ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done
set -- "${POSITIONAL[@]}"

TARGET_ARM64="${1:-}"
ARM64_PYVER="${2:-}"

# ── Prerequisites ─────────────────────────────────────────────────────────────

if [ ! -d "$PROJECT_ROOT/api" ]; then
    echo -e "${RED}Error: api/ not found — run: python .vscode/gen_api.py${NC}"
    exit 1
fi

# Find metadata.json in src/<project>/
METADATA_FILE=$(find "$WORKSPACE_ROOT/src" -maxdepth 2 -name "metadata.json" 2>/dev/null | head -1)
if [ -z "$METADATA_FILE" ] || [ ! -f "$METADATA_FILE" ]; then
    echo -e "${RED}Error: metadata.json not found. Expected at src/<project>/metadata.json${NC}"
    exit 1
fi

PKG_DIR="$(dirname "$METADATA_FILE")"
PKG_DIR_NAME="$(basename "$PKG_DIR")"

if [ "$INCLUDE_LIB" = "true" ] && [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo -e "${YELLOW}No requirements.txt found — creating default${NC}"
    printf "grpcio>=1.62.0\nprotobuf>=4.25.0\n" > "$PROJECT_ROOT/requirements.txt"
fi

# ── Parse metadata.json ───────────────────────────────────────────────────────

eval "$(METADATA_LOAD_PATH="$METADATA_FILE" METADATA_DEFAULT_ENTRY="$PKG_DIR_NAME" python3 <<'PY'
import json, os, sys, shlex
path = os.environ["METADATA_LOAD_PATH"]
default_entry = os.environ["METADATA_DEFAULT_ENTRY"]
with open(path, encoding="utf-8") as f:
    d = json.load(f)
for k in ("package_id", "name", "version", "description"):
    if k not in d:
        print(f"missing required field {k!r} in {path}", file=sys.stderr)
        sys.exit(1)
if not str(d.get("version", "")).strip():
    print(f"metadata.json: non-empty \"version\" is required in {path}", file=sys.stderr)
    sys.exit(1)
entry = (d.get("entry_point") or default_entry).strip()
if not entry:
    print("entry_point (or directory name) must be non-empty", file=sys.stderr)
    sys.exit(1)
for k in ("package_id", "name", "version", "description"):
    print(f"export METADATA_{k.upper()}={shlex.quote(str(d[k]))}")
print(f"export METADATA_ENTRY_POINT={shlex.quote(entry)}")
print(f"export METADATA_PERMISSIONS={shlex.quote(json.dumps(d.get('permissions', [])))}")
print(f"export METADATA_DEPENDENCIES={shlex.quote(json.dumps(d.get('dependencies', [])))}")
PY
)"

ENTRY_POINT="$METADATA_ENTRY_POINT"
RELEASE_VERSION="$METADATA_VERSION"

# Resolve entry point file
ENTRY_FILE="$PKG_DIR/$ENTRY_POINT"
if [ ! -f "$ENTRY_FILE" ]; then
    echo -e "${RED}Error: ${ENTRY_POINT}.py not found in $PKG_DIR${NC}"
    exit 1
fi

# ── Build info ────────────────────────────────────────────────────────────────

BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo -e "${GREEN}=== Packaging ${METADATA_PACKAGE_ID} v${RELEASE_VERSION} ===${NC}"
echo -e "${GREEN}BuildDate: $BUILD_DATE | GitCommit: $GIT_COMMIT${NC}"

# ── Clean ─────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Cleaning previous build...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/bin" "$BUILD_DIR/lib" "$BUILD_DIR/META-INF" "$OUTPUT_DIR"

# ── Python dependencies into lib/ ─────────────────────────────────────────────

if [ "$INCLUDE_LIB" = "true" ]; then
    echo -e "${YELLOW}Installing Python dependencies into lib/...${NC}"

    if [ "$TARGET_ARM64" = "arm64" ]; then
        PYVER="${ARM64_PYVER:-$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')}"
        echo -e "${GREEN}Target: aarch64 (arm64), Python $PYVER${NC}"
        python3 -m pip install \
            --requirement "$PROJECT_ROOT/requirements.txt" \
            --target="$BUILD_DIR/lib" \
            --platform=manylinux2014_aarch64 \
            --python-version="$PYVER" \
            --implementation=cp \
            --only-binary=:all: \
            --upgrade --quiet
    else
        echo -e "${GREEN}Target: current platform${NC}"
        python3 -m pip install \
            --requirement "$PROJECT_ROOT/requirements.txt" \
            --target="$BUILD_DIR/lib" \
            --upgrade --quiet 2>/dev/null
    fi

    find "$BUILD_DIR/lib" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}✓ Python libs installed${NC}"
else
    echo -e "${YELLOW}Skipping lib/ (--no-lib)${NC}"
fi

# ── App-specific dependencies (from metadata.json "dependencies") ─────────────

if [[ -n "${METADATA_DEPENDENCIES:-}" ]] && [[ "$METADATA_DEPENDENCIES" != "[]" ]]; then
    TEMP_REQS=$(mktemp)
    python3 -c "
import json, sys
for dep in json.loads(sys.argv[1]):
    dep = dep.strip()
    if dep:
        print(dep)
" "$METADATA_DEPENDENCIES" > "$TEMP_REQS"
    if [[ -s "$TEMP_REQS" ]]; then
        echo -e "${YELLOW}Installing app dependencies...${NC}"
        if [ "$TARGET_ARM64" = "arm64" ]; then
            _PYVER="${ARM64_PYVER:-$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')}"
            python3 -m pip install \
                --requirement "$TEMP_REQS" \
                --target="$BUILD_DIR/lib" \
                --platform=manylinux2014_aarch64 \
                --python-version="$_PYVER" \
                --implementation=cp \
                --only-binary=:all: \
                --upgrade --quiet 2>/dev/null
        else
            python3 -m pip install \
                --requirement "$TEMP_REQS" \
                --target="$BUILD_DIR/lib" \
                --upgrade --quiet 2>/dev/null
        fi
        echo -e "${GREEN}✓ App deps installed${NC}"
    fi
    rm -f "$TEMP_REQS"
fi

# ── Install SDK into lib/ (pure Python, platform-independent) ─────────────────

echo -e "${YELLOW}Installing SDK into lib/...${NC}"
python3 -m pip install "$PROJECT_ROOT" \
    --target="$BUILD_DIR/lib" \
    --no-deps --upgrade --quiet 2>/dev/null

# Stamp build metadata into the installed SDK copy (never modifies source tree)
LIB_META="$BUILD_DIR/lib/metadata/metadata.py"
if [ -f "$LIB_META" ]; then
    sed -i "s/BASE_VERSION = \".*\"/BASE_VERSION = \"$RELEASE_VERSION\"/" "$LIB_META"
    sed -i "s/BUILD_DATE   = \".*\"/BUILD_DATE   = \"$BUILD_DATE\"/"   "$LIB_META"
    sed -i "s/GIT_COMMIT   = \".*\"/GIT_COMMIT   = \"$GIT_COMMIT\"/"   "$LIB_META"
    sed -i "s/ENTRY_POINT  = \".*\"/ENTRY_POINT  = \"$ENTRY_POINT\"/"  "$LIB_META"
    sed -i "s/PACKAGE_TYPE = \".*\"/PACKAGE_TYPE = \"python\"/"         "$LIB_META"
    if [ "$TARGET_ARM64" = "arm64" ]; then
        sed -i "s/BUILD_ARCH   = \".*\"/BUILD_ARCH   = \"arm64\"/"      "$LIB_META"
    fi
fi
find "$BUILD_DIR/lib" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
echo -e "${GREEN}✓ SDK installed${NC}"

# ── Copy app source into bin/ ─────────────────────────────────────────────────

echo -e "${YELLOW}Copying app source into bin/...${NC}"
cp -r "$PKG_DIR"/. "$BUILD_DIR/bin/"
rm -f "$BUILD_DIR/bin/metadata.json"
rm -rf "$BUILD_DIR/bin/orb"
find "$BUILD_DIR/bin" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
echo -e "${GREEN}✓ App source copied${NC}"

# ── manifest.json ─────────────────────────────────────────────────────────────

echo -e "${YELLOW}Generating manifest.json...${NC}"
export M_PACKAGE_ID="$METADATA_PACKAGE_ID" M_VERSION="$RELEASE_VERSION" \
    M_NAME="$METADATA_NAME" M_DESCRIPTION="$METADATA_DESCRIPTION" \
    M_TYPE="python" M_ARCHITECTURE="${TARGET_ARM64:-native}" \
    M_ENTRY_POINT="$ENTRY_POINT" M_BUILD_DATE="$BUILD_DATE" \
    M_GIT_COMMIT="$GIT_COMMIT" M_PERMISSIONS="$METADATA_PERMISSIONS"
python3 - <<'PY' >"$BUILD_DIR/manifest.json"
import json, os
from collections import OrderedDict
m = os.environ
manifest = OrderedDict([
    ("package_id",   m["M_PACKAGE_ID"]),
    ("version",      m["M_VERSION"]),
    ("name",         m["M_NAME"]),
    ("description",  m["M_DESCRIPTION"]),
    ("type",         m["M_TYPE"]),
    ("architecture", m["M_ARCHITECTURE"]),
    ("entry_point",  m["M_ENTRY_POINT"]),
    ("build_date",   m["M_BUILD_DATE"]),
    ("git_commit",   m["M_GIT_COMMIT"]),
    ("permissions",  json.loads(m.get("M_PERMISSIONS", "[]"))),
])
print(json.dumps(manifest, indent=2) + "\n")
PY
echo -e "${GREEN}✓ manifest.json created${NC}"

# ── orb/ assets ───────────────────────────────────────────────────────────────

ORB_ASSET_DIR="$PKG_DIR/orb"
if [[ -d "$ORB_ASSET_DIR" ]] && [[ -n "$(ls -A "$ORB_ASSET_DIR" 2>/dev/null)" ]]; then
    echo -e "${YELLOW}Packing orb/ → ORB root...${NC}"
    cp -a "$ORB_ASSET_DIR"/. "$BUILD_DIR/"
    echo -e "${GREEN}✓ orb/ contents at ORB root${NC}"
fi

# ── Package ───────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Creating ORB package...${NC}"
ORB_SLUG="${ENTRY_POINT%.*}"
ORB_NAME="${ORB_SLUG}_v${RELEASE_VERSION}.orb"
cd "$BUILD_DIR"
printf "ORB File\n" | zip -r -q -z "$ORB_NAME" . -x"./${ORB_NAME}" > /dev/null
mv "$ORB_NAME" "$OUTPUT_DIR/"
cd "$WORKSPACE_ROOT"
rm -rf "$BUILD_DIR"

echo -e "${GREEN}=== Package created ===${NC}"
echo -e "${GREEN}Path: $OUTPUT_DIR/$ORB_NAME${NC}"
echo -e "${GREEN}Size: $(du -h "$OUTPUT_DIR/$ORB_NAME" | cut -f1)${NC}"
