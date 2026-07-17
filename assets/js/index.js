async function loadPosts() {
  const postsContainer = document.getElementById("posts");
  const emptyState = document.getElementById("empty");

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

    postsContainer.innerHTML = posts
      .map(
        (post) => `
        <article class="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
          <p class="text-xs uppercase tracking-wide text-slate-400">${new Date(post.published_at).toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
          })}</p>
          <h3 class="mt-2 text-lg font-semibold text-slate-100">
            <a class="hover:text-cyan-300" href="./post.html?slug=${encodeURIComponent(post.slug)}">${post.title}</a>
          </h3>
          <p class="mt-2 text-sm text-slate-300">${post.excerpt}</p>
          <a class="mt-4 inline-block text-sm font-medium text-cyan-300 hover:text-cyan-200" href="./post.html?slug=${encodeURIComponent(post.slug)}">
            Read article →
          </a>
        </article>
      `
      )
      .join("");
  } catch (error) {
    emptyState.textContent = "Could not load posts. Make sure /content/index.json exists.";
    emptyState.classList.remove("hidden");
  }
}

loadPosts();
