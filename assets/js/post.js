const SITE_URL = "https://www.cryptobelastinggids.nl";

function getSlug() {
  const params = new URLSearchParams(window.location.search);
  return (params.get("slug") || "").trim();
}

function stripHtmlTags(value) {
  return String(value || "").replace(/<[^>]*>/g, "").trim();
}

function estimateReadingTime(markdown) {
  const plain = stripHtmlTags(String(markdown || "").replace(/[#>*_`[\]()!-]/g, " "));
  const words = plain.split(/\s+/).filter(Boolean).length;
  const minutes = Math.max(1, Math.ceil(words / 220));
  return `${minutes} min leestijd`;
}

function parseFrontMatter(markdown) {
  const lines = markdown.split("\n");
  if (lines[0]?.trim() !== "---") {
    return { meta: {}, body: markdown };
  }

  const meta = {};
  let closingIndex = -1;

  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].trim() === "---") {
      closingIndex = i;
      break;
    }

    const separatorIndex = lines[i].indexOf(":");
    if (separatorIndex === -1) {
      continue;
    }

    const key = lines[i].slice(0, separatorIndex).trim();
    const rawValue = lines[i].slice(separatorIndex + 1).trim();
    if (!key) {
      continue;
    }

    try {
      meta[key] = JSON.parse(rawValue);
    } catch {
      meta[key] = rawValue.replace(/^"|"$/g, "");
    }
  }

  if (closingIndex === -1) {
    return { meta: {}, body: markdown };
  }

  return {
    meta,
    body: lines.slice(closingIndex + 1).join("\n").replace(/^\n+/, ""),
  };
}

function removeLeadingH1(markdown) {
  const lines = markdown.split("\n");
  const body = [];
  let skipped = false;

  for (const line of lines) {
    if (!skipped && line.trim().startsWith("# ")) {
      skipped = true;
      continue;
    }
    body.push(line);
  }

  return body.join("\n").trim();
}

function styleRenderedContent(contentEl, articleTitle) {
  contentEl.className = "text-slate-700";

  contentEl.querySelectorAll("h1").forEach((el) => {
    const h2 = document.createElement("h2");
    h2.innerHTML = el.innerHTML;
    h2.className = "mt-8 mb-4 text-3xl font-bold tracking-tight text-slate-900";
    el.replaceWith(h2);
  });

  contentEl.querySelectorAll("h2").forEach((el) => {
    el.className = "mt-8 mb-4 text-3xl font-bold tracking-tight text-slate-900";
  });
  contentEl.querySelectorAll("h3").forEach((el) => {
    el.className = "mt-6 mb-3 text-2xl font-bold tracking-tight text-slate-900";
  });
  contentEl.querySelectorAll("h4").forEach((el) => {
    el.className = "mt-6 mb-3 text-xl font-bold tracking-tight text-slate-900";
  });
  contentEl.querySelectorAll("p").forEach((el) => {
    el.className = "mb-6 leading-relaxed text-slate-700";
  });
  contentEl.querySelectorAll("ul").forEach((el) => {
    el.className = "mb-6 list-disc space-y-2 pl-5 text-slate-700";
  });
  contentEl.querySelectorAll("ol").forEach((el) => {
    el.className = "mb-6 list-decimal space-y-2 pl-5 text-slate-700";
  });
  contentEl.querySelectorAll("li").forEach((el) => {
    el.classList.add("leading-relaxed");
  });
  contentEl.querySelectorAll("a").forEach((el) => {
    el.className = "font-semibold text-indigo-600 transition hover:underline";
    if (!el.getAttribute("rel")) {
      el.setAttribute("rel", "noopener");
    }
  });
  contentEl.querySelectorAll("blockquote").forEach((el) => {
    el.className = "mb-6 border-l-4 border-slate-300 pl-4 italic text-slate-600";
  });
  contentEl.querySelectorAll("img").forEach((img) => {
    if (!img.getAttribute("alt") || !img.getAttribute("alt").trim()) {
      img.setAttribute("alt", `Illustratie bij ${articleTitle}`);
    }
    img.setAttribute("loading", "lazy");
    img.setAttribute("decoding", "async");
    img.className = "my-8 rounded-2xl border border-slate-200 shadow-sm";
  });
}

function setMetaTag(selector, content) {
  const el = document.querySelector(selector);
  if (el && content) {
    el.setAttribute("content", content);
  }
}

