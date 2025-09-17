from pathlib import Path

path = Path("app/templates/analyze/result.html")
lines = path.read_text().splitlines(keepends=True)
needle = "                  <div class=\"accordion-body p-0\">\n"
try:
    idx = lines.index(needle)
except ValueError:
    raise SystemExit("accordion body line not found")
insert = [
    "                  <div class=\"accordion-body p-0\">\n",
    "                    <div class=\"category-intro px-3 py-2 text-muted small\" style=\"background: rgba(103, 126, 234, 0.08); border-left: 3px solid {{ category_colors.get(cat, '#667eea') }};\">\n",
    "                      <strong>Why this category matters:</strong> {{ category_intros.get(cat) }}\n",
    "                    </div>\n",
]
lines[idx:idx+1] = insert
path.write_text(''.join(lines))
