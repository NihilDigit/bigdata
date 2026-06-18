#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def inline_markup(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def render_table(lines: list[str]) -> str:
    rows = []
    for line in lines:
        cells = [inline_markup(cell.strip()) for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return "\n".join(f"<p>{inline_markup(line)}</p>" for line in lines)

    head = rows[0]
    body = rows[2:]
    head_html = "".join(f"<th>{cell}</th>" for cell in head)
    body_html = "\n".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in body
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def render_markdown(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    table: list[str] = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            output.append(f"<p>{inline_markup(' '.join(paragraph))}</p>")
            paragraph = []

    def flush_table() -> None:
        nonlocal table
        if table:
            output.append(render_table(table))
            table = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                output.append(
                    f'<pre><code class="language-{html.escape(code_lang)}">'
                    + html.escape("\n".join(code_lines))
                    + "</code></pre>"
                )
                in_code = False
                code_lang = ""
                code_lines = []
            else:
                flush_paragraph()
                flush_table()
                in_code = True
                code_lang = line.removeprefix("```").strip()
            continue

        if in_code:
            code_lines.append(line)
            continue

        image_match = re.fullmatch(r"\{\{IMG: ([^}]+)\}\}", line.strip())
        if image_match:
            flush_paragraph()
            flush_table()
            src = image_match.group(1)
            output.append(f'<figure><img src="../{html.escape(src)}" alt="" /></figure>')
            continue

        if line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            table.append(line)
            continue
        if table:
            flush_table()

        if not line.strip():
            flush_paragraph()
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            output.append(f"<h{level}>{inline_markup(heading_match.group(2))}</h{level}>")
            continue

        list_match = re.match(r"^(\d+\.|-)\s+(.*)$", line)
        if list_match:
            flush_paragraph()
            output.append(f"<p class=\"list-line\">{inline_markup(line)}</p>")
            continue

        paragraph.append(line.strip())

    flush_paragraph()
    flush_table()
    return "\n".join(output)


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports" / "实验报告.md"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "reports" / "实验报告.html"
    body = render_markdown(src.read_text(encoding="utf-8"))
    dst.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>气象大数据采集、分析与可视化系统实验报告</title>
  <style>
    body {{
      margin: 0;
      background: #f5f7f9;
      color: #1f2933;
      font-family: "Source Han Sans SC", "Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei", system-ui, sans-serif;
      line-height: 1.75;
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
      background: #fff;
      padding: 42px 54px 72px;
      box-shadow: 0 18px 60px rgba(15, 23, 42, 0.08);
    }}
    h1 {{ font-size: 26px; text-align: center; margin: 0 0 32px; }}
    h2 {{ font-size: 21px; margin: 34px 0 14px; border-bottom: 1px solid #d9e0e7; padding-bottom: 8px; }}
    h3 {{ font-size: 17px; margin: 28px 0 10px; }}
    p {{ margin: 9px 0; }}
    .list-line {{ padding-left: 1em; text-indent: -1em; }}
    code {{ font-family: "JetBrains Mono", "Noto Sans Mono", monospace; background: #f1f5f7; padding: 1px 4px; border-radius: 4px; }}
    pre {{
      overflow: auto;
      background: #252a33;
      color: #edf2f7;
      border-radius: 8px;
      padding: 14px 16px;
      line-height: 1.55;
      font-size: 13px;
    }}
    pre code {{ background: transparent; padding: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 18px; font-size: 14px; }}
    th, td {{ border: 1px solid #d9e0e7; padding: 8px 10px; text-align: left; }}
    th {{ background: #f3f6f8; }}
    figure {{ margin: 18px 0 8px; text-align: center; }}
    img {{ max-width: 100%; border: 1px solid #d9e0e7; border-radius: 6px; }}
    strong {{ font-weight: 700; }}
    @media print {{
      body {{ background: #fff; }}
      main {{ box-shadow: none; padding: 0; }}
      figure, pre, table {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <main>
{body}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
