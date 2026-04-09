from __future__ import annotations

from html import escape


def _render_section(title: str, entries: list[dict]) -> str:
    if not entries:
        return ""

    blocks: list[str] = [f"<h2>{escape(title)}</h2>"]
    for entry in entries:
        entry_title = escape(str(entry.get("title") or ""))
        bullets = entry.get("bullets") or []
        bullet_html = "".join(f"<li>{escape(str(bullet))}</li>" for bullet in bullets if str(bullet or "").strip())
        blocks.append(f"<div class='block'><h3>{entry_title}</h3><ul>{bullet_html}</ul></div>")
    return "".join(blocks)


def _render_html(resume_json: dict) -> str:
    skills = "".join(f"<li>{escape(str(skill))}</li>" for skill in resume_json.get("skills", []))
    return f"""
    <html>
      <head>
        <style>
          body {{
            font-family: Arial, sans-serif;
            color: #111827;
            padding: 28px;
            line-height: 1.45;
          }}
          h1, h2, h3 {{ margin: 0 0 10px; }}
          h1 {{ font-size: 24px; }}
          h2 {{
            margin-top: 24px;
            font-size: 16px;
            text-transform: uppercase;
            border-bottom: 1px solid #d1d5db;
            padding-bottom: 6px;
          }}
          h3 {{ font-size: 14px; margin-top: 12px; }}
          p {{ margin: 0; }}
          ul {{ margin: 8px 0 0 18px; padding: 0; }}
          li {{ margin-bottom: 6px; }}
          .skills {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            list-style: none;
            margin: 10px 0 0;
            padding: 0;
          }}
          .skills li {{
            background: #f3f4f6;
            border-radius: 999px;
            padding: 4px 10px;
            margin: 0;
          }}
          .block {{
            margin-top: 10px;
          }}
        </style>
      </head>
      <body>
        <h1>RolePrep Resume Draft</h1>
        <p>{escape(str(resume_json.get("summary") or ""))}</p>
        <h2>Skills</h2>
        <ul class="skills">{skills}</ul>
        {_render_section("Experience", list(resume_json.get("experience") or []))}
        {_render_section("Projects", list(resume_json.get("projects") or []))}
      </body>
    </html>
    """


def generate_pdf(resume_json: dict) -> bytes:
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("WeasyPrint is required for PDF generation") from exc

    html = _render_html(resume_json)
    return HTML(string=html).write_pdf()
