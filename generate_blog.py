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

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
TOPICS_FILE = ROOT / "topics.txt"
AFFILIATES_FILE = ROOT / "affiliates.json"
INDEX_FILE = CONTENT_DIR / "index.json"


@dataclass(frozen=True)
class AffiliateRule:
  keyword: str
  url: str


def slugify(text: str) -> str:
  slug = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
  slug = re.sub(r"[\s_]+", "-", slug)
  slug = re.sub(r"-{2,}", "-", slug)
  return slug or f"post-{int(datetime.now(timezone.utc).timestamp())}"


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


def generate_article(client: OpenAI, topic: str) -> str:
  prompt = f"""
Write a high-quality Dutch (Nederlands) SEO blog article about: "{topic}".

Requirements:
- Around 1200 words.
- Start with a single H1 markdown heading.
- Include an engaging intro, practical sections with H2/H3 headings, and a clear conclusion.
- Write for real users first, while staying SEO-friendly.
- Include concrete tips, examples, and actionable takeaways.
- Keep tone professional and readable.
- Return markdown only.
""".strip()

  response = client.chat.completions.create(
    model="gpt-4o",
    temperature=0.7,
    messages=[
      {"role": "system", "content": "You are an expert Dutch SEO blog writer."},
      {"role": "user", "content": prompt},
    ],
  )
  content = response.choices[0].message.content
  if not content:
    raise RuntimeError(f"Empty response for topic: {topic}")
  return content.strip()


def save_generated_post(topic: str, markdown: str) -> Path:
  CONTENT_DIR.mkdir(parents=True, exist_ok=True)
  base_slug = slugify(topic)
  output = CONTENT_DIR / f"{base_slug}.md"

  if output.exists():
    output = CONTENT_DIR / f"{base_slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.md"

  output.write_text(markdown.strip() + "\n", encoding="utf-8")
  return output


def load_affiliate_rules(path: Path) -> list[AffiliateRule]:
  data = json.loads(path.read_text(encoding="utf-8"))
  raw_keywords = data.get("keywords", {})
  if not isinstance(raw_keywords, dict):
    raise ValueError("affiliates.json must contain a `keywords` object")

  rules = [AffiliateRule(keyword=k, url=v) for k, v in raw_keywords.items() if k and v]
  rules.sort(key=lambda r: len(r.keyword), reverse=True)
  return rules


def inject_links_in_text(text: str, rules: list[AffiliateRule]) -> str:
  anchor_or_markdown_link = re.compile(r"(<a\b[^>]*>.*?</a>|\[[^\]]+\]\([^)]+\))", re.IGNORECASE | re.DOTALL)

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
  for line in text.splitlines(keepends=True):
    if re.match(r"^\s*#{1,6}\s", line):
      updated_lines.append(line)
      continue
    updated_lines.append(inject_segment(line))

  return "".join(updated_lines)


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


def extract_title_and_excerpt(markdown: str, fallback_slug: str) -> tuple[str, str]:
  lines = [line.strip() for line in markdown.splitlines() if line.strip()]
  title = fallback_slug.replace("-", " ").title()

  for line in lines:
    if line.startswith("# "):
      title = line[2:].strip()
      break
  title = re.sub(r"<[^>]+>", "", title).strip()

  plain = re.sub(r"<[^>]+>", "", markdown)
  plain = re.sub(r"[#>*_`]", "", plain)
  excerpt = re.sub(r"\s+", " ", plain).strip()[:170]
  return title, excerpt


def rebuild_post_index(content_dir: Path, index_path: Path) -> None:
  posts = []
  for article in iter_article_files(content_dir):
    slug = article.stem
    raw = article.read_text(encoding="utf-8")
    title, excerpt = extract_title_and_excerpt(raw, slug)
    published = datetime.fromtimestamp(article.stat().st_mtime, tz=timezone.utc).isoformat()
    posts.append(
      {
        "slug": slug,
        "title": title,
        "excerpt": excerpt,
        "published_at": published,
        "file": article.name,
      }
    )

  posts.sort(key=lambda item: item["published_at"], reverse=True)
  payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "posts": posts}
  index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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

  print("Done: content generated (if topics available), affiliate links injected, and index.json rebuilt.")


if __name__ == "__main__":
  main()
