const acceptedExtensions = new Set(["png", "jpg", "jpeg", "webp", "svg"]);
const state = { logo: [], cover: [], gallery: [], urls: [] };

const form = document.querySelector("#optimizer-form");
const outputFolder = document.querySelector("#output-folder");
const entityName = document.querySelector("#entity-name");
const processButton = document.querySelector("#process-button");
const clearAllButton = document.querySelector("#clear-all");
const statusMessage = document.querySelector("#status-message");
const altFields = document.querySelector("#alt-fields");
const resultsDialog = document.querySelector("#results-dialog");

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / (1024 ** index);
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
}

function validImages(files) {
  return [...files].filter(file => acceptedExtensions.has((file.name.split(".").pop() || "").toLowerCase()));
}

function revokePreviewUrls() {
  state.urls.forEach(url => URL.revokeObjectURL(url));
  state.urls = [];
}

function previewMarkup(file) {
  const extension = (file.name.split(".").pop() || "").toLowerCase();
  const url = URL.createObjectURL(file);
  state.urls.push(url);
  if (extension === "svg") return `<img src="${url}" alt="Preview of ${escapeHtml(file.name)}">`;
  return `<img src="${url}" alt="Preview of ${escapeHtml(file.name)}">`;
}

function renderPreviews() {
  revokePreviewUrls();
  for (const kind of ["logo", "cover", "gallery"]) {
    const card = document.querySelector(`[data-upload-card="${kind}"]`);
    const zone = card.querySelector(".drop-zone");
    const preview = card.querySelector(".preview-area");
    const files = state[kind];
    zone.classList.toggle("has-files", files.length > 0);
    card.querySelector(".clear-card").disabled = files.length === 0;

    if (!files.length) {
      preview.innerHTML = "";
    } else if (kind !== "gallery") {
      preview.innerHTML = `<div class="single-preview" data-preview-kind="${kind}" data-preview-index="0">${previewMarkup(files[0])}<button class="remove-image" type="button" data-remove-kind="${kind}" data-remove-index="0" aria-label="Remove ${kind}">×</button><span class="file-badge">${escapeHtml(files[0].name)} · ${formatBytes(files[0].size)}</span></div>`;
    } else {
      preview.innerHTML = files.map((file, index) => {
        return `<div class="gallery-thumb" data-preview-kind="gallery" data-preview-index="${index}">${previewMarkup(file)}<button class="remove-image" type="button" data-remove-kind="gallery" data-remove-index="${index}" aria-label="Remove ${escapeHtml(file.name)}">×</button></div>`;
      }).join("");
    }
  }
  renderAltFields();
  updateFormState();
}

function language() {
  return document.querySelector('input[name="naming_language"]:checked').value;
}

function altSuggestion(kind, index = 1) {
  const name = entityName.value.trim();
  if (language() === "arabic") {
    if (kind === "logo") return `شعار ${name}`;
    if (kind === "cover") return `غلاف ${name}`;
    return `صورة ${index} من ${name}`;
  }
  if (kind === "logo") return `${name} logo`;
  if (kind === "cover") return `${name} cover`;
  return `${name} gallery photo ${index}`;
}

function renderAltFields() {
  const previous = new Map([...altFields.querySelectorAll("input")].map(input => [input.id, input.value]));
  const fields = [];
  if (state.logo.length) fields.push(["logo-alt", "Logo", altSuggestion("logo")]);
  if (state.cover.length) fields.push(["cover-alt", "Cover", altSuggestion("cover")]);
  state.gallery.forEach((file, index) => fields.push([`gallery-alt-${index + 1}`, `Gallery ${String(index + 1).padStart(2, "0")}`, altSuggestion("gallery", index + 1)]));
  if (!fields.length) {
    altFields.innerHTML = '<p class="option-note">Add images to create editable suggestions.</p>';
    return;
  }
  altFields.innerHTML = fields.map(([id, label, suggestion]) => {
    const value = previous.has(id) ? previous.get(id) : suggestion;
    return `<label for="${id}">${label}<input id="${id}" type="text" value="${escapeHtml(value)}"></label>`;
  }).join("");
}

