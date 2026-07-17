function getSlug() {
  const params = new URLSearchParams(window.location.search);
  return (params.get("slug") || "").trim();
}

function stripHtmlTags(value) {
  return String(value || "").replace(/<[^>]*>/g, "").trim();
}

function applySeo(title, description, slug) {
  document.title = `${title} | Crypto Tax Blog`;
  const metaDescription = document.querySelector('meta[name="description"]');
  const ogTitle = document.querySelector('meta[property="og:title"]');
  const ogDescription = document.querySelector('meta[property="og:description"]');
  const ogUrl = document.querySelector('meta[property="og:url"]');
  const canonical = document.getElementById("canonical-link");
  const url = `${window.location.origin}/post.html?slug=${encodeURIComponent(slug)}`;

  if (metaDescription) metaDescription.setAttribute("content", description);
  if (ogTitle) ogTitle.setAttribute("content", `${title} | Crypto Tax Blog`);
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
  const errorEl = document.getElementById("post-error");

  if (!slug) {
    errorEl.textContent = "Missing slug. Open this page with ?slug=your-post-slug.";
    errorEl.classList.remove("hidden");
    return;
  }

  try {
    const { title, markdown } = await fetchPost(slug);
    const sanitizedHtml = DOMPurify.sanitize(marked.parse(markdown));
    titleEl.textContent = stripHtmlTags(title);
    contentEl.innerHTML = sanitizedHtml;
    metaEl.textContent = `Published article: ${slug}`;

    const firstParagraph = markdown.split("\n").find((line) => line.trim().length > 40) || "Crypto tax guide and automation insights.";
    applySeo(title, firstParagraph.slice(0, 155), slug);
  } catch (error) {
    errorEl.classList.remove("hidden");
  }
}

loadPost();
