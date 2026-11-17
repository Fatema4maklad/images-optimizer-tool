const form = document.querySelector('#optimizer-form');
const input = document.querySelector('#image-input');
const dropZone = document.querySelector('#drop-zone');
const selected = document.querySelector('#selected-images');
const message = document.querySelector('#form-message');
const submit = document.querySelector('#submit-button');
const results = document.querySelector('#results');
const resultImages = document.querySelector('#result-images');
const chosen = [];
const allowed = new Set(['image/jpeg', 'image/png', 'image/webp']);
const t = window.imageSeoI18n.t;
const userMessage = window.imageSeoI18n.userMessage;
let lastResult = null;

function formatBytes(bytes) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function addFiles(files) {
  for (const file of files) {
    if (chosen.length >= 12) { message.textContent = t('Choose up to 12 images.'); break; }
    if (!allowed.has(file.type) && !/\.(jpe?g|png|webp)$/i.test(file.name)) { message.textContent = t('Use JPG, PNG, or WebP images.'); continue; }
    if (!file.size || file.size > 10 * 1024 * 1024) { message.textContent = t('Each image must be between 1 byte and 10 MB.'); continue; }
    chosen.push(file);
  }
  input.value = '';
  renderSelection();
}

function renderSelection() {
  selected.replaceChildren();
  chosen.forEach((file, index) => {
    const card = document.createElement('div'); card.className = 'selection';
    const preview = document.createElement('img'); preview.alt = t('Selected image {number}', { number: index + 1 });
    const url = URL.createObjectURL(file); preview.src = url;
    preview.addEventListener('load', () => URL.revokeObjectURL(url), { once: true });
    const info = document.createElement('div'); info.className = 'selection-info';
    const name = document.createElement('span'); name.textContent = file.name; name.title = file.name;
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', t('Remove {name}', { name: file.name }));
    remove.addEventListener('click', () => { chosen.splice(index, 1); renderSelection(); });
    info.append(name, remove); card.append(preview, info); selected.append(card);
  });
  if (chosen.length) message.textContent = t(chosen.length === 1 ? '{count} image selected.' : '{count} images selected.', { count: chosen.length });
}

input.addEventListener('change', () => addFiles(input.files));
dropZone.addEventListener('dragover', event => { event.preventDefault(); dropZone.classList.add('dragging'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
dropZone.addEventListener('drop', event => { event.preventDefault(); dropZone.classList.remove('dragging'); addFiles(event.dataTransfer.files); });

function showResults(data, scroll = true) {
  lastResult = data;
  resultImages.replaceChildren();
  document.querySelector('#results-summary').textContent = t(data.images.length === 1 ? '{count} image ready · {before} → {after} · {percent}% smaller' : '{count} images ready · {before} → {after} · {percent}% smaller', { count: data.images.length, before: formatBytes(data.original_bytes), after: formatBytes(data.output_bytes), percent: data.reduction_percent.toFixed(0) });
  document.querySelector('#download-all').href = data.download_all_url;
  for (const image of data.images) {
    const card = document.createElement('article'); card.className = 'result-card';
    const preview = document.createElement('img'); preview.src = image.preview_url; preview.alt = image.alt_text; preview.loading = 'lazy';
    const info = document.createElement('div'); info.className = 'result-info';
    const name = document.createElement('span'); name.className = 'result-name'; name.textContent = image.filename; name.title = image.filename;
    const size = document.createElement('p'); size.textContent = `${formatBytes(image.original_bytes)} → ${formatBytes(image.output_bytes)}`;
    const download = document.createElement('a'); download.href = image.download_url; download.download = image.filename; download.textContent = t('Download image ↓');
    info.append(name, size, download); card.append(preview, info); resultImages.append(card);
  }
  results.hidden = false;
  if (scroll) results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.addEventListener('image-seo:language-change', () => {
  if (chosen.length) renderSelection();
  if (lastResult && !results.hidden) showResults(lastResult, false);
  if (lastResult && !results.hidden) message.textContent = t('Your images are ready.');
  if (submit.disabled) message.textContent = t('Working on your images…');
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const projectName = document.querySelector('#project-name').value.trim();
  if (!projectName) { message.textContent = t('Enter a project name.'); return; }
  if (!chosen.length) { message.textContent = t('Choose at least one image.'); return; }
  const body = new FormData();
  body.set('project_name', projectName);
  body.set('filename_prefix', document.querySelector('#filename-prefix').value.trim());
  body.set('naming_language', document.querySelector('#naming-language').value);
  chosen.forEach(file => body.append('images', file, file.name));
  submit.disabled = true; submit.querySelector('[data-i18n]').textContent = t('Optimizing…'); message.textContent = t('Working on your images…');
  results.hidden = true;
  try {
    const response = await fetch('/api/public/process', { method: 'POST', body });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not process these images.');
    showResults(data); message.textContent = t('Your images are ready.');
  } catch (error) {
    message.textContent = responseErrorMessage(error);
  } finally {
    submit.disabled = false; submit.querySelector('[data-i18n]').textContent = t('Optimize images');
  }
});

function responseErrorMessage(error) {
  return userMessage(error.message, 'Something went wrong. Please try again.');
}
