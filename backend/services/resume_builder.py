from __future__ import annotations


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _build_summary(input_data: dict, jd_data: dict) -> str:
    role = str(jd_data.get("role") or "target role").strip()
    skills = _dedupe_preserve_order(list(jd_data.get("skills") or []) + list(input_data.get("skills") or []))[:4]
    if skills:
        return f"Results-oriented candidate targeting {role}, with experience across {', '.join(skills)}."
    return f"Results-oriented candidate targeting {role}, with strong delivery, problem-solving, and execution focus."


def build_resume(input_data: dict, jd_data: dict) -> dict:
    bullets = _dedupe_preserve_order(list(input_data.get("bullets") or []))
    skills = _dedupe_preserve_order(list(input_data.get("skills") or []) + list(jd_data.get("skills") or []))[:16]

    experience: list[dict] = []
    projects: list[dict] = []
    for index, bullet in enumerate(bullets):
        target = experience if index < 4 else projects
        target.append(
            {
                "title": f"{'Experience' if target is experience else 'Project'} {len(target) + 1}",
                "bullets": [bullet],
            }
        )

    return {
        "summary": _build_summary(input_data, jd_data),
        "skills": skills,
        "experience": experience,
        "projects": projects,
    }
