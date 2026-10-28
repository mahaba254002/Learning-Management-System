export function downloadCsv(filename, columns, rows) {
  const cell = value => {
    let text = String(value ?? '');
    // Protect spreadsheet users from formulas in names, notes or other imported values.
    if (/^[\s]*[=+@\-\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  const csv = '\uFEFF' + [columns, ...rows].map(row => row.map(cell).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const studentColumns = ['first_name', 'last_name', 'admission_number', 'login_method', 'login_id', 'email', 'phone'];
