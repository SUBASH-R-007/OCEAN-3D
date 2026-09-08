/** Keep the full slider range while bounding labels for long archives. */
export function timelineIndices(count: number, limit = 5): number[] {
  if (!Number.isInteger(count) || count < 1 || !Number.isInteger(limit) || limit < 2) return [];
  const n = Math.min(count, limit);
  return Array.from({length:n}, (_,i)=>n===1?0:Math.round(i*(count-1)/(n-1)));
}
