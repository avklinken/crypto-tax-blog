#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from openai import OpenAI

SITE_URL = "https://www.cryptobelastinggids.nl"
BLOG_NAME = "CryptoBelastingGids"
CATEGORY_NAME = "Crypto Belasting"
ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
POSTS_DIR = ROOT / "posts"
TOPICS_FILE = ROOT / "topics.txt"
AFFILIATES_FILE = ROOT / "affiliates.json"
INDEX_FILE = CONTENT_DIR / "index.json"
SITEMAP_FILE = ROOT / "sitemap.xml"
ROBOTS_FILE = ROOT / "robots.txt"

PROHIBITED_PHRASES = [
  "In de dynamische wereld van",
  "Cruciaal",
  "Kortom",
  "Het is belangrijk om te onthouden",
  "In deze blogpost",
  "Navigeren door",
]


@dataclass(frozen=True)
class AffiliateRule:
  keyword: str
  url: str


@dataclass(frozen=True)
class AuthorProfile:
  name: str
  role: str
  bio: str


AUTHOR_PROFILES = [
  AuthorProfile(
    name="Eva van Riet",
    role="Crypto Belastingconsultant",
    bio=(
      "Eva begeleidt Nederlandse beleggers bij Box 3-aangiftes en portefeuille-structurering. "
      "Ze vertaalt fiscale regels naar praktische stappen voor particuliere crypto-investeerders."
    ),
  ),
  AuthorProfile(
    name="Milan de Groot",
    role="On-chain Data Analist",
    bio=(
      "Milan analyseert walletstromen, exchange-data en transactielogs voor fiscale reconstructies. "
      "Zijn focus ligt op aantoonbare datakwaliteit en reproduceerbare rapportages."
    ),
  ),
  AuthorProfile(
    name="Sanne Verbeek",
    role="Financieel Jurist",
    bio=(
      "Sanne specialiseert zich in Europese crypto-regelgeving en Nederlandse fiscale compliance. "
      "Ze helpt lezers juridische risico’s te herkennen voordat ze in de praktijk escaleren."
    ),
  ),
  AuthorProfile(
    name="Tobias Kleijn",
    role="Digital Asset Accountant",
    bio=(
      "Tobias ondersteunt klanten met jaarafsluiting, vermogensoverzichten en audit-ready cryptodossiers. "
      "Hij combineert accountancy-precisie met automatisering voor complexe portfolios."
    ),
  ),
  AuthorProfile(
    name="Noor Hendriks",
    role="DeFi Risico-adviseur",
    bio=(
      "Noor onderzoekt de fiscale impact van staking, lending en DeFi-opbrengsten. "
      "Ze vertaalt technische protocollen naar begrijpelijke keuzes voor Nederlandse belastingplichtigen."
    ),
  ),
]

FALLBACK_IMAGE_POOL = [
  "https://picsum.photos/id/180/1600/900",
  "https://picsum.photos/id/0/1600/900",
  "https://picsum.photos/id/1/1600/900",
  "https://picsum.photos/id/48/1600/900",
  "https://picsum.photos/id/119/1600/900",
]

REQUIRED_JSON_SCHEMA = {
  "title": "Hier de echte titel (bijv. Vrijstelling Box 3 crypto)",
  "h1": "Hier de echte titel",
  "post_title": "Hier de echte titel",
  "name": "Hier de echte titel",
  "category": "Crypto Belasting",
  "blog_name": "CryptoBelastingGids",
  "content": "De volledige artikel-inhoud in HTML",
}


def select_fallback_image(seed: str) -> str:
  value = sum(ord(char) for char in (seed or ""))
  return FALLBACK_IMAGE_POOL[value % len(FALLBACK_IMAGE_POOL)]


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


