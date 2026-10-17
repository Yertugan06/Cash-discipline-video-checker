"""Print header rows and value COUNTS for short categorical columns only (maxlen<=40, distinct<=12).
Free-text columns and per-clip rows are never printed."""
import sys, collections, openpyxl
wb = openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True)
hdr_row = {'Нарушения': 1}
for ws in wb.worksheets:
    rows = [r for r in ws.iter_rows(values_only=True) if any(v not in (None, '') for v in r)]
    h = hdr_row.get(ws.title, 0)
    print(f'== {ws.title}: header row {h}:', [str(x)[:40] if x is not None else None for x in rows[h]])
    for i in range(len(rows[h])):
        vals = [str(r[i]).strip() for r in rows[h+1:] if i < len(r) and r[i] not in (None, '')]
        if vals and len(set(vals)) <= 12 and max(map(len, vals)) <= 40:
            print(f'   col{i}', dict(collections.Counter(vals).most_common()))
