async function loadPosts() {
  const SITE_URL = "https://www.cryptobelastinggids.nl";
  const postsContainer = document.getElementById("posts");
  const emptyState = document.getElementById("empty");
  const searchInput = document.getElementById("post-search");
  const footerYear = document.getElementById("footer-year");
  const stripHtmlTags = (value) => String(value || "").replace(/<[^>]*>/g, "").trim();
  const estimateReadingTime = (text) => {
    const words = stripHtmlTags(text).split(/\s+/).filter(Boolean).length;
    const minutes = Math.max(5, Math.ceil(words / 220));
    return `${minutes} min leestijd`;
  };

  if (footerYear) {
    footerYear.textContent = String(new Date().getFullYear());
  }

  try {
    const response = await fetch("./content/index.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Failed to load post index");
    }

    const payload = await response.json();
    const posts = Array.isArray(payload.posts) ? payload.posts : [];

    if (!posts.length) {
      emptyState.classList.remove("hidden");
      return;
    }

    const renderPosts = (query = "") => {
      const normalizedQuery = query.trim().toLowerCase();
      const filteredPosts = !normalizedQuery
        ? posts
        : posts.filter((post) => {
            const title = stripHtmlTags(post.title).toLowerCase();
            const excerpt = stripHtmlTags(post.excerpt).toLowerCase();
            return title.includes(normalizedQuery) || excerpt.includes(normalizedQuery);
          });

      if (!filteredPosts.length) {
        postsContainer.innerHTML = "";
        emptyState.textContent = "Geen artikelen gevonden voor je zoekopdracht. Probeer een ander trefwoord.";
        emptyState.classList.remove("hidden");
        return;
      }

      emptyState.classList.add("hidden");
      postsContainer.innerHTML = filteredPosts
        .map(
          (post) => `
          <article class="group rounded-2xl border border-slate-100 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md">
            <div class="flex items-center justify-between gap-3">
              <span class="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">Belastinggids</span>
              <span class="text-xs font-medium text-slate-500">${estimateReadingTime(post.excerpt)}</span>
            </div>
            <p class="mt-4 text-xs uppercase tracking-wide text-slate-400">${new Date(post.published_at).toLocaleDateString("nl-NL", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}</p>
            <h3 class="mt-2 text-xl font-bold tracking-tight text-slate-900">
              <a class="transition group-hover:text-indigo-600" href="${SITE_URL}/post.html?slug=${encodeURIComponent(post.slug)}">${stripHtmlTags(post.title)}</a>
            </h3>
            <p class="mt-3 text-sm leading-relaxed text-slate-600">${stripHtmlTags(post.excerpt)}</p>
            <a class="mt-5 inline-flex items-center text-sm font-semibold text-indigo-600 transition hover:underline" href="${SITE_URL}/post.html?slug=${encodeURIComponent(post.slug)}">
              Lees meer →
            </a>
          </article>
        `
        )
        .join("");
    };

    renderPosts();
    if (searchInput) {
      searchInput.addEventListener("input", (event) => {
        renderPosts(event.target.value);
      });
    }
  } catch (error) {
    emptyState.textContent = "Artikelen konden niet worden geladen. Controleer of /content/index.json bestaat.";
    emptyState.classList.remove("hidden");
  }
}

loadPosts();
