#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from openai import OpenAI

SITE_URL = "https://www.cryptobelastinggids.nl"
ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
TOPICS_FILE = ROOT / "topics.txt"
AFFILIATES_FILE = ROOT / "affiliates.json"
INDEX_FILE = CONTENT_DIR / "index.json"
SITEMAP_FILE = ROOT / "sitemap.xml"
ROBOTS_FILE = ROOT / "robots.txt"


@dataclass(frozen=True)
class AffiliateRule:
  keyword: str
  url: str


def slugify(text: str) -> str:
  slug = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
  slug = re.sub(r"[\s_]+", "-", slug)
  slug = re.sub(r"-{2,}", "-", slug)
  return slug or f"post-{int(datetime.now(timezone.utc).timestamp())}"


def trim_to_limit(value: str, limit: int) -> str:
  cleaned = re.sub(r"\s+", " ", (value or "").strip())
  if len(cleaned) <= limit:
    return cleaned
  return cleaned[: limit - 1].rstrip() + "…"


def quote_yaml_value(value: str) -> str:
  return json.dumps(value, ensure_ascii=False)


def read_top_topics(path: Path, amount: int = 2) -> tuple[list[str], list[str]]:
  if not path.exists():
    raise FileNotFoundError(f"Missing topics file: {path}")

  lines = path.read_text(encoding="utf-8").splitlines()
  selected_indices: list[int] = []
  selected_topics: list[str] = []

  for idx, line in enumerate(lines):
    value = line.strip()
    if not value:
      continue
    selected_indices.append(idx)
    selected_topics.append(value)
    if len(selected_topics) == amount:
      break

  if not selected_topics:
    return [], lines

  selected_index_set = set(selected_indices)
  remaining = [line for idx, line in enumerate(lines) if idx not in selected_index_set]
  return selected_topics, remaining


def write_remaining_topics(path: Path, remaining_lines: list[str]) -> None:
  payload = "\n".join(remaining_lines).strip()
  if payload:
    path.write_text(payload + "\n", encoding="utf-8")
  else:
    path.write_text("", encoding="utf-8")


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
  lines = text.splitlines()
  if not lines or lines[0].strip() != "---":
    return {}, text

  fm_lines: list[str] = []
  closing_index = None
  for idx in range(1, len(lines)):
    if lines[idx].strip() == "---":
      closing_index = idx
      break
    fm_lines.append(lines[idx])

  if closing_index is None:
    return {}, text

  metadata: dict[str, str] = {}
  for line in fm_lines:
    if ":" not in line:
      continue
    key, raw_value = line.split(":", 1)
    key = key.strip()
    value = raw_value.strip()
    if not key:
      continue
    if value:
      try:
        metadata[key] = json.loads(value)
      except json.JSONDecodeError:
        metadata[key] = value.strip('"')
    else:
      metadata[key] = ""

  body = "\n".join(lines[closing_index + 1 :]).lstrip("\n")
  return metadata, body


def strip_leading_h1(markdown: str) -> str:
  lines = markdown.splitlines()
  stripped: list[str] = []
  removed = False
  for line in lines:
    if not removed and line.lstrip().startswith("# "):
      removed = True
      continue
    stripped.append(line)
  return "\n".join(stripped).strip()


def generate_article(client: OpenAI, topic: str) -> dict[str, str]:
  prompt = f"""
Geef een hoogwaardig Nederlands SEO-artikel over: "{topic}".

Retourneer uitsluitend geldige JSON met deze sleutels:
- title: de artikelkop in het Nederlands
- meta_title: een klikwaardige meta title (max 60 tekens)
- meta_description: een pakkende meta description (max 155 tekens)
- content_markdown: het volledige artikel in Markdown

Regels:
- Schrijf ongeveer 1200 woorden.
- Schrijf in professioneel, helder Nederlands.
- Gebruik alleen een intro en secties met H2/H3; voeg geen H1 toe in de body.
- Gebruik echte Markdown-opmaak voor koppen, lijsten, vetgedrukte tekst en links.
- Gebruik alleen beschrijvende alt-teksten bij afbeeldingen en voorkom raw HTML img-tags.
- Maak de content SEO-vriendelijk, maar natuurlijk leesbaar.
- Geen code fences, geen extra uitleg, alleen JSON.
""".strip()

  response = client.chat.completions.create(
    model="gpt-4o",
    temperature=0.7,
    messages=[
      {"role": "system", "content": "You are an expert Dutch SEO blog writer."},
      {"role": "user", "content": prompt},
    ],
  )

  raw = response.choices[0].message.content
  if not raw:
    raise RuntimeError(f"Empty response for topic: {topic}")

  try:
    payload = json.loads(raw)
  except json.JSONDecodeError as exc:
    raise RuntimeError(f"Model returned invalid JSON for topic: {topic}") from exc

  title = str(payload.get("title", "")).strip() or topic
  meta_title = trim_to_limit(str(payload.get("meta_title", "")).strip() or title, 60)
  content_markdown = str(payload.get("content_markdown", "")).strip()

  if not content_markdown:
    raise RuntimeError(f"Missing content_markdown for topic: {topic}")

  plain_body = re.sub(r"<[^>]+>", "", content_markdown)
  plain_body = re.sub(r"[#>*_`]", "", plain_body)
  fallback_description = trim_to_limit(re.sub(r"\s+", " ", plain_body).strip()[:155], 155)
  meta_description = trim_to_limit(str(payload.get("meta_description", "")).strip() or fallback_description or title, 155)

  return {
    "title": title,
    "meta_title": meta_title,
    "meta_description": meta_description,
    "content_markdown": content_markdown,
  }


