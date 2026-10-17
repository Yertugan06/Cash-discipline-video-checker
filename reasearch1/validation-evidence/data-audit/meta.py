import zipfile, re, struct, os, hashlib, sys, xml.etree.ElementTree as ET
root = sys.argv[1]
z = zipfile.ZipFile(os.path.join(root, 'open_labels.xlsx'))
ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ss = []
if 'xl/sharedStrings.xml' in z.namelist():
    t = ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in t.findall('m:si', ns):
        ss.append(''.join(x.text or '' for x in si.iter('{%s}t' % ns['m'])))
sh = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
rows = []
for r in sh.iter('{%s}row' % ns['m']):
    vals = []
    for c in r.findall('m:c', ns):
        v = c.find('m:v', ns); is_ = c.find('m:is', ns)
        if c.get('t') == 's' and v is not None: vals.append(ss[int(v.text)])
        elif is_ is not None: vals.append(''.join(x.text or '' for x in is_.iter('{%s}t' % ns['m'])))
        else: vals.append(v.text if v is not None else '')
    rows.append(vals)
for r in rows: print('ROW', r)

def atoms(f, start, end):
    f.seek(start)
    while f.tell() < end:
        pos = f.tell(); h = f.read(8)
        if len(h) < 8: break
        size, typ = struct.unpack('>I4s', h); hdr = 8
        if size == 1: size = struct.unpack('>Q', f.read(8))[0]; hdr = 16
        elif size == 0: size = end - pos
        yield typ.decode('latin1'), pos, pos + hdr, pos + size
        f.seek(pos + size)

def info(path):
    out = {}
    with open(path, 'rb') as f:
        end = os.path.getsize(path)
        for t, p, d, e in atoms(f, 0, end):
            if t == 'moov':
                for t2, p2, d2, e2 in atoms(f, d, e):
                    if t2 == 'mvhd':
                        f.seek(d2); ver = f.read(1)[0]; f.read(3)
                        if ver == 1: f.read(16); ts, dur = struct.unpack('>IQ', f.read(12))
                        else: f.read(8); ts, dur = struct.unpack('>II', f.read(8))
                        out['dur'] = dur / ts
                        f.seek(d2)
                    if t2 == 'trak':
                        tr = {}
                        for t3, p3, d3, e3 in atoms(f, d2, e2):
                            if t3 == 'tkhd':
                                f.seek(d3); ver = f.read(1)[0]; f.read(3)
                                f.read(32 if ver == 1 else 20)
                                f.read(8 + 8); mat = struct.unpack('>9i', f.read(36))
                                w, h = struct.unpack('>II', f.read(8))
                                tr['wh'] = (w / 65536, h / 65536); tr['mat'] = mat[:4]
                            if t3 == 'mdia':
                                for t4, p4, d4, e4 in atoms(f, d3, e3):
                                    if t4 == 'mdhd':
                                        f.seek(d4); ver = f.read(1)[0]; f.read(3)
                                        if ver == 1: f.read(16); ts, dur = struct.unpack('>IQ', f.read(12))
                                        else: f.read(8); ts, dur = struct.unpack('>II', f.read(8))
                                        tr['tdur'] = dur / ts
                                    if t4 == 'minf':
                                        for t5, p5, d5, e5 in atoms(f, d4, e4):
                                            if t5 == 'stbl':
                                                for t6, p6, d6, e6 in atoms(f, d5, e5):
                                                    if t6 == 'stsz':
                                                        f.seek(d6 + 8); tr['n'] = struct.unpack('>I', f.read(4))[0]
                                                    if t6 == 'stsd':
                                                        f.seek(d6 + 12); f.read(4); tr['codec'] = f.read(4).decode('latin1')
                                            
                            f.seek(e3)
                        if 'n' in tr and tr.get('codec') not in (None,) and 'tdur' in tr:
                            tr['fps'] = tr['n'] / tr['tdur'] if tr['tdur'] else 0
                        out.setdefault('tracks', []).append(tr)
                    f.seek(e2)
            f.seek(e)
    return out

vd = os.path.join(root, 'videos')
for fn in sorted(os.listdir(vd), key=lambda s: int(re.sub(r'\D', '', s))):
    p = os.path.join(vd, fn)
    md5 = hashlib.md5(open(p, 'rb').read()).hexdigest()[:10]
    i = info(p)
    vt = [t for t in i.get('tracks', []) if t.get('wh', (0, 0))[0] > 0]
    print('VID', fn, round(os.path.getsize(p) / 1e6, 2), md5, round(i.get('dur', 0), 2),
          [(t.get('codec'), t.get('wh'), t.get('mat'), t.get('n'), round(t.get('fps', 0), 2)) for t in vt], len(i.get('tracks', [])))
