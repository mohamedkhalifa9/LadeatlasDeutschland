# Data Profile — BNetzA Ladesäulenregister

Week 1 output. Source of truth for every number here: [`src/profile.py`](../src/profile.py).

## The file

- Source: Bundesnetzagentur *Ladesäulenregister* (public EV charging station register)
- Local copy: `data/raw/Ladesaeulenregister_BNetzA_2026-09-01.csv`
- Encoding: UTF-8 with a byte-order mark (confirmed with `xxd` / `iconv`); Polars strips
  the BOM automatically on read
- Delimiter: `;` (German CSV convention — `,` is the decimal separator)
- Locale: German decimal commas in numeric fields (e.g. `48,442398`), dates as
  `DD.MM.YYYY`
- 10 junk/preamble lines before the real header row (title, a notice, the last-updated
  date); the real header is the 11th line

## Row and column count

- **116,443 rows** confirmed via `pl.read_csv(...).shape` — this is the number that
  matters, not `wc -l`'s naive count of 146,671. The gap is because some fields contain
  embedded line breaks inside quoted values, which a line-based tool can't distinguish
  from real row boundaries but a CSV-aware parser can.
- **47 columns**, confirmed by name. First column (`Ladeeinrichtungs-ID`) has no leaked
  `﻿` prefix — Polars handled the BOM correctly.

## Structure

The schema is wide: after 23 station-level columns, there are 6 repeated groups of 4
columns each (`Steckertypen`, `Nennleistung Stecker`, `EVSE-ID`, `Public Key`, suffixed
`1`–`6`), one group per possible connector on a station. Null rates rise sharply with
slot number — most stations only populate 1–2 of the 6 slots. This is the wide-format
anti-pattern Week 4's unpivot step will convert into one row per connector.

Full per-column null counts and distinct-value counts are in
[`data_dictionary.md`](data_dictionary.md).

## Anomalies reproduced

Every number below was produced by code in `src/profile.py`, not assumed.

| Check | Result |
|---|---|
| `Ladeeinrichtungs-ID` distinct values | 116,443 — unique per row, candidate business key for a station dimension |
| `Betreiber` (operator) distinct values | 11,755 |
| `Bundesland` distinct values | 16 — exactly the number of German federal states, no stray spelling variants |
| Stations in Nordrhein-Westfalen | 22,500 |
| Total connectors (sum of non-null `Steckertypen1`–`6`) | 209,136 |
| Stations rated above 1,000 kW | 3 — Audi AG (Neckarsulm, 1200 kW), Audi AG (Ingolstadt, 1200 kW), Energie Südbayern GmbH (Wallersdorf, 1800 kW). These read as legitimate large charging hubs, not data errors. |
| Stations commissioned before 2010 | 22 |
| Rows outside Germany's bounding box (lat 47.27–55.06, lon 5.87–15.04) | 4 rows / 3 distinct addresses (see below) |
| Rows sharing identical lat/lon/operator | 41,093 |

### The out-of-bounds rows

Four rows fail the bounding-box check, at three addresses:

| Operator | City | Recorded lat/lon | What's actually wrong |
|---|---|---|---|
| batec group GmbH | Wegberg | 55.122778, 6.21601 | Two separate station records (`Ladeeinrichtungs-ID` 1129475 and 1131144, confirmed distinct — not duplicates) at the same address, sharing the same corrupted latitude. Wegberg's real latitude is ~51°N; `55` in place of `51` looks like a transposed digit. |
| Wirelane GmbH | Lemgo | 52.023038, 4.0 | Latitude matches Lemgo closely. Longitude is wrong — Lemgo's real longitude is ~8.9°E, not 4.0. |
| TankE GmbH | Köln | 50.98463, 5.85372 | Latitude matches Köln closely. Longitude is off by ~1.1° — Köln's real longitude is ~6.96°E. |

None of these are stations genuinely located outside Germany — every operator and city is
a real, ordinary German registration. In each case a single coordinate value (not both)
is corrupted. This check should be read and documented as **a coordinate-corruption
detector**, not a "foreign station" detector.

### The shared lat/lon/operator rows

Grouping by (`Breitengrad`, `Längengrad`, `Betreiber`) produces 14,128 groups with more
than one row, totaling 55,221 rows. The brief's figure of **41,093** is the *excess* row
count — `55,221 − 14,128` — i.e. how many rows would be removed if each group were
deduplicated down to one row. Whether these excess rows are true duplicates or
legitimate distinct stations sharing one address (as seen with the batec case above) is
not resolved by this check alone; it's a candidate rule for `docs/dq_rules.md` in Week 8,
not a decision made here.

## Open items

- `Art der Ladeeinrichtung` has 2 distinct values, not yet identified — check
  `df["Art der Ladeeinrichtung"].unique()` before writing it into the data dictionary as
  more than "2 categories."
- The dedup question for the 41,093 shared-coordinate rows (true duplicates vs.
  legitimate multi-station addresses) is open, to be resolved as a documented rule in
  Week 8.
