import test from 'node:test';
import assert from 'node:assert/strict';
import { feeRows, parseCsv } from '../src/pages/records/csv.js';

test('parses quoted cells, doubled quotes and CRLF', () => {
  assert.deepEqual(parseCsv('﻿a,b\r\n"x, y","say ""hi"""\r\n\r\n'), [['a', 'b'], ['x, y', 'say "hi"']]);
});

test('maps fee list columns by name in any order', () => {
  const rows = feeRows('Status,Adm No,Balance\nPaid,A001,\nPartial,A002,"3,000"\n');
  assert.deepEqual(rows, [
    { admission_number: 'A001', status: 'Paid', balance: '', note: '' },
    { admission_number: 'A002', status: 'Partial', balance: '3,000', note: '' },
  ]);
});

test('refuses a fee list without the required columns', () => {
  assert.throws(() => feeRows('name,amount\nJane,10\n'), /admission_number and status/);
  assert.throws(() => feeRows('admission_number,status\n'), /no students/);
});
