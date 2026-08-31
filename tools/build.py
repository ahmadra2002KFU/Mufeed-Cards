"""Build the Mufeed cards site.

Reads people/<slug>/card.json (+ optional photo.jpg/photo.png), renders
template/card.html for each person, generates their vCard (photo embedded
when available), and writes everything to site/ ready for GitHub Pages.
The root page comes from template/index.html (team list + add-your-card tool).

Run from the repo root: python tools/build.py
"""

import base64
import html
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PEOPLE = ROOT / "people"
SITE = ROOT / "site"
DOMAIN = "cards.mufeedai.com"

try:
    from PIL import Image
except ImportError:
    print("Pillow is required: pip install pillow", file=sys.stderr)
    sys.exit(1)


def fold(line: str, limit: int = 75) -> list[str]:
    """vCard 3.0 line folding: continuation lines start with one space."""
    out = [line[:limit]]
    line = line[limit:]
    while line:
        out.append(" " + line[: limit - 1])
        line = line[limit - 1 :]
    return out


def build_vcf(p: dict, photo: Path | None) -> str:
    v = p["vcard"]
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N;CHARSET=UTF-8:{v['family']};{v['given']};{v.get('middle', '')};;",
        f"FN;CHARSET=UTF-8:{p['full_name_en']}",
    ]
    if p.get("phonetic_first_ar"):
        lines.append(f"X-PHONETIC-FIRST-NAME;CHARSET=UTF-8:{p['phonetic_first_ar']}")
    if p.get("phonetic_last_ar"):
        lines.append(f"X-PHONETIC-LAST-NAME;CHARSET=UTF-8:{p['phonetic_last_ar']}")
    if p.get("org"):
        lines.append(f"ORG;CHARSET=UTF-8:{p['org']}")
    if p.get("title_en"):
        lines.append(f"TITLE;CHARSET=UTF-8:{p['title_en']}")
    lines.append(f"TEL;TYPE=CELL:{p['phone']}")
    if p.get("email"):
        lines.append(f"EMAIL;TYPE=WORK:{p['email']}")
    if p.get("website"):
        lines.append(f"URL:{p['website']}")
    if p.get("linkedin"):
        lines += [f"item1.URL:{p['linkedin']}", "item1.X-ABLabel:LinkedIn"]
    if photo:
        im = Image.open(photo).convert("RGB")
        im.thumbnail((320, 320), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        lines.append("PHOTO;ENCODING=b;TYPE=JPEG:" + b64)
    if p.get("notes"):
        lines.append(f"NOTE;CHARSET=UTF-8:{p['notes']}")
    lines.append("END:VCARD")
    folded: list[str] = []
    for line in lines:
        folded.extend(fold(line))
    return "\r\n".join(folded) + "\r\n"


def render_card(template: str, p: dict, slug: str, has_photo: bool) -> str:
    if has_photo:
        portrait = (
            f'<div class="portrait"><img src="photo.jpg" '
            f'alt="{html.escape(p["name_en"])}"></div>'
        )
    else:
        portrait = (
            '<div class="portrait seal" aria-hidden="true">'
            f'<span data-ar="{html.escape(p["monogram_ar"])}" '
            f'data-en="{html.escape(p["monogram_en"])}">'
            f'{html.escape(p["monogram_en"])}</span></div>'
        )
    card_json = json.dumps(
        {
            "url": "",  # empty = the page's own URL (QR + Android fallback)
            "phone": p["phone"],
            "whatsapp": p.get("whatsapp", ""),
            "email": p.get("email", ""),
            "website": p.get("website", ""),
            "linkedin": p.get("linkedin", ""),
            "fullName": p["full_name_en"],
            "jobTitle": p.get("title_en", ""),
            "org": p.get("org", ""),
            "notes": p.get("notes", ""),
            "vcf": f"{slug}.vcf",
        },
        ensure_ascii=False,
    )
    role_parts = []
    if p.get("title_en"):
        role_parts.append(
            f'<span data-ar="{html.escape(p.get("title_ar") or p["title_en"])}" '
            f'data-en="{html.escape(p["title_en"])}">{html.escape(p["title_en"])}</span>'
        )
    if p.get("title_en") and p.get("org"):
        role_parts.append('<span aria-hidden="true"> · </span>')
    if p.get("org"):
        role_parts.append(
            f'<span class="org" data-ar="{html.escape(p.get("org_ar") or p["org"])}" '
            f'data-en="{html.escape(p["org"])}">{html.escape(p["org"])}</span>'
        )
    role_html = f'<p class="role">{"".join(role_parts)}</p>' if role_parts else ""
    tokens = {
        "{{NAME_EN}}": html.escape(p["name_en"]),
        "{{NAME_AR}}": html.escape(p["name_ar"]),
        "{{ROLE_HTML}}": role_html,
        "{{ORG_EN}}": html.escape(p.get("org") or "Mufeed"),
        "{{PORTRAIT}}": portrait,
        "{{VCF_FILE}}": f"{slug}.vcf",
        "{{VCF_DOWNLOAD}}": f"{p['full_name_en'].replace(' ', '-')}.vcf",
        "{{CARD_JSON}}": card_json,
    }
    out = template
    for k, val in tokens.items():
        out = out.replace(k, val)
    return out


def render_directory(entries: list[dict]) -> str:
    rows = "\n".join(
        f'    <a class="person" href="/{e["slug"]}/">'
        f'<strong data-ar="{html.escape(e["name_ar"])}" data-en="{html.escape(e["name_en"])}">'
        f'{html.escape(e["name_en"])}</strong>'
        f'<span data-ar="{html.escape(e.get("title_ar") or e.get("title_en", ""))}" '
        f'data-en="{html.escape(e.get("title_en", ""))}">'
        f'{html.escape(e.get("title_en", ""))}</span></a>'
        for e in entries
    )
    template = (ROOT / "template" / "index.html").read_text(encoding="utf-8")
    return template.replace("{{PEOPLE_LIST}}", rows)


def main() -> None:
    template = (ROOT / "template" / "card.html").read_text(encoding="utf-8")
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    shutil.copy(ROOT / "template" / "qrcode.min.js", SITE / "qrcode.min.js")
    shutil.copy(ROOT / "template" / "logo-white.png", SITE / "logo-white.png")
    shutil.copy(ROOT / "template" / "logo-ink.png", SITE / "logo-ink.png")
    (SITE / "CNAME").write_text(DOMAIN + "\n", encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    entries = []
    for person_dir in sorted(PEOPLE.iterdir()):
        cfg = person_dir / "card.json"
        if not cfg.is_file():
            continue
        slug = person_dir.name
        p = json.loads(cfg.read_text(encoding="utf-8"))
        photo = next(
            (person_dir / n for n in ("photo.jpg", "photo.png")
             if (person_dir / n).is_file()),
            None,
        )
        out = SITE / slug
        out.mkdir()
        (out / "index.html").write_text(
            render_card(template, p, slug, photo is not None),
            encoding="utf-8", newline="\n",
        )
        with open(out / f"{slug}.vcf", "w", encoding="utf-8", newline="") as f:
            f.write(build_vcf(p, photo))
        if photo:
            im = Image.open(photo).convert("RGB")
            im.thumbnail((640, 640), Image.LANCZOS)
            im.save(out / "photo.jpg", "JPEG", quality=88, optimize=True)
        entries.append({"slug": slug, **p})
        print(f"built /{slug}/ (photo: {'yes' if photo else 'no'})")

    (SITE / "index.html").write_text(
        render_directory(entries), encoding="utf-8", newline="\n"
    )
    print(f"done: {len(entries)} card(s) -> site/")


if __name__ == "__main__":
    main()
