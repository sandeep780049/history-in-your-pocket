// main.js - small helpers for date -> mm-dd and client interactions

function mmddFromDateInput(dateVal) {
  // dateVal expected 'YYYY-MM-DD'
  if (!dateVal) return null;
  const parts = dateVal.split("-");
  if (parts.length >= 3) {
    return (parts[1].padStart(2,'0') + "-" + parts[2].padStart(2,'0'));
  }
  return null;
}

function setDateToTodayInput(selector) {
  const el = document.querySelector(selector);
  if (!el) return;
  const today = new Date().toISOString().slice(0,10);
  el.value = today;
}

// Copy text to clipboard with fallback
function copyToClipboard(text) {
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  } else {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch(e) {}
    document.body.removeChild(ta);
  }
}

// download JSON or text file
function downloadFile(filename, content, mime='text/plain') {
  const blob = new Blob([content], {type: mime});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

