# Automated SEO Blog (Static, Database-Free)

Lightweight blog stack for GitHub Pages or Vercel:
- **Frontend:** HTML + Tailwind CSS + Vanilla JavaScript
- **Content:** Flat files in `/content`
- **Automation:** `generate_blog.py` using OpenAI + affiliate link injection

## File architecture

```text
.
├── affiliates.json
├── assets
│   ├── css
│   │   └── styles.css
│   └── js
│       ├── index.js
│       └── post.js
├── content
│   ├── index.json
│   └── welcome.md
├── generate_blog.py
├── index.html
├── post.html
├── requirements.txt
└── topics.txt
```

## How it works

1. Add blog topics (one per line) to `topics.txt`.
2. Run `generate_blog.py`.
3. Script generates up to 3 new posts from the top lines of `topics.txt`.
4. Script injects affiliate links into **all** existing articles in `/content`.
5. Script rebuilds `/content/index.json` used by homepage post listing.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key_here"
python generate_blog.py
```

Then serve statically, for example:

```bash
python3 -m http.server 8080
```

Open:
- `http://localhost:8080/index.html`
- `http://localhost:8080/post.html?slug=welcome`

## Deploy

- **GitHub Pages:** Push this repository and enable Pages for branch root.
- **Vercel:** Import repository as a static site (no build command required).
