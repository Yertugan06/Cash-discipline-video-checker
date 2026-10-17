"""Pre-registered prompts (v1, frozen 2026-10-17 before any model output was inspected).

The checklist is written from the public RK norms in the team's 'Нормы' sheet (NBRK Resolutions 231, 14, 48;
AML law 191-IV), phrased as viewpoint-independent observable predicates. No clip-specific detail.
"""

CATALOG = [
    ('231-20-2', 'Cash that is not being handled for the current client is left lying openly on the desk/counter '
                 '(not put away into a closed drawer, box or safe), or cash is left unattended.'),
    ('231-80', 'Keys, stamps, seals or safe keys are left lying unattended on the desk where others could take them.'),
    ('231-22', 'The cashier walks away from the workplace while a client is still being served.'),
    ('48-71-9', 'The cashier leaves the workplace while the computer screen stays unlocked/active.'),
    ('14-16-1', 'The door of the cash room / cash desk is left open or unlocked (e.g. standing open while unattended).'),
    ('231-12-1', 'Personal belongings (handbag, backpack, personal wallet) are kept at the cashier workplace.'),
    ('231-12-2', 'A mobile phone is used at the cashier workplace (e.g. talking, photographing, filming).'),
    ('231-19-1', 'Cash is accepted from a client without the cashier checking the client\'s ID document.'),
    ('231-19-2', 'Banknotes are accepted without being counted sheet by sheet / checked.'),
    ('231-20-1', 'Cash received from a client is not counted in the client\'s presence (taken away, counted out of sight).'),
    ('231-31-4', 'Cash is handed out to a client without being counted in the client\'s presence.'),
    ('231-24', 'A cash-collection bag is accepted without checking that the bag and its seal are intact.'),
    ('231-101', 'A cash collector receives bags without showing an ID document.'),
]
EXCEPTION = 'Not a violation: whole sealed bundles of banknotes in intact packaging may be handed out without sheet-by-sheet counting.'


def checklist():
    return '\n'.join(f'- {c}: {d}' for c, d in CATALOG)


DISCOVERY_V1 = f"""You are reviewing a security-camera video of a bank cashier workplace (staff, clients and cash collectors may appear).
Find moments where one of these cash-discipline violations is VISIBLE:
{checklist()}
{EXCEPTION}

Rules:
- Report only what is actually visible. Do not guess about things the video cannot show (accounting, authorisation, identities).
- Many videos contain no violation. If you see none, return an empty list.
- time_sec = the second (from the start of the video) where the violation is most clearly visible.

Answer with JSON only:
{{"events": [{{"time_sec": <number>, "code": "<code from the list>", "observation": "<what is seen, one sentence>", "confidence": "high|medium|low"}}]}}"""


VERIFY_V1 = f"""You are reviewing a short security-camera clip of a bank cashier workplace (staff, clients and cash collectors may appear).
Does any of these cash-discipline violations VISIBLY happen in this clip?
{checklist()}
{EXCEPTION}

Report only what is actually visible; if nothing in the list is clearly visible, answer "no".
Answer with JSON only:
{{"violation": "yes|no", "code": "<code or null>", "time_sec": <number or null>, "observation": "<what is seen, one sentence>"}}"""


# ---- Addendum A2 (written 2026-10-17 after the VERIFY_V1 4B probe; dev split first, lockbox once) -------------------
VERIFY_ITEMS_V2 = f"""You are reviewing a short security-camera clip of a bank cashier workplace (staff, clients and cash collectors may appear).
For EACH item below, decide whether it VISIBLY happens in this clip. Answer "no" unless it is clearly visible.
{checklist()}
{EXCEPTION}

Answer with JSON only, one key per item code, plus the second where the clearest "yes" is visible:
{{{", ".join(f'"{c}": "yes|no"' for c, _ in CATALOG)}, "time_sec": <number or null>, "observation": "<what is seen, one sentence>"}}"""


def parse_items(a):
    """VERIFY_ITEMS_V2 answer dict -> (violation 'yes'|'no', first yes code or None)."""
    yes = [c for c, _ in CATALOG if str(a.get(c, '')).lower().startswith('y')]
    return ('yes' if yes else 'no'), (yes[0] if yes else None)
