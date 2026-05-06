#!/usr/bin/env bash
# Build the showcase demo deck from source.
#
#   loop.mmd  → loop.svg     (Mermaid CLI)
#   demo.md   → demo.html    (Marp CLI)
#   demo.md   → demo.pptx    (Marp CLI)
#   demo.md   → demo.pdf     (Marp CLI, when --pdf is passed)
#
# Mermaid is rendered separately because Marp does not execute JavaScript at
# render time — embedded ```mermaid``` fences would not appear in exported
# files. Pre-rendering to SVG once keeps the deck portable.
#
# Usage:
#   ./build.sh           # html + pptx
#   ./build.sh --pdf     # html + pptx + pdf
#   ./build.sh --clean   # delete generated artifacts and rebuild
#   ./build.sh --help    # this message

set -euo pipefail

# Always operate on this script's directory, regardless of cwd.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

want_pdf=0
want_clean=0
for arg in "$@"; do
  case "$arg" in
    --pdf)   want_pdf=1 ;;
    --clean) want_clean=1 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "build.sh: unknown argument: $arg" >&2
      echo "run with --help for usage" >&2
      exit 2
      ;;
  esac
done

mmd_src="loop.mmd"
svg_out="loop.svg"
md_src="demo.md"
html_out="demo.html"
pptx_out="demo.pptx"
pdf_out="demo.pdf"

for required in "$mmd_src" "$md_src"; do
  if [ ! -f "$required" ]; then
    echo "build.sh: required source file not found: $required" >&2
    exit 1
  fi
done

if [ "$want_clean" -eq 1 ]; then
  echo "[clean] removing generated artifacts"
  rm -f -- "$svg_out" "$html_out" "$pptx_out" "$pdf_out"
fi

# Render Mermaid → SVG only when the source is newer than the output.
# Skipping when SVG is fresh saves ~5s on every run.
if [ ! -f "$svg_out" ] || [ "$mmd_src" -nt "$svg_out" ]; then
  echo "[mermaid] $mmd_src → $svg_out"
  npx --yes @mermaid-js/mermaid-cli@latest \
    -i "$mmd_src" \
    -o "$svg_out" \
    -b transparent
else
  echo "[mermaid] $svg_out is up-to-date (skipped)"
fi

marp_cmd=(npx --yes @marp-team/marp-cli@latest --allow-local-files "$md_src")

echo "[marp] $md_src → $html_out"
"${marp_cmd[@]}" --html -o "$html_out"

echo "[marp] $md_src → $pptx_out"
"${marp_cmd[@]}" -o "$pptx_out"

if [ "$want_pdf" -eq 1 ]; then
  echo "[marp] $md_src → $pdf_out"
  "${marp_cmd[@]}" --pdf -o "$pdf_out"
fi

echo
echo "Done. Artifacts in $(pwd):"
for f in "$svg_out" "$html_out" "$pptx_out" "$pdf_out"; do
  if [ -f "$f" ]; then
    size=$(ls -lh "$f" | awk '{print $5}')
    printf "  %s  %s\n" "$size" "$f"
  fi
done
