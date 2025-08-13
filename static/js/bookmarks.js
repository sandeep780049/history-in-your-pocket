// bookmarks.js - client-only bookmarks stored in localStorage
const BOOKMARK_KEY = "hip_bookmarks_v1";

function loadBookmarks() {
  let raw = localStorage.getItem(BOOKMARK_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch(e) { return []; }
}

function saveBookmarks(list) {
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify(list));
}

function addBookmark(eventObj) {
  const list = loadBookmarks();
  // avoid duplicates by title+date
  const exists = list.some(b => b.title === eventObj.title && b.date === eventObj.date);
  if (exists) return false;
  list.unshift(eventObj);
  saveBookmarks(list);
  return true;
}

function clearBookmarks() {
  localStorage.removeItem(BOOKMARK_KEY);
}

function exportBookmarks() {
  const list = loadBookmarks();
  const ts = new Date().toISOString().slice(0,19).replace(/[:T]/g,"-");
  const filename = `bookmarks-${ts}.json`;
  const content = JSON.stringify(list, null, 2);
  const blob = new Blob([content], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

