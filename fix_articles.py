#!/usr/bin/env python3
import html
import re
from pathlib import Path
from urllib.parse import quote_plus

# VUL HIER JE BLOGMAP IN (standaard: "content")
ARTICLE_DIR = Path("content")

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm"}

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
H1_MD_RE = re.compile(r"(?m)^\s*#\s+\S")
H1_HTML_RE = re.compile(r"<h1\b[^>]*>\s*.*?\S.*?</h1>", re.IGNORECASE | re.DOTALL)

IMG_PLACEHOLDER_HTML_RE = re.compile(
    r'(<img\b[^>]*\bsrc=["\'])https?://example\.com(?:/[^"\']*)?(["\'])',
    re.IGNORECASE,
)
IMG_PLACEHOLDER_MD_RE = re.compile(
    r'(!\[[^\]]*\]\()https?://example\.com(?:/[^)\s]*)?(\))',
    re.IGNORECASE,
)
IMG_PLACEHOLDER_FM_RE = re.compile(
    r'(?mi)^(image(?:_url)?\s*:\s*[\'"]?)https?://example\.com[^\s\'"]*([\'"]?\s*)$'
)

TITLE_FM_LINE_RE = re.compile(r"(?mi)^title\s*:\s*(.*)$")


def slug_to_title(slug: str) -> str:
    tokens = re.split(r"[-_]+", slug.strip())
    acronyms = {"nl": "NL", "btw": "BTW", "dao": "DAO", "defi": "DeFi", "btc": "BTC", "eth": "ETH"}
    words = []
    for token in tokens:
        if not token:
            continue
        lower = token.lower()
        if lower in acronyms:
            words.append(acronyms[lower])
        else:
            words.append(lower.capitalize())
    return " ".join(words) if words else "Artikel"


def build_unsplash_url(seed_text: str) -> str:
    terms = ["crypto", "tax", "netherlands"]
    extra = re.findall(r"[a-zA-Z0-9]+", seed_text.lower())
    for t in extra:
        if t not in terms and len(t) > 2:
            terms.append(t)
        if len(terms) >= 6:
            break
    query = ",".join(terms)
    return f"https://source.unsplash.com/1600x900/?{quote_plus(query)}"


def replace_placeholder_images(text: str, unsplash_url: str) -> str:
    text = IMG_PLACEHOLDER_HTML_RE.sub(rf"\1{unsplash_url}\2", text)
    text = IMG_PLACEHOLDER_MD_RE.sub(rf"\1{unsplash_url}\2", text)
    return text


def extract_front_matter(text: str):
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return "", text, False
    front_matter = match.group(1)
    body = text[match.end() :]
    return front_matter, body, True


def ensure_front_matter_title(front_matter: str, title: str) -> str:
    if TITLE_FM_LINE_RE.search(front_matter):
        def _replace(m):
            current = (m.group(1) or "").strip().strip('"').strip("'")
            if current:
                return m.group(0)
            return f'title: "{title}"'

        return TITLE_FM_LINE_RE.sub(_replace, front_matter, count=1)
    return front_matter.rstrip() + f'\ntitle: "{title}"\n'


def process_markdown_like(path: Path, raw: str) -> str:
    slug_title = slug_to_title(path.stem)
    front_matter, body, has_fm = extract_front_matter(raw)

    title = slug_title
    if has_fm:
        m = TITLE_FM_LINE_RE.search(front_matter)
        if m:
            candidate = (m.group(1) or "").strip().strip('"').strip("'")
            if candidate:
                title = candidate

    unsplash_url = build_unsplash_url(f"{title} {path.stem}")

    if not H1_MD_RE.search(body):
        body = f"# {title}\n\n" + body.lstrip()

    body = replace_placeholder_images(body, unsplash_url)

    if has_fm:
        front_matter = ensure_front_matter_title(front_matter, title)
        front_matter = IMG_PLACEHOLDER_FM_RE.sub(rf"\1{unsplash_url}\2", front_matter)
        return f"---\n{front_matter.strip()}\n---\n\n{body.lstrip()}"
    return body


def inject_h1_into_html(raw: str, title: str) -> str:
    if H1_HTML_RE.search(raw):
        return raw

    h1 = f"<h1>{html.escape(title)}</h1>\n"

    for tag_pattern in [r"(<article\b[^>]*>)", r"(<main\b[^>]*>)", r"(<body\b[^>]*>)"]:
        updated, count = re.subn(tag_pattern, r"\1\n" + h1, raw, count=1, flags=re.IGNORECASE)
        if count:
            return updated

    return h1 + raw


def process_html(path: Path, raw: str) -> str:
    title = slug_to_title(path.stem)
    unsplash_url = build_unsplash_url(f"{title} {path.stem}")

    updated = inject_h1_into_html(raw, title)
    updated = replace_placeholder_images(updated, unsplash_url)
    return updated


def main():
    if not ARTICLE_DIR.exists():
        raise FileNotFoundError(
            f"Map niet gevonden: {ARTICLE_DIR}. "
            "Pas ARTICLE_DIR bovenin fix_articles.py aan naar jouw artikelmap."
        )

    changed = 0
    scanned = 0

    for file_path in ARTICLE_DIR.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        scanned += 1
        original = file_path.read_text(encoding="utf-8")

        if file_path.suffix.lower() in {".html", ".htm"}:
            updated = process_html(file_path, original)
        else:
            updated = process_markdown_like(file_path, original)

        if updated != original:
            file_path.write_text(updated, encoding="utf-8")
            changed += 1
            print(f"[UPDATED] {file_path}")

    print(f"Klaar. Gescand: {scanned}, Aangepast: {changed}")


if __name__ == "__main__":
    main()