function updateFormState() {
  const hasImages = state.logo.length || state.cover.length || state.gallery.length;
  const ready = Boolean(outputFolder.value.trim() && entityName.value.trim() && hasImages);
  processButton.disabled = !ready;
  clearAllButton.disabled = !hasImages;
  if (!processButton.classList.contains("loading")) {
    statusMessage.className = "status-message";
    statusMessage.textContent = ready
      ? `${state.logo.length + state.cover.length + state.gallery.length} image(s) ready to optimize.`
      : "Choose a folder, enter a name, and add at least one image.";
  }
}

function setFiles(kind, files, append = false) {
  const accepted = validImages(files);
  if (kind === "gallery" && append) {
    const combined = [...state.gallery, ...accepted];
    const seen = new Set();
    state.gallery = combined.filter(file => {
      const key = `${file.name}:${file.size}:${file.lastModified}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  } else {
    state[kind] = kind === "gallery" ? accepted : accepted.slice(0, 1);
  }
  renderPreviews();
}

for (const kind of ["logo", "cover", "gallery"]) {
  const input = document.querySelector(`#${kind}-input`);
  const zone = document.querySelector(`#${kind}-drop-zone`);
  input.addEventListener("change", () => {
    setFiles(kind, input.files, kind === "gallery");
    input.value = "";
  });
  zone.addEventListener("dragover", event => { event.preventDefault(); zone.classList.add("dragging"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
  zone.addEventListener("drop", event => {
    event.preventDefault();
    zone.classList.remove("dragging");
    setFiles(kind, event.dataTransfer.files, kind === "gallery");
  });
}

document.querySelectorAll("[data-add]").forEach(button => button.addEventListener("click", () => {
  document.querySelector(`#${button.dataset.add}-input`).click();
}));

document.querySelectorAll("[data-clear]").forEach(button => button.addEventListener("click", () => {
  const kind = button.dataset.clear;
  state[kind] = [];
  document.querySelector(`#${kind}-input`).value = "";
  renderPreviews();
}));

document.querySelector(".upload-grid").addEventListener("click", event => {
  const removeButton = event.target.closest("[data-remove-kind]");
  if (removeButton) {
    event.preventDefault();
    event.stopPropagation();
    const kind = removeButton.dataset.removeKind;
    const index = Number(removeButton.dataset.removeIndex);
    state[kind].splice(index, 1);
    renderPreviews();
    return;
  }

  const preview = event.target.closest("[data-preview-kind]");
  if (preview) {
    event.preventDefault();
    const kind = preview.dataset.previewKind;
    const index = Number(preview.dataset.previewIndex);
    showImagePreview(state[kind][index], preview.querySelector("img").src);
  }
});

clearAllButton.addEventListener("click", () => {
  for (const kind of ["logo", "cover", "gallery"]) {
    state[kind] = [];
    document.querySelector(`#${kind}-input`).value = "";
  }
  renderPreviews();
});

outputFolder.addEventListener("input", updateFormState);
entityName.addEventListener("input", () => { renderAltFields(); updateFormState(); });
document.querySelectorAll('input[name="naming_language"]').forEach(input => input.addEventListener("change", renderAltFields));

document.querySelector("#browse-button").addEventListener("click", async () => {
  const button = document.querySelector("#browse-button");
  button.disabled = true;
  button.textContent = "Opening…";
  try {
    const response = await fetch("/api/select-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_folder: outputFolder.value.trim() })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Folder picker could not open.");
    if (data.path) outputFolder.value = data.path;
    updateFormState();
  } catch (error) {
    statusMessage.className = "status-message error";
    statusMessage.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Browse";
  }
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (processButton.disabled) return;

  const data = new FormData();
  data.append("output_folder", outputFolder.value.trim());
  data.append("entity_name", entityName.value.trim());
  data.append("naming_language", language());
  data.append("include_brand_prefix", document.querySelector('input[name="include_brand_prefix"]:checked').value);
  data.append("overwrite", document.querySelector("#overwrite").checked ? "true" : "false");
  if (state.logo.length) {
    data.append("logo", state.logo[0]);
    data.append("logo_alt", document.querySelector("#logo-alt")?.value ?? "");
  }
  if (state.cover.length) {
    data.append("cover", state.cover[0]);
    data.append("cover_alt", document.querySelector("#cover-alt")?.value ?? "");
  }
  state.gallery.forEach(file => data.append("gallery", file));
  data.append("gallery_alt", JSON.stringify(state.gallery.map((_, index) => document.querySelector(`#gallery-alt-${index + 1}`)?.value ?? "")));

  processButton.disabled = true;
  processButton.classList.add("loading");
  processButton.querySelector("span").textContent = "Optimizing";
  statusMessage.className = "status-message";
  statusMessage.textContent = "Optimizing and saving your images…";
  try {
    const response = await fetch("/api/process", { method: "POST", body: data });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The images could not be processed.");
    showResults(result);
    statusMessage.className = "status-message success";
    statusMessage.textContent = result.message;
  } catch (error) {
    statusMessage.className = "status-message error";
    statusMessage.textContent = error.message;
  } finally {
    processButton.classList.remove("loading");
    processButton.querySelector("span").textContent = "Optimize and save images";
    updateFormState();
  }
});

function showResults(result) {
  document.querySelector("#results-path").textContent = `Saved in ${result.output_folder}`;
  document.querySelector("#result-metrics").innerHTML = `
    <div class="metric"><span>Original size</span><strong>${formatBytes(result.original_bytes)}</strong></div>
    <div class="metric"><span>Optimized size</span><strong>${formatBytes(result.output_bytes)}</strong></div>
    <div class="metric"><span>Total reduction</span><strong>${result.reduction_percent.toFixed(1)}%</strong></div>`;
  document.querySelector("#results-body").innerHTML = result.images.map(image => `
    <tr><td title="${escapeHtml(image.filename)}">${escapeHtml(image.filename)}</td>
    <td>${image.original_size.join("×")} → ${image.output_size.join("×")}</td>
    <td>${formatBytes(image.original_bytes)}</td><td>${formatBytes(image.output_bytes)}</td>
    <td>${image.reduction_percent.toFixed(1)}%</td></tr>`).join("");
  document.querySelector("#download-button").href = result.download_url;
  resultsDialog.showModal();
}

function showImagePreview(file, source) {
  if (!file) return;
  document.querySelector("#preview-title").textContent = `${file.name} · ${formatBytes(file.size)}`;
  document.querySelector("#large-preview-image").src = source;
  document.querySelector("#preview-dialog").showModal();
}

document.querySelector("#close-dialog").addEventListener("click", () => resultsDialog.close());
document.querySelector("#done-button").addEventListener("click", () => resultsDialog.close());
resultsDialog.addEventListener("click", event => {
  const bounds = resultsDialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) resultsDialog.close();
});

const previewDialog = document.querySelector("#preview-dialog");
document.querySelector("#close-preview").addEventListener("click", () => previewDialog.close());
previewDialog.addEventListener("click", event => {
  const bounds = previewDialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) previewDialog.close();
});

const themeToggle = document.querySelector("#theme-toggle");
const savedTheme = localStorage.getItem("ramworld-theme");
const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
themeToggle.checked = savedTheme ? savedTheme === "dark" : prefersDark;
document.documentElement.dataset.theme = themeToggle.checked ? "dark" : "light";
themeToggle.addEventListener("change", () => {
  const selected = themeToggle.checked ? "dark" : "light";
  document.documentElement.dataset.theme = selected;
  localStorage.setItem("ramworld-theme", selected);
});

updateFormState();
