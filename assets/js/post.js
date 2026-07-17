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

function styleRenderedContent(contentEl) {
  contentEl.className = "text-slate-700";

  contentEl.querySelectorAll("h1").forEach((el) => {
    el.className = "mt-8 mb-4 text-3xl font-bold tracking-tight text-slate-900";
  });
  contentEl.querySelectorAll("h2").forEach((el) => {
    el.className = "mt-8 mb-4 text-2xl font-bold tracking-tight text-slate-900";
  });
  contentEl.querySelectorAll("h3").forEach((el) => {
    el.className = "mt-6 mb-3 text-xl font-bold tracking-tight text-slate-900";
  });
  contentEl.querySelectorAll("p").forEach((el) => {
    el.className = "mb-6 leading-relaxed text-slate-700";
  });
  contentEl.querySelectorAll("ul").forEach((el) => {
    el.className = "mb-4 list-disc space-y-2 pl-5 text-slate-700";
  });
  contentEl.querySelectorAll("ol").forEach((el) => {
    el.className = "mb-4 list-decimal space-y-2 pl-5 text-slate-700";
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
}

function applySeo(title, description, slug) {
  document.title = `${title} | CryptoTaxAuthority`;
  const metaDescription = document.querySelector('meta[name="description"]');
  const ogTitle = document.querySelector('meta[property="og:title"]');
  const ogDescription = document.querySelector('meta[property="og:description"]');
  const ogUrl = document.querySelector('meta[property="og:url"]');
  const canonical = document.getElementById("canonical-link");
  const url = `${window.location.origin}/post.html?slug=${encodeURIComponent(slug)}`;

  if (metaDescription) metaDescription.setAttribute("content", description);
  if (ogTitle) ogTitle.setAttribute("content", `${title} | CryptoTaxAuthority`);
  if (ogDescription) ogDescription.setAttribute("content", description);
  if (ogUrl) ogUrl.setAttribute("content", url);
  if (canonical) canonical.setAttribute("href", url);
}

function parseMarkdownDocument(markdownText, fallbackSlug) {
  const lines = markdownText.split("\n");
  let title = "";
  const bodyLines = [];

  for (const line of lines) {
    if (!title && line.trim().startsWith("# ")) {
      title = line.replace(/^#\s+/, "").trim();
      continue;
    }
    bodyLines.push(line);
  }

  return {
    title: stripHtmlTags(title || fallbackSlug.replace(/-/g, " ")),
    content: bodyLines.join("\n").trim() || markdownText,
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
      return { title, markdown };
    }

    const rawText = await response.text();
    const parsed = parseMarkdownDocument(rawText, slug);
    return { title: parsed.title, markdown: parsed.content };
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
    const { title, markdown } = await fetchPost(slug);
    marked.setOptions({ gfm: true, breaks: false });
    const sanitizedHtml = DOMPurify.sanitize(marked.parse(markdown));
    titleEl.textContent = stripHtmlTags(title);
    contentEl.innerHTML = sanitizedHtml;
    styleRenderedContent(contentEl);
    metaEl.textContent = `Artikel: ${slug}`;
    if (readingTimeEl) {
      readingTimeEl.textContent = estimateReadingTime(markdown);
    }

    const firstParagraph = markdown.split("\n").find((line) => line.trim().length > 40) || "Crypto belastinggids met praktische automatiseringsinzichten.";
    applySeo(title, firstParagraph.slice(0, 155), slug);
  } catch (error) {
    errorEl.textContent = "Dit artikel kon niet worden geladen.";
    errorEl.classList.remove("hidden");
  }
}

loadPost();
