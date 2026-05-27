const jobsBody = document.getElementById("jobs-body");
const meta = document.getElementById("meta");
const errorBox = document.getElementById("error");
const refreshBtn = document.getElementById("refresh-btn");
const applyAllBtn = document.getElementById("apply-all-btn");
const batchState = document.getElementById("batch-state");
const statusSelect = document.getElementById("status-select");
const relevantOnly = document.getElementById("relevant-only");
const freshOnly = document.getElementById("fresh-only");
const pageSizeSelect = document.getElementById("page-size-select");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const pageInfo = document.getElementById("page-info");
const sortHeaders = document.querySelectorAll("th[data-sort-key]");

let currentItems = [];
let sortState = { key: "posted_age", direction: "asc" };
let pageSize = Number(pageSizeSelect.value);
let currentPage = 1;
const applyStateByJob = new Map();

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderRows(items) {
  if (!items.length) {
    jobsBody.innerHTML = `
        <tr>
          <td colspan="8">No jobs found for current filters.</td>
        </tr>
    `;
    return;
  }

  jobsBody.innerHTML = items
    .map((item) => {
      const url = escapeHtml(item.url);
      return `
        <tr>
          <td>${escapeHtml(item.title || "-")}</td>
          <td>${escapeHtml(item.company || "-")}</td>
          <td>${escapeHtml(item.location || "-")}</td>
          <td>${escapeHtml(item.posted_age || "-")}</td>
          <td>${escapeHtml(item.status || "-")}</td>
          <td>${escapeHtml(item.source || "-")}</td>
          <td><a href="${url}" target="_blank" rel="noopener noreferrer">Open</a></td>
          <td>
            <button
              type="button"
              class="apply-btn"
              data-job-id="${item.id}"
              ${item.source !== "jobstreet" ? "disabled" : ""}
            >
              Auto Fill
            </button>
            <div class="apply-state">${escapeHtml(applyStateByJob.get(item.id) || "")}</div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function paginateItems(items) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  if (currentPage > totalPages) currentPage = totalPages;
  if (currentPage < 1) currentPage = 1;

  const start = (currentPage - 1) * pageSize;
  const end = start + pageSize;
  return {
    pageItems: items.slice(start, end),
    totalPages,
  };
}

function postedAgeToHours(value) {
  if (!value) return Number.POSITIVE_INFINITY;
  const text = String(value).toLowerCase().trim();
  let match = text.match(/^(\d+)\s*h ago$/);
  if (match) return Number(match[1]);
  match = text.match(/^(\d+)\s*hours? ago$/);
  if (match) return Number(match[1]);
  if (text === "1d ago" || text === "1 day ago" || text === "1 day") return 24;
  return Number.POSITIVE_INFINITY;
}

function sortItems(items) {
  const { key, direction } = sortState;
  const sorted = [...items].sort((a, b) => {
    if (key === "posted_age") {
      const left = postedAgeToHours(a.posted_age);
      const right = postedAgeToHours(b.posted_age);
      return left - right;
    }
    const left = String(a[key] ?? "").toLowerCase();
    const right = String(b[key] ?? "").toLowerCase();
    return left.localeCompare(right);
  });

  if (direction === "desc") sorted.reverse();
  return sorted;
}

function updateSortHeaderState() {
  sortHeaders.forEach((header) => {
    header.classList.remove("sort-asc", "sort-desc");
    const key = header.getAttribute("data-sort-key");
    if (key === sortState.key) {
      header.classList.add(sortState.direction === "asc" ? "sort-asc" : "sort-desc");
    }
  });
}

function renderCurrentItems() {
  const sorted = sortItems(currentItems);
  const { pageItems, totalPages } = paginateItems(sorted);
  renderRows(pageItems);
  pageInfo.textContent = `Page ${currentPage} / ${totalPages}`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;
  updateSortHeaderState();
}

async function loadJobs() {
  const params = new URLSearchParams();
  params.set("limit", "500");

  if (statusSelect.value) params.set("status", statusSelect.value);
  params.set("relevant_only", String(relevantOnly.checked));
  params.set("fresh_only", String(freshOnly.checked));

  errorBox.hidden = true;
  meta.textContent = "Loading jobs...";

  try {
    const response = await fetch(`/jobs?${params.toString()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.items) ? data.items : [];

    currentItems = items;
    currentPage = 1;
    renderCurrentItems();
    meta.textContent = `${items.length} jobs loaded`;
  } catch (err) {
    currentItems = [];
    currentPage = 1;
    jobsBody.innerHTML = "";
    pageInfo.textContent = "Page 1 / 1";
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    meta.textContent = "Failed to load jobs";
    errorBox.hidden = false;
    errorBox.textContent = `Error: ${err.message}`;
  }
}

async function applyJob(jobId, button) {
  button.disabled = true;
  const previousLabel = button.textContent;
  button.textContent = "Filling...";
  applyStateByJob.set(jobId, "Processing...");
  renderCurrentItems();

  try {
    const response = await fetch(`/jobs/${jobId}/apply`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    const statusText = data.status ? `${data.status}: ${data.message}` : data.message;
    applyStateByJob.set(jobId, statusText);
  } catch (err) {
    applyStateByJob.set(jobId, `failed: ${err.message}`);
  } finally {
    button.textContent = previousLabel;
    button.disabled = false;
    renderCurrentItems();
  }
}

async function applyAllJobs() {
  applyAllBtn.disabled = true;
  refreshBtn.disabled = true;
  batchState.hidden = false;
  batchState.textContent = "Starting batch auto-fill...";
  errorBox.hidden = true;

  const params = new URLSearchParams();
  params.set("limit", "500");
  params.set("status", statusSelect.value || "new");
  params.set("include_saved", String(statusSelect.value === ""));
  params.set("relevant_only", String(relevantOnly.checked));
  params.set("fresh_only", String(freshOnly.checked));
  params.set("auto_submit", "false");

  try {
    const response = await fetch(`/jobs/apply-batch?${params.toString()}`, {
      method: "POST",
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    const counts = (data.results || []).reduce((acc, item) => {
      acc[item.status] = (acc[item.status] || 0) + 1;
      return acc;
    }, {});
    const summary = Object.entries(counts)
      .map(([status, count]) => `${status}: ${count}`)
      .join(", ");
    batchState.textContent =
      `Batch complete. Processed ${data.processed}/${data.requested}` +
      (summary ? ` (${summary})` : ".");
    await loadJobs();
  } catch (err) {
    batchState.textContent = "Batch failed.";
    errorBox.hidden = false;
    errorBox.textContent = `Error: ${err.message}`;
  } finally {
    applyAllBtn.disabled = false;
    refreshBtn.disabled = false;
  }
}

refreshBtn.addEventListener("click", loadJobs);
applyAllBtn.addEventListener("click", applyAllJobs);
statusSelect.addEventListener("change", loadJobs);
relevantOnly.addEventListener("change", loadJobs);
freshOnly.addEventListener("change", loadJobs);
pageSizeSelect.addEventListener("change", () => {
  pageSize = Number(pageSizeSelect.value);
  currentPage = 1;
  renderCurrentItems();
});
prevBtn.addEventListener("click", () => {
  currentPage -= 1;
  renderCurrentItems();
});
nextBtn.addEventListener("click", () => {
  currentPage += 1;
  renderCurrentItems();
});
sortHeaders.forEach((header) => {
  header.addEventListener("click", () => {
    const key = header.getAttribute("data-sort-key");
    if (!key) return;
    if (sortState.key === key) {
      sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
    } else {
      sortState = { key, direction: "asc" };
    }
    renderCurrentItems();
  });
});

jobsBody.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.classList.contains("apply-btn")) return;
  const rawId = target.getAttribute("data-job-id");
  const jobId = Number(rawId);
  if (!Number.isFinite(jobId)) return;
  applyJob(jobId, target);
});

loadJobs();
