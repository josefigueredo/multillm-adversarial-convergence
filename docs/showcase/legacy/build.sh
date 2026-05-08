#!/usr/bin/env bash
# Build the showcase demo decks from source.
#
#   *.mmd · patterns/*.mmd  → *.svg     (Mermaid CLI)
#   demo*.md                → *.html    (Marp CLI)
#   demo*.md                → *.pptx    (Marp CLI)
#   demo*.md                → *.pdf     (Marp CLI, only with --pdf)
#
# Mermaid is rendered separately because Marp does not execute JavaScript at
# render time — embedded ```mermaid``` fences would not appear in exported
# files. Pre-rendering to SVG once keeps the deck portable.
#
# Usage:
#   ./build.sh                  # render every demo*.md to html + pptx
#   ./build.sh --pdf            # also generate pdf
#   ./build.sh --clean          # delete generated artifacts and rebuild
#   ./build.sh demo.md          # build only this deck (still renders all SVGs)
#   ./build.sh --help

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

want_pdf=0
want_clean=0
explicit_decks=()
for arg in "$@"; do
  case "$arg" in
    --pdf)   want_pdf=1 ;;
    --clean) want_clean=1 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "build.sh: unknown flag: $arg" >&2
      echo "run with --help for usage" >&2
      exit 2
      ;;
    *)
      if [ -f "$arg" ]; then
        explicit_decks+=("$arg")
      else
        echo "build.sh: deck not found: $arg" >&2
        exit 1
      fi
      ;;
  esac
done

# All mermaid sources: top-level + patterns/. Use nullglob so the loop is
# silent if a directory is empty.
shopt -s nullglob
mmd_sources=( *.mmd patterns/*.mmd )
shopt -u nullglob

# Decks: explicit list if provided, otherwise everything matching demo*.md.
if [ ${#explicit_decks[@]} -gt 0 ]; then
  decks=( "${explicit_decks[@]}" )
else
  shopt -s nullglob
  decks=( demo*.md )
  shopt -u nullglob
fi

if [ ${#decks[@]} -eq 0 ]; then
  echo "build.sh: no demo*.md decks found" >&2
  exit 1
fi

if [ "$want_clean" -eq 1 ]; then
  echo "[clean] removing generated artifacts"
  for mmd_src in "${mmd_sources[@]}"; do
    rm -f -- "${mmd_src%.mmd}.svg"
  done
  for md_src in "${decks[@]}"; do
    base="${md_src%.md}"
    rm -f -- "${base}.html" "${base}.pptx" "${base}.pdf"
  done
fi

# Render mermaid sources. Skip when SVG mtime is newer than MMD mtime.
for mmd_src in "${mmd_sources[@]}"; do
  svg_out="${mmd_src%.mmd}.svg"
  if [ ! -f "$svg_out" ] || [ "$mmd_src" -nt "$svg_out" ]; then
    echo "[mermaid] $mmd_src → $svg_out"
    npx --yes @mermaid-js/mermaid-cli@latest \
      -i "$mmd_src" \
      -o "$svg_out" \
      -b transparent
  else
    echo "[mermaid] $svg_out is up-to-date (skipped)"
  fi
done

# Render every deck to HTML + PPTX (and PDF when requested).
for md_src in "${decks[@]}"; do
  base="${md_src%.md}"
  echo "[marp] $md_src → ${base}.html"
  npx --yes @marp-team/marp-cli@latest --allow-local-files "$md_src" --html -o "${base}.html"

  echo "[marp] $md_src → ${base}.pptx"
  npx --yes @marp-team/marp-cli@latest --allow-local-files "$md_src" -o "${base}.pptx"

  if [ "$want_pdf" -eq 1 ]; then
    echo "[marp] $md_src → ${base}.pdf"
    npx --yes @marp-team/marp-cli@latest --allow-local-files "$md_src" --pdf -o "${base}.pdf"
  fi
done

echo
echo "Done. Artifacts in $(pwd):"
shopt -s nullglob
for f in *.svg patterns/*.svg *.html *.pptx *.pdf; do
  size=$(ls -lh "$f" | awk '{print $5}')
  printf "  %s  %s\n" "$size" "$f"
done
shopt -u nullglob
