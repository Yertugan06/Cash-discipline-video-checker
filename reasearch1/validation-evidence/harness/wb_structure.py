"""Print only the STRUCTURE of the annotation workbook: sheet names, header row, row counts,
per-column fill counts and cardinality. No cell values beyond the header row are printed."""
import sys, openpyxl
wb = openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True)
for ws in wb.worksheets:
    rows = [r for r in ws.iter_rows(values_only=True) if any(v not in (None, '') for v in r)]
    print(f'== sheet {ws.title!r}: {len(rows)} non-empty rows (incl. header), max_col={ws.max_column}')
    if not rows: continue
    hdr = rows[0]
    for i, h in enumerate(hdr):
        col = [r[i] for r in rows[1:] if i < len(r)]
        filled = [v for v in col if v not in (None, '')]
        print(f'  col{i}: header={h!r} filled={len(filled)} distinct={len(set(map(str, filled)))} '
              f'maxlen={max((len(str(v)) for v in filled), default=0)}')
