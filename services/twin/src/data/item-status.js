/** Normalize PLC / DB status tokens for matching. */
function norm(status) {
  return String(status ?? '')
    .toLowerCase()
    .trim()
    .replace(/[\s_]+/g, '-');
}

/** Database no-go tag on pos5/pos6 — item left holding for the reject bay. */
export function isNoGoStatus(status) {
  const s = norm(status);
  return s.includes('no-go') || s === 'nogo' || s.includes('nogo');
}

/** Item destined for the reject hole (no-go or explicit scrap). */
export function isRejectStatus(status) {
  const s = norm(status);
  return isNoGoStatus(status) || s.includes('scrap') || s === 'rejected';
}