function applySeo(meta, fallbackTitle, fallbackDescription, slug) {
  const title = stripHtmlTags(meta.meta_title || meta.title || fallbackTitle);
  const description = stripHtmlTags(meta.meta_description || fallbackDescription);
  const url = `${SITE_URL}/post.html?slug=${encodeURIComponent(slug)}`;

  document.title = `${title} | CryptoBelastingGids`;
  setMetaTag('meta[name="description"]', description);
  setMetaTag('meta[property="og:title"]', title);
  setMetaTag('meta[property="og:description"]', description);
  setMetaTag('meta[property="og:type"]', "article");
  setMetaTag('meta[property="og:url"]', url);
  setMetaTag('meta[property="og:site_name"]', "CryptoBelastingGids");
  setMetaTag('meta[name="robots"]', "index,follow");

  const canonical = document.getElementById("canonical-link");
  if (canonical) {
    canonical.setAttribute("href", url);
  }
}

function extractMarkdownDocument(markdownText, fallbackSlug) {
  const { meta, body } = parseFrontMatter(markdownText);
  const bodyWithoutLeadingH1 = removeLeadingH1(body);
  const title = stripHtmlTags(meta.title || fallbackSlug.replace(/-/g, " "));
  return {
    meta: {
      title,
      meta_title: stripHtmlTags(meta.meta_title || title),
      meta_description: stripHtmlTags(meta.meta_description || ""),
      published_at: stripHtmlTags(meta.published_at || ""),
      slug: stripHtmlTags(meta.slug || fallbackSlug),
    },
    body: bodyWithoutLeadingH1 || body,
  };
}

async function fetchPost(slug) {
  const candidates = [`./content/${slug}.md`, `./content/${slug}.json`, `./content/${slug}.txt`];

  for (const path of candidates) {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) continue;

    if (path.endsWith(".json")) {
      const data = await response.json();
      const title = stripHtmlTags(data.title || slug.replace(/-/g, " "));
      const markdown = data.content_markdown || data.content || "";
      return {
        meta: {
          title,
          meta_title: stripHtmlTags(data.meta_title || title),
          meta_description: stripHtmlTags(data.meta_description || ""),
          published_at: stripHtmlTags(data.published_at || ""),
          slug,
        },
        body: removeLeadingH1(markdown),
      };
    }

    const rawText = await response.text();
    return extractMarkdownDocument(rawText, slug);
  }

  throw new Error("Post not found");
}

async function loadPost() {
  const slug = getSlug();
  const titleEl = document.getElementById("post-title");
  const contentEl = document.getElementById("post-content");
  const metaEl = document.getElementById("post-meta");
  const readingTimeEl = document.getElementById("reading-time");
  const footerYear = document.getElementById("footer-year");
  const errorEl = document.getElementById("post-error");

  if (footerYear) {
    footerYear.textContent = String(new Date().getFullYear());
  }

  if (!slug) {
    errorEl.textContent = "Ontbrekende slug. Open deze pagina met ?slug=jouw-artikel-slug.";
    errorEl.classList.remove("hidden");
    return;
  }

  try {
    const post = await fetchPost(slug);
    marked.setOptions({ gfm: true, breaks: false });
    const renderedHtml = DOMPurify.sanitize(marked.parse(post.body));

    titleEl.textContent = stripHtmlTags(post.meta.title);
    contentEl.innerHTML = renderedHtml;
    styleRenderedContent(contentEl, post.meta.title);
    metaEl.textContent = post.meta.published_at ? `Gepubliceerd: ${new Date(post.meta.published_at).toLocaleDateString("nl-NL")}` : `Artikel: ${slug}`;
    if (readingTimeEl) {
      readingTimeEl.textContent = estimateReadingTime(post.body);
    }

    const fallbackDescription =
      stripHtmlTags(post.body.split("\n").find((line) => line.trim().length > 40) || "Crypto belastinggids met praktische automatiseringsinzichten.").slice(0, 155) ||
      "Crypto belastinggids met praktische automatiseringsinzichten.";
    applySeo(post.meta, post.meta.title, fallbackDescription, slug);
  } catch (error) {
    errorEl.textContent = "Dit artikel kon niet worden geladen.";
    errorEl.classList.remove("hidden");
  }
}

loadPost();
