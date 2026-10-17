# Rules

Generated from codex.yaml. Source citations are workbook data, not a legal review.

Implemented in v1: 16 detectors. Other entries remain in evaluation as known misses.

## A-DOOR-LOCK

ENTER(person) and no door-close / hand-on-door event within 5 s while the person walks to the desk.

Duration proposal: 5 s. Anchor: Person passes the door.

Source: [NBRK 14, п.8, п.16(1)](https://adilet.zan.kz/rus/docs/V2000020075). Strength: Indirect. Status: Confirmed.

## A-OUTSIDER-ZONE

A person other than the cashier stays inside the cashier zone.

Duration proposal: 2 s. Anchor: First frame in the zone.

Source: [NBRK 14, п.8; NBRK 231, п.75](https://adilet.zan.kz/rus/docs/V2000020075). Strength: Indirect. Status: Confirmed.

## A-SECOND-PERSON

Client session open and a second non-staff person hands an item to the cashier.

Duration proposal: -. Anchor: Second person's handover.

Source: [NBRK 231, п.21, п.22](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Indirect. Status: Confirmed.

## C-ID-BEFORE-CASH

First HANDOVER(client to cashier, cash) of a session with no ID_SHOWN before it.

Duration proposal: whole session. Anchor: First cash handover.

Source: [NBRK 231, п.7, п.19 пп.1, п.31 пп.1](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## C-COUNT-BEFORE-EXIT

EXIT(client) before COUNT_END for that client's cash.

Duration proposal: -. Anchor: Client exit.

Source: [NBRK 231, п.19 пп.2, п.20](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## C-REJECT-NOT-RETURNED

Note from the machine's reject pocket handed to the client.

Duration proposal: -. Anchor: Handover to client.

Source: [NBRK 231, п.59-61](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## C-DETECTOR-CHECK

Rejected note re-stacked with no detector use in between.

Duration proposal: -. Anchor: Re-stack moment.

Source: [NBRK 231, п.9, п.59](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Weak. Status: Candidate.

## S-CLEAN-DESK-HANDOVER

ENTER(client N+1) while cash tagged with session N is on the desk.

Duration proposal: -. Anchor: Next client's entry.

Source: [NBRK 231, п.20](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## S-NO-MERGE

Cash tagged N joins a stack tagged N+1.

Duration proposal: -. Anchor: Moment the stacks join.

Source: [NBRK 231, п.20, п.21](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## S-SAFE-CLOSED

Safe door open while the cashier is away from the safe zone.

Duration proposal: 3 s. Anchor: Cashier leaves the safe zone.

Source: [NBRK 231, п.20](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Indirect. Status: Confirmed.

## K-COLLECTOR-DOC

HANDOVER(collector to cashier, bag) with no document shown during the collector's visit.

Duration proposal: -. Anchor: Bag handover.

Source: [NBRK 231, п.24 пп.1-2 (п.106-107 to read)](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## K-SEAL-CHECK

Collector exits within ~5 s of the bag handover with no inspection of the bag.

Duration proposal: 5 s. Anchor: Collector exit.

Source: [NBRK 231, п.24 пп.3-4, п.25, п.94](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## K-RECOUNT-BEFORE-SAFE

Bundles move from the bag to the safe without passing the counter or a hand count.

Duration proposal: -. Anchor: Bundles go into the safe.

Source: [NBRK 231, п.42, п.74](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Indirect. Status: Confirmed.

## L-NO-CASH-ON-LEAVE

EXIT(cashier) while cash is on the desk.

Duration proposal: -. Anchor: Cashier leaves the desk zone.

Source: [NBRK 231, п.20, п.22](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## L-NO-BAG-ON-LEAVE

EXIT(cashier) while a collection bag is on the desk.

Duration proposal: -. Anchor: Cashier leaves the desk zone.

Source: [NBRK 231, п.20, п.80](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## L-NO-DOCS-ON-LEAVE

EXIT(cashier) while a document or tablet is on the desk.

Duration proposal: -. Anchor: Cashier leaves the desk zone.

Source: [NBRK 231, п.80](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Indirect. Status: Confirmed.

## L-PC-LOCKED

EXIT(cashier) while the laptop shows a working (not lock) screen.

Duration proposal: -. Anchor: Cashier leaves the desk zone.

Source: [NBRK 48, п.71 пп.9 (repealed; successor to confirm)](https://adilet.zan.kz/rus/docs/V1800016772). Strength: Indirect. Status: Confirmed.

## L-SAFE-LOCKED-ON-LEAVE

EXIT(cashier) with no safe-locking motion after the last safe use.

Duration proposal: -. Anchor: Cashier leaves.

Source: [NBRK 231, п.20, п.78](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Indirect. Status: Candidate.

## W-NO-PERSONAL-ITEMS

Coat, handbag or similar item on the cash desk.

Duration proposal: 3 s. Anchor: Item placed on the desk.

Source: [NBRK 231, п.12](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Confirmed.

## W-NO-FOOD

Food or a cup raised to the mouth at the cash desk.

Duration proposal: 1 s. Anchor: First bite or sip.

Source: [No explicit clause found; nearest NBRK 231, п.12](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Weak. Status: Confirmed.

## W-NO-CAMERA-PHONE

A phone visible in the cashier's hand or on the desk.

Duration proposal: 2 s. Anchor: Phone first visible.

Source: [NBRK 231, п.12](https://adilet.zan.kz/rus/docs/V1900019680). Strength: Direct. Status: Candidate.
