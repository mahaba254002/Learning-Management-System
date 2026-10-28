export function recordRevision(records) {
  return JSON.stringify(records.map(row => [row.id, row.updated_at]).sort((a, b) => a[0].localeCompare(b[0])));
}