def save_generated_post(topic: str, article: dict[str, str]) -> Path:
  CONTENT_DIR.mkdir(parents=True, exist_ok=True)
  base_slug = slugify(topic)
  output = CONTENT_DIR / f"{base_slug}.md"

  if output.exists():
    output = CONTENT_DIR / f"{base_slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.md"

  published_at = datetime.now(timezone.utc).isoformat()
  body = strip_leading_h1(article["content_markdown"])
  front_matter = "\n".join(
    [
      "---",
      f"title: {quote_yaml_value(article['title'])}",
      f"meta_title: {quote_yaml_value(article['meta_title'])}",
      f"meta_description: {quote_yaml_value(article['meta_description'])}",
      f"slug: {quote_yaml_value(output.stem)}",
      f"topic: {quote_yaml_value(topic)}",
      f"published_at: {quote_yaml_value(published_at)}",
      "---",
      "",
    ]
  )

  output.write_text(front_matter + body.strip() + "\n", encoding="utf-8")
  return output


def load_affiliate_rules(path: Path) -> list[AffiliateRule]:
  data = json.loads(path.read_text(encoding="utf-8"))
  raw_keywords = data.get("keywords", {})
  if not isinstance(raw_keywords, dict):
    raise ValueError("affiliates.json must contain a `keywords` object")

  rules = [AffiliateRule(keyword=k, url=v) for k, v in raw_keywords.items() if k and v]
  rules.sort(key=lambda r: len(r.keyword), reverse=True)
  return rules


def split_front_matter_block(text: str) -> tuple[str, str, bool]:
  lines = text.splitlines(keepends=True)
  if not lines or lines[0].strip() != "---":
    return "", text, False

  closing_index = None
  for idx in range(1, len(lines)):
    if lines[idx].strip() == "---":
      closing_index = idx
      break

  if closing_index is None:
    return "", text, False

  front_matter = "".join(lines[: closing_index + 1])
  body = "".join(lines[closing_index + 1 :])
  return front_matter, body, True


def inject_links_in_text(text: str, rules: list[AffiliateRule]) -> str:
  anchor_or_markdown_link = re.compile(r"(<a\b[^>]*>.*?</a>|\[[^\]]+\]\([^)]+\))", re.IGNORECASE | re.DOTALL)
  front_matter, body, has_front_matter = split_front_matter_block(text)

  def replace_keyword(segment: str, rule: AffiliateRule) -> str:
    pattern = re.compile(rf"(?<![\w])({re.escape(rule.keyword)})(?![\w])", re.IGNORECASE)
    return pattern.sub(
      lambda m: f"<a href='{rule.url}' target='_blank' rel='noopener nofollow sponsored'>{m.group(1)}</a>",
      segment,
    )

  def inject_segment(segment: str) -> str:
    parts = anchor_or_markdown_link.split(segment)
    processed_parts: list[str] = []
    for part in parts:
      if not part:
        continue
      if part.lower().startswith("<a ") or part.startswith("["):
        processed_parts.append(part)
        continue
      updated_part = part
      for rule in rules:
        updated_part = replace_keyword(updated_part, rule)
      processed_parts.append(updated_part)
    return "".join(processed_parts)

  updated_lines: list[str] = []
  for line in body.splitlines(keepends=True):
    if re.match(r"^\s*#{1,6}\s", line):
      updated_lines.append(line)
      continue
    updated_lines.append(inject_segment(line))

  updated_body = "".join(updated_lines)
  return front_matter + updated_body if has_front_matter else updated_body