def clean_json_response(raw: str) -> str:
  cleaned = raw.strip()
  cleaned = re.sub(r"^\s*```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
  cleaned = re.sub(r"\s*```\s*$", "", cleaned)
  return cleaned.strip()


def format_keyword_list(keywords: list[str]) -> str:
  return ", ".join(f'"{keyword}"' for keyword in keywords if keyword)


def detect_language(topic: str) -> str:
  configured = os.getenv("BLOG_LANGUAGE", "").strip().lower()
  if configured in {"nl", "en"}:
    return configured

  dutch_markers = {"belasting", "belastingen", "nederland", "box", "fiscus", "belastingsdienst", "aangifte"}
  token_set = set(re.findall(r"[a-zA-Z]+", topic.lower()))
  if token_set.intersection(dutch_markers):
    return "nl"
  return "en"


def get_language_context(language: str) -> dict[str, str]:
  if language == "en":
    return {
      "language_name": "English",
      "datapoints": (
        "Use these mandatory 2026 datapoints accurately in context: "
        "Dutch Box 3 tax rate is 36% in 2026, deemed return on crypto is 6.00%, "
        "tax-free allowance is €59,357 (or €118,714 for fiscal partners), "
        "and EU DAC8 reporting rules start on 1 January 2026."
      ),
      "disclaimer": (
        "*Disclaimer: The information on this website is for informational purposes only and does not constitute "
        "financial or tax advice. Always verify legislation with the Dutch Tax Administration or a certified advisor.*"
      ),
      "related_heading": "Related articles:",
      "author_heading": "About the author",
    }

  return {
    "language_name": "Nederlands",
    "datapoints": (
      "Verwerk deze verplichte 2026-datapunten exact en contextueel: "
      "Box 3 belastingtarief is 36% in 2026, fictief forfaitair rendement op crypto is 6,00%, "
      "heffingsvrij vermogen is €59.357 (of €118.714 voor fiscale partners), "
      "en de Europese DAC8-rapportageregels gaan in per 1 januari 2026."
    ),
    "disclaimer": (
      "*Disclaimer: De informatie op deze website is louter informatief en vormt geen financieel of fiscaal advies. "
      "Verifieer wetgeving altijd bij de Belastingdienst of een erkend adviseur.*"
    ),
    "related_heading": "Gerelateerde artikelen:",
    "author_heading": "Over de auteur",
  }


def select_author(topic: str) -> AuthorProfile:
  seed_value = datetime.now(timezone.utc).toordinal() + sum(ord(char) for char in topic)
  return AUTHOR_PROFILES[seed_value % len(AUTHOR_PROFILES)]


def tokenize_for_relevance(text: str) -> set[str]:
  tokens = set(re.findall(r"[a-zA-Z0-9]+", text.lower()))
  stop_words = {
    "de",
    "het",
    "een",
    "en",
    "voor",
    "met",
    "van",
    "in",
    "op",
    "bij",
    "how",
    "what",
    "the",
    "and",
    "for",
    "with",
  }
  return {token for token in tokens if len(token) > 2 and token not in stop_words}


def load_existing_posts(index_path: Path, content_dir: Path) -> list[dict[str, str]]:
  posts: list[dict[str, str]] = []

  if index_path.exists():
    try:
      data = json.loads(index_path.read_text(encoding="utf-8"))
      if isinstance(data.get("posts"), list):
        for post in data["posts"]:
          if not isinstance(post, dict):
            continue
          slug = str(post.get("slug", "")).strip()
          title = str(post.get("title", "")).strip()
          published_at = str(post.get("published_at", "")).strip()
          if slug and title:
            posts.append({"slug": slug, "title": title, "published_at": published_at})
    except json.JSONDecodeError:
      pass

  if posts:
    return posts

  for path in content_dir.iterdir():
    if not path.is_file() or path.name == "index.json" or path.suffix.lower() not in {".md", ".txt", ".html", ".json"}:
      continue
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    title = str(meta.get("title", "")).strip()
    if not title:
      for line in body.splitlines():
        if line.strip().startswith("# "):
          title = line.strip()[2:].strip()
          break
    if not title:
      title = path.stem.replace("-", " ").title()
    posts.append(
      {
        "slug": path.stem,
        "title": title,
        "published_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
      }
    )
  return posts


def select_related_posts(topic: str, title: str, existing_posts: list[dict[str, str]], max_links: int = 2) -> list[dict[str, str]]:
  if not existing_posts:
    return []

  article_tokens = tokenize_for_relevance(f"{topic} {title}")
  scored: list[tuple[int, str, dict[str, str]]] = []
  for post in existing_posts:
    post_slug = str(post.get("slug", "")).strip()
    post_title = str(post.get("title", "")).strip()
    if not post_slug or not post_title:
      continue

    score = len(article_tokens.intersection(tokenize_for_relevance(f"{post_title} {post_slug}")))
    published = str(post.get("published_at", "")).strip()
    scored.append((score, published, post))

  scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
  best = [item[2] for item in scored if item[0] > 0][:max_links]
  if len(best) < max_links:
    already = {post["slug"] for post in best}
    fallback = [item[2] for item in scored if item[2]["slug"] not in already][: max_links - len(best)]
    best.extend(fallback)
  return best[:max_links]


def append_related_and_signature(
  content_markdown: str,
  related_posts: list[dict[str, str]],
  disclaimer: str,
  author: AuthorProfile,
  related_heading: str,
  author_heading: str,
) -> str:
  body = content_markdown.strip()
  parts = [body] if body else []

  if related_posts:
    links = [f"- [{post['title']}]({SITE_URL}/post.html?slug={post['slug']})" for post in related_posts]
    parts.append(f"## {related_heading}\n\n" + "\n".join(links))

  parts.append(disclaimer)
  parts.append(
    f"## {author_heading}\n\n"
    f"**{author.name} — {author.role}**\n\n"
    f"{author.bio}"
  )

  return "\n\n".join(parts).strip()


def enrich_existing_articles(content_dir: Path, existing_posts: list[dict[str, str]]) -> None:
  for article_path in iter_article_files(content_dir):
    if article_path.suffix.lower() not in {".md", ".txt"}:
      continue

    raw = article_path.read_text(encoding="utf-8")
    metadata, body = parse_front_matter(raw)
    body = body.strip()
    slug = article_path.stem

    title = str(metadata.get("title", "")).strip()
    if not title:
      for line in body.splitlines():
        if line.strip().startswith("# "):
          title = line.strip()[2:].strip()
          break
    if not title:
      title = slug.replace("-", " ").title()

    language_context = get_language_context(detect_language(title))
    author = select_author(slug)
    related_candidates = [post for post in existing_posts if str(post.get("slug", "")).strip() != slug]
    related_posts = select_related_posts(slug, title, related_candidates, max_links=2)

    has_related = re.search(r"^##\s+(Gerelateerde artikelen|Related articles):?\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
    has_disclaimer = re.search(r"\*Disclaimer:", body, flags=re.IGNORECASE)
    has_author = re.search(r"^##\s+(Over de auteur|About the author)\s*$", body, flags=re.MULTILINE | re.IGNORECASE)

    if has_related and has_disclaimer and has_author:
      continue

    additions: list[str] = []
    if not has_related and related_posts:
      links = [f"- [{post['title']}]({SITE_URL}/post.html?slug={post['slug']})" for post in related_posts]
      additions.append(f"## {language_context['related_heading']}\n\n" + "\n".join(links))
    if not has_disclaimer:
      additions.append(language_context["disclaimer"])
    if not has_author:
      additions.append(
        f"## {language_context['author_heading']}\n\n"
        f"**{author.name} — {author.role}**\n\n"
        f"{author.bio}"
      )

    if not additions:
      continue

    enriched_body = (body + "\n\n" + "\n\n".join(additions)).strip() + "\n"
    front_matter_block, _, has_front_matter = split_front_matter_block(raw)
    if has_front_matter:
      article_path.write_text(front_matter_block + "\n" + enriched_body, encoding="utf-8")
    else:
      article_path.write_text(enriched_body, encoding="utf-8")


def generate_article(
  client: OpenAI,
  topic: str,
  affiliate_keywords: list[str],
  language_context: dict[str, str],
) -> dict[str, str] | None:
  keyword_list = format_keyword_list(affiliate_keywords)
  keyword_requirement = (
    f"Crucial SEO Requirement: You MUST naturally and contextually weave the following brand names into the article at least 1 or 2 times each: {keyword_list}."
    if keyword_list
    else "Crucial SEO Requirement: Keep the article brand-compatible and ready for affiliate keyword injection."
  )
  prohibited_text = "; ".join(f'"{phrase}"' for phrase in PROHIBITED_PHRASES)

  prompt = f"""
Create a high-quality SEO article about: "{topic}".

Return only valid JSON with these keys:
- title
- h1
- post_title
- name
- blog_name
- category
- content (HTML)

Required JSON schema shape:
{json.dumps(REQUIRED_JSON_SCHEMA, ensure_ascii=False, indent=2)}

Editorial rules (strict):
- Write in {language_context["language_name"]}.
- Approx. 1200 words.
- Use an active voice. Avoid passive constructions unless unavoidable.
- Vary sentence length: mix short, punchy sentences with longer explanatory ones.
- Avoid predictable AI phrasing and cliche intros/outros.
- Forbidden phrases: {prohibited_text}.
- Do not write these generic transitions: "Kortom", "In deze blogpost", "Navigeren door".
- Use practical examples, concrete tax scenarios, and direct recommendations.
- Use only H2/H3 sections in the body; no H1 in content.
- Write the article body as clean semantic HTML.
- Use descriptive alt text in images.
- {language_context["datapoints"]}
- {keyword_requirement}
- All title-like keys (title, h1, post_title, name) must contain the same human title and MUST NOT be "crypto-tax-blog".
- Set blog_name to "{BLOG_NAME}" and category to "{CATEGORY_NAME}".
- No code fences. No extra explanation. Output JSON only.
""".strip()

  response = client.chat.completions.create(
    model="gpt-4o",
    temperature=0.7,
    response_format={"type": "json_object"},
    messages=[
      {
        "role": "system",
        "content": (
          "You are a senior editorial crypto tax writer following strict EEAT standards. "
          "Always return exactly one valid JSON object with keys: title, h1, post_title, name, category, blog_name, content. "
          "Keep title, h1, post_title, and name exactly identical and never use the placeholder crypto-tax-blog. "
          f'Use blog_name="{BLOG_NAME}" and category="{CATEGORY_NAME}". '
          "Never use markdown code fences around JSON."
        ),
      },
      {"role": "user", "content": prompt},
    ],
  )

  raw = response.choices[0].message.content
  if not raw:
    print(f"[WARN] Empty response for topic: {topic}")
    return None

  cleaned_raw = clean_json_response(raw)

  try:
    payload = json.loads(cleaned_raw)
  except json.JSONDecodeError as exc:
    preview = cleaned_raw[:500].replace("\n", " ")
    print(f"[WARN] Invalid JSON for topic '{topic}': {exc}")
    print(f"[WARN] Raw preview: {preview}")
    return None

  if not isinstance(payload, dict):
    print(f"[WARN] JSON root is not an object for topic: {topic}")
    return None

  expected_keys = {"title", "h1", "post_title", "name", "blog_name", "category", "content"}
  missing_keys = [key for key in expected_keys if key not in payload]
  if missing_keys:
    print(f"[WARN] Missing expected JSON keys for topic '{topic}': {', '.join(missing_keys)}")

  title_candidates = [
    str(payload.get("title", "")).strip(),
    str(payload.get("h1", "")).strip(),
    str(payload.get("post_title", "")).strip(),
    str(payload.get("name", "")).strip(),
  ]
  title = next((value for value in title_candidates if value and value.casefold() != "crypto-tax-blog"), topic)
  content_html = str(payload.get("content") or "").strip()

  if not content_html:
    print(f"[WARN] Missing content for topic: {topic}")
    return None

  plain_body = re.sub(r"<[^>]+>", "", content_html)
  plain_body = re.sub(r"[#>*_`]", "", plain_body)
  fallback_description = trim_to_limit(re.sub(r"\s+", " ", plain_body).strip()[:155], 155)
  meta_title = trim_to_limit(title, 60)
  meta_description = trim_to_limit(fallback_description or title, 155)

  return {
    "title": title,
    "h1": title,
    "post_title": title,
    "name": title,
    "blog_name": BLOG_NAME,
    "category": CATEGORY_NAME,
    "meta_title": meta_title,
    "meta_description": meta_description,
    "content_markdown": content_html,
    "content_html": content_html,
  }


def save_generated_post(topic: str, article: dict[str, str], author: AuthorProfile) -> Path:
  CONTENT_DIR.mkdir(parents=True, exist_ok=True)
  POSTS_DIR.mkdir(parents=True, exist_ok=True)
  base_slug = slugify(topic)
  output = CONTENT_DIR / f"{base_slug}.md"
  static_output = POSTS_DIR / f"{base_slug}.html"

  if output.exists():
    timestamped = f"{base_slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    output = CONTENT_DIR / f"{timestamped}.md"
    static_output = POSTS_DIR / f"{timestamped}.html"

  published_at = datetime.now(timezone.utc).isoformat()
  image_url = select_fallback_image(f"{topic}-{article['title']}")
  body_source = str(article.get("content_html") or article.get("content_markdown") or "")
  body_core = body_source.replace("crypto-tax-blog", article["title"])
  body_core = strip_leading_h1(body_core)
  body_core = re.sub(r"^\s*<h1\b[^>]*>.*?</h1>\s*", "", body_core, flags=re.IGNORECASE | re.DOTALL)
  title_h1 = f"<h1>{html.escape(article['title'])}</h1>"
  image_block = f'<img src="{image_url}" alt="Illustratie bij {html.escape(article["title"])}" loading="eager" decoding="async" />'
  body = f"{title_h1}\n\n{image_block}\n\n{body_core.strip()}".strip()

  front_matter = "\n".join(
    [
      "---",
      f"title: {quote_yaml_value(article['title'])}",
      f"h1: {quote_yaml_value(article['h1'])}",
      f"post_title: {quote_yaml_value(article['post_title'])}",
      f"name: {quote_yaml_value(article['name'])}",
      f"blog_name: {quote_yaml_value(article['blog_name'])}",
      f"category: {quote_yaml_value(article['category'])}",
      f"meta_title: {quote_yaml_value(article['meta_title'])}",
      f"meta_description: {quote_yaml_value(article['meta_description'])}",
      f"image_url: {quote_yaml_value(image_url)}",
      f"slug: {quote_yaml_value(output.stem)}",
      f"topic: {quote_yaml_value(topic)}",
      f"published_at: {quote_yaml_value(published_at)}",
      f"author_name: {quote_yaml_value(author.name)}",
      f"author_role: {quote_yaml_value(author.role)}",
      f"author_bio: {quote_yaml_value(author.bio)}",
      "---",
      "",
    ]
  )

  output.write_text(front_matter + body.strip() + "\n", encoding="utf-8")

  static_html = "\n".join(
    [
      "<!doctype html>",
      '<html lang="nl">',
      "  <head>",
      '    <meta charset="UTF-8" />',
      '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />',
      f"    <title>{html.escape(article['meta_title'])} | {BLOG_NAME}</title>",
      f'    <meta name="description" content="{html.escape(article["meta_description"])}" />',
      f'    <link rel="canonical" href="{SITE_URL}/posts/{output.stem}.html" />',
      f'    <meta property="og:title" content="{html.escape(article["meta_title"])}" />',
      f'    <meta property="og:description" content="{html.escape(article["meta_description"])}" />',
      f'    <meta property="og:url" content="{SITE_URL}/posts/{output.stem}.html" />',
      f'    <meta property="og:image" content="{image_url}" />',
      '    <meta property="og:type" content="article" />',
      f'    <meta property="og:site_name" content="{BLOG_NAME}" />',
      '    <link rel="stylesheet" href="/assets/css/styles.css" />',
      "  </head>",
      "  <body>",
      '    <header><nav><a href="https://www.cryptobelastinggids.nl/">CryptoBelastingGids</a></nav></header>',
      "    <main>",
      "      <article>",
      f"        {title_h1}",
      f'        <img src="{image_url}" alt="Illustratie bij {html.escape(article["title"])}" loading="eager" decoding="async" />',
      f"        {body_core}",
      "      </article>",
      "    </main>",
      "    <footer><p>© CryptoBelastingGids</p></footer>",
      "  </body>",
      "</html>",
      "",
    ]
  )
  static_output.write_text(static_html, encoding="utf-8")
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
      if part.lower().startswith("<a "):
        anchor_match = re.match(r"<a\b[^>]*>(.*?)</a>$", part, flags=re.IGNORECASE | re.DOTALL)
        if not anchor_match:
          processed_parts.append(part)
          continue

        anchor_inner = anchor_match.group(1)
        anchor_text = re.sub(r"<[^>]+>", "", anchor_inner)
        anchor_text = re.sub(r"\s+", " ", anchor_text).strip().casefold()

        matched_rule = next((rule for rule in rules if anchor_text == rule.keyword.casefold()), None)
        if matched_rule:
          processed_parts.append(
            f"<a href='{matched_rule.url}' target='_blank' rel='noopener nofollow sponsored'>{anchor_inner}</a>"
          )
        else:
          processed_parts.append(part)
        continue

      if part.startswith("["):
        markdown_match = re.match(r"^\[([^\]]+)\]\(([^)]+)\)$", part)
        if not markdown_match:
          processed_parts.append(part)
          continue

        link_text = re.sub(r"\s+", " ", markdown_match.group(1)).strip()
        matched_rule = next((rule for rule in rules if link_text.casefold() == rule.keyword.casefold()), None)
        if matched_rule:
          processed_parts.append(f"[{markdown_match.group(1)}]({matched_rule.url})")
        else:
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
  rules = load_affiliate_rules(AFFILIATES_FILE)
  affiliate_keywords = [rule.keyword for rule in rules]
  existing_posts = load_existing_posts(INDEX_FILE, CONTENT_DIR)

  if topics:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
      raise EnvironmentError("OPENAI_API_KEY is required to generate new content.")
    client = OpenAI(api_key=api_key)

    failed_topics: list[str] = []
    for topic in topics:
      language_context = get_language_context(detect_language(topic))
      author = select_author(topic)

      try:
        article = generate_article(client, topic, affiliate_keywords, language_context)
      except Exception as exc:
        print(f"[WARN] Failed to generate topic '{topic}': {exc}")
        failed_topics.append(topic)
        continue

      if not article:
        failed_topics.append(topic)
        continue

      related_posts = select_related_posts(topic, article["title"], existing_posts, max_links=2)
      article["content_markdown"] = append_related_and_signature(
        article["content_markdown"],
        related_posts,
        language_context["disclaimer"],
        author,
        language_context["related_heading"],
        language_context["author_heading"],
      )
      article["content_html"] = article["content_markdown"]
      saved_path = save_generated_post(topic, article, author)
      existing_posts.append(
        {
          "slug": saved_path.stem,
          "title": article["title"],
          "published_at": datetime.now(timezone.utc).isoformat(),
        }
      )

    write_remaining_topics(TOPICS_FILE, failed_topics + remaining)

  enrich_existing_articles(CONTENT_DIR, existing_posts)
  inject_links_into_all_articles(CONTENT_DIR, rules)
  rebuild_post_index(CONTENT_DIR, INDEX_FILE)
  build_sitemap(CONTENT_DIR, SITEMAP_FILE)
  build_robots(ROBOTS_FILE)

  print("Done: content generated (if topics available), affiliate links injected, and SEO files rebuilt.")


if __name__ == "__main__":
  main()
