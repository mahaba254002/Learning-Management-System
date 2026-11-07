/** Read a CSV file's text into rows of cells. Handles quoted cells, doubled quotes and CRLF. */
export function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", quoted = false;
  const source = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (quoted) {
      if (ch === '"' && source[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && source[i + 1] === "\n") i++;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows.filter(r => r.some(c => c.trim() !== ""));
}

const HEADERS = { admission_number: ["admission_number", "admission number", "admission no", "adm no", "adm"], status: ["status", "fee status"],
  balance: ["balance", "fee balance", "amount due"], note: ["note", "notes", "remark", "remarks"] };

/** Map a fee list to {admission_number, status, balance, note} rows, or throw a readable error. */
export function feeRows(text) {
  const [header, ...body] = parseCsv(text);
  if (!header) throw new Error("The file is empty.");
  const names = header.map(h => h.trim().toLowerCase());
  const index = Object.fromEntries(Object.entries(HEADERS).map(([key, options]) => [key, names.findIndex(n => options.includes(n))]));
  if (index.admission_number < 0 || index.status < 0) throw new Error("The first row must name the columns, including admission_number and status.");
  if (!body.length) throw new Error("The file has no students.");
  if (body.length > 5000) throw new Error("Upload at most 5,000 students at a time.");
  return body.map(cells => Object.fromEntries(Object.entries(index).map(([key, i]) => [key, i < 0 ? "" : (cells[i] || "").trim()])));
}