def iter_article_files(content_dir: Path) -> Iterable[Path]:
  allowed = {".md", ".txt", ".html", ".json"}
  for path in content_dir.iterdir():
    if path.is_file() and path.name != "index.json" and path.suffix.lower() in allowed:
      yield path


def inject_links_into_all_articles(content_dir: Path, rules: list[AffiliateRule]) -> None:
  for article in iter_article_files(content_dir):
    original = article.read_text(encoding="utf-8")
    updated = inject_links_in_text(original, rules)
    if updated != original:
      article.write_text(updated, encoding="utf-8")


def extract_title_and_excerpt(markdown: str, fallback_slug: str) -> tuple[str, str, dict[str, str]]:
  metadata, body = parse_front_matter(markdown)
  lines = [line.strip() for line in body.splitlines() if line.strip()]
  title = metadata.get("title", "") or fallback_slug.replace("-", " ").title()

  for line in lines:
    if line.startswith("# "):
      title = line[2:].strip()
      break

  title = re.sub(r"<[^>]+>", "", title).strip()
  meta_description = metadata.get("meta_description", "").strip()
  meta_title = metadata.get("meta_title", "").strip()
  plain = re.sub(r"<[^>]+>", "", body)
  plain = re.sub(r"[#>*_`]", "", plain)
  excerpt = meta_description or re.sub(r"\s+", " ", plain).strip()[:170]

  return title, excerpt, {
    "meta_title": meta_title,
    "meta_description": meta_description,
  }


def rebuild_post_index(content_dir: Path, index_path: Path) -> None:
  posts = []
  for article in iter_article_files(content_dir):
    slug = article.stem
    raw = article.read_text(encoding="utf-8")
    title, excerpt, meta = extract_title_and_excerpt(raw, slug)
    published = datetime.fromtimestamp(article.stat().st_mtime, tz=timezone.utc).isoformat()
    posts.append(
      {
        "slug": slug,
        "title": title,
        "meta_title": meta["meta_title"] or title,
        "meta_description": meta["meta_description"] or excerpt,
        "excerpt": excerpt,
        "published_at": published,
        "file": article.name,
      }
    )

  posts.sort(key=lambda item: item["published_at"], reverse=True)
  payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "posts": posts}
  index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_sitemap(content_dir: Path, sitemap_path: Path) -> None:
  urls = [
    {
      "loc": f"{SITE_URL}/",
      "lastmod": datetime.now(timezone.utc).date().isoformat(),
      "changefreq": "daily",
      "priority": "1.0",
    }
  ]

  for article in iter_article_files(content_dir):
    if article.name == "index.json":
      continue
    urls.append(
      {
        "loc": f"{SITE_URL}/post.html?slug={article.stem}",
        "lastmod": datetime.fromtimestamp(article.stat().st_mtime, tz=timezone.utc).date().isoformat(),
        "changefreq": "weekly",
        "priority": "0.8",
      }
    )

  lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
  for url in urls:
    lines.extend(
      [
        "  <url>",
        f"    <loc>{url['loc']}</loc>",
        f"    <lastmod>{url['lastmod']}</lastmod>",
        f"    <changefreq>{url['changefreq']}</changefreq>",
        f"    <priority>{url['priority']}</priority>",
        "  </url>",
      ]
    )
  lines.append("</urlset>")
  sitemap_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_robots(robots_path: Path) -> None:
  robots_path.write_text(
    "\n".join(
      [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        "",
      ]
    ),
    encoding="utf-8",
  )


def main() -> None:
  CONTENT_DIR.mkdir(parents=True, exist_ok=True)
  topics, remaining = read_top_topics(TOPICS_FILE, amount=2)

  if topics:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
      raise EnvironmentError("OPENAI_API_KEY is required to generate new content.")
    client = OpenAI(api_key=api_key)

    for topic in topics:
      article = generate_article(client, topic)
      save_generated_post(topic, article)

    write_remaining_topics(TOPICS_FILE, remaining)

  rules = load_affiliate_rules(AFFILIATES_FILE)
  inject_links_into_all_articles(CONTENT_DIR, rules)
  rebuild_post_index(CONTENT_DIR, INDEX_FILE)
  build_sitemap(CONTENT_DIR, SITEMAP_FILE)
  build_robots(ROBOTS_FILE)

  print("Done: content generated (if topics available), affiliate links injected, and SEO files rebuilt.")


if __name__ == "__main__":
  main()
