function showLoader() {
  document.getElementById('loader').style.display = 'flex';
}

function hideLoader() {
  document.getElementById('loader').style.display = 'none';
}

// Hide loader after page loads (meaning analysis done)
window.addEventListener('load', () => {
  hideLoader();
});

function copyRevisedCode() {
  const revisedCodeEl = document.querySelector('#revised pre');
  if (!revisedCodeEl) return;

  navigator.clipboard.writeText(revisedCodeEl.textContent.trim())
    .then(() => alert('Revised code copied to clipboard! 📋'))
    .catch(() => alert('Failed to copy! Please copy manually.'));

  const copyIcon = document.querySelector('.copy-icon-btn');
  copyIcon.classList.add('animate-copy');
  setTimeout(() => copyIcon.classList.remove('animate-copy'), 300);
}

function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto'; // reset height
  textarea.style.height = textarea.scrollHeight + 'px'; // set to scrollHeight
}

window.addEventListener('DOMContentLoaded', () => {
  const textarea = document.getElementById('code');
  if (!textarea) return;

  // Initialize height on page load if there's content
  autoResizeTextarea(textarea);

  // Adjust height on input (typing, paste, delete)
  textarea.addEventListener('input', () => {
    autoResizeTextarea(textarea);
  });
});