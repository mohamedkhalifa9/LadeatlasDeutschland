# Data Dictionary v0 — BNetzA Ladesäulenregister

One row per source column. `n_unique` and `nulls` are measured on all 116,443 rows via
[`src/profile.py`](../src/profile.py). Types are what the column becomes *after* the
cleanup steps in that script (German decimal-comma → float, `DD.MM.YYYY` → date);
everything else is read as a plain string.

## Station-level columns

| Column | Type | n_unique | nulls | Meaning |
|---|---|---|---|---|
| `Ladeeinrichtungs-ID` | string | 116,443 | 0 | BNetzA's unique ID for the station. Unique per row — candidate business key. |
| `Betreiber` | string | 11,755 | 0 | Operating company's legal name, self-reported. Highly fragmented — many spelling variants of the same real operator. |
| `Anzeigename (Karte)` | string | 1,922 | 64,578 | Display name shown on the public BNetzA map. Optional; most rows have none. |
| `Status` | string | 2 | 0 | Operational status. Values: `In Betrieb` (in operation), `In Wartung` (under maintenance). |
| `Art der Ladeeinrichtung` | string | 2 | 0 | Station type category. **Values not yet confirmed** — check `.unique()` before relying on this. |
| `Anzahl Ladepunkte` | string | 6 | 0 | Number of charge points at the station. Bounded at 6, consistent with the 6 connector-slot groups below. |
| `Nennleistung Ladeeinrichtung [kW]` | float | 253 | 0 | Total rated power output of the station, in kW. |
| `Inbetriebnahmedatum` | date | 3,924 | 0 | Commissioning date. |
| `Straße` | string | 35,414 | 0 | Street name. |
| `Hausnummer` | string | 2,668 | 0 | House/building number. |
| `Adresszusatz` | string | 8,598 | 95,784 | Address supplement (building, floor, etc.). Mostly blank. |
| `Postleitzahl` | string | 7,315 | 0 | German postal code. |
| `Ort` | string | 7,690 | 0 | City/town. |
| `Kreis/kreisfreie Stadt` | string | 401 | 0 | District or independent city. |
| `Bundesland` | string | 16 | 0 | Federal state. Exactly the 16 real German states — no stray variants. |
| `Breitengrad` | float | 73,249 | 0 | Latitude. |
| `Längengrad` | float | 73,621 | 0 | Longitude. |
| `Standortbezeichnung` | string | 21,951 | 83,914 | Free-text site description. Mostly blank. |
| `Informationen zum Parkraum` | string | 6 | 58,309 | Parking availability/restriction info. About half blank. |
| `Bezahlsysteme` | string | 1,402 | 12,009 | Accepted payment systems; semicolon-separated within the field. |
| `Öffnungszeiten` | string | 3 | 0 | Opening-hours category. |
| `Öffnungszeiten: Wochentage` | string | 30 | 74,331 | Days of the week the detailed hours apply to. Blank when hours are unrestricted. |
| `Öffnungszeiten: Tageszeiten` | string | 427 | 74,331 | Time-of-day ranges for opening hours. Blank for the same reason as above. |

## Connector-slot columns (repeated 6×, suffixed 1–6)

Each station has up to 6 connector slots. For slot *N* (1–6):

| Column pattern | Meaning |
|---|---|
| `Steckertypen{N}` | Connector/plug type for slot *N* (e.g. Typ 2, CCS, CHAdeMO). |
| `Nennleistung Stecker{N}` | Rated power of that connector, in kW. |
| `EVSE-ID{N}` | European charge-point identifier (EVSE ID) for that connector. Often blank even for slot 1. |
| `Public Key{N}` | Cryptographic public key associated with that connector's authentication. Often blank even for slot 1. |

Null counts rise sharply with slot number — most stations only use 1–2 slots:

| Slot | `Steckertypen{N}` n_unique | nulls | Non-null (has a connector here) |
|---|---|---|---|
| 1 | 58 | 0 | 116,443 |
| 2 | 31 | 32,333 | 84,110 |
| 3 | 25 | 111,095 | 5,348 |
| 4 | 14 | 113,484 | 2,959 |
| 5 | 7 | 116,292 | 151 |
| 6 | 5 | 116,318 | 125 |

Summed non-null count across all 6 slots: **209,136** — the total connector count. This
wide, repeated-group shape is what Week 4's unpivot step turns into one row per
connector, at which point each of the 4 sub-columns above becomes a single column on the
long table.

## Open items

- `Art der Ladeeinrichtung`'s two values are unconfirmed — resolve before Week 5's
  dimensional modelling depends on it.
- Whether `Anzeigename (Karte)`'s high null rate should be backfilled from `Betreiber`,
  left null, or treated some other way is a modelling decision for later, not decided
  here.
