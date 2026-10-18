"""Norm-code matching shared by the scorer and the probes."""
import re


def code_key(s):
    """'п. 20 ч. 2' / '231-20-2' / '14-16-1' / '53-71-9' -> '20-2' / '20-2' / '16-1' / '71-9' for
    loose norm matching (the act number is dropped)."""
    if not s:
        return None
    n = re.findall(r'\d+', str(s))
    if str(s).startswith(('231', '14-', '48-', '53-')) and len(n) > 1:
        n = n[1:]
    return '-'.join(n[:2]) if n else None


def code_match(a, b):
    """Same clause number, and same sub-item when both sides give one."""
    a, b = code_key(a), code_key(b)
    if not a or not b:
        return False
    a, b = a.split('-'), b.split('-')
    return a[0] == b[0] and (len(a) == 1 or len(b) == 1 or a[1] == b[1])
