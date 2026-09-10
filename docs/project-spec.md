# Ladeatlas Deutschland — Full Project Specification

_Data engineering learning project. Spec written 2026-09-08._

**The question it answers:** Where in Germany is charging infrastructure actually being
built, who is building it, and where are the gaps?

**Source data:** BNetzA Ladesäulenregister (updated 1 September 2026). ~54 MB CSV,
116,443 charging stations, 47 columns, records back to 1992. NRW is the second-largest
state with ~22,500 stations.

**Known messiness (all confirmed by profiling):**

- Byte-order mark, semicolon delimiter, German decimal commas (`48,442398`)
- 10 rows of junk before the real header
- 209,136 charging connectors hidden across 6 repeated column groups
  (`Steckertypen1..6`, `Nennleistung Stecker1..6`) — a wide-to-long unpivot
- 41,093 rows sharing lat/lon/operator — duplicates or genuine multi-station sites? A
  judgment call
- 3 stations outside Germany's bounding box, 3 rated above 1,000 kW, 22 commissioned
  before 2010 (earliest 1992)
- 11,755 distinct operators to clean and group

**Effort:** ~12 weeks at 6 h/week = 72 h.

---

## 0. How we work together (teaching mode)

- **I explain concepts, you write the code.** Each week I give the "why", the
  vocabulary, the design decisions, and pointers to docs. You implement. I review, ask
  questions, help debug.
- **I give exercises and checkpoints, not solutions.** When you're stuck I hint before
  answering outright.
- **I write throwaway diagnostic snippets** only while we debug together — never the
  pipeline itself.
- **You can ask me to just show you** a pattern if truly blocked — but the default is
  you build it.
- Say so explicitly if you want me to switch to writing code.

---

## 1. Project structure — four layers

| Layer | Skill cluster | Weeks |
|---|---|---|
| 1. Ingest & clean into cloud storage | Cloud fundamentals, encoding, medallion architecture, columnar formats | 1–3 |
| 2. Dimensional model (star schema) | Kimball modelling, grain, conformed dimensions, surrogate keys | 4–7 |
| 3. Data quality & governance | DQ dimensions, rule catalogues, lineage, data dictionary, ownership | 8 |
| 4a. Power BI | Semantic model, relationships, DAX, report design, publishing | 9–10 |
| 4b. RAG / text-to-SQL | Schema linking, few-shot prompting, guardrails, eval-driven dev | 11–12 |

Weeks 11–12 are the most likely to slip. If behind, they compress to one week or become
a documented stretch goal. Everything through Week 10 is the real portfolio piece.

---

## 2. Prerequisites & one hard constraint

**Install now:**

- Python 3.12 + a virtualenv tool (`uv` or `venv`)
- [Polars](https://docs.pola.rs/) (recommended over pandas — teaches expression thinking;
  pandas acceptable if already known)
- DuckDB CLI (scratch SQL engine, used constantly)
- Azure CLI (`az`)
- Git + a GitHub repo
- VS Code

**Hard constraint — Power BI is Windows-only, and you are on macOS.** Decide by Week 8:

| Option | Cost | Notes |
|---|---|---|
| Azure Windows VM (B2s), started only during Power BI sessions | ~€0.10/h → ~€3 for the project if stopped every time | Recommended. Also teaches VM lifecycle + cost discipline. |
| Parallels / VMware Fusion + a Windows license | one-time license cost | Best if you'll keep using Power BI afterwards |
| Power BI Service (browser) only | free | Limited modelling; loses part of the learning. Fallback only. |

**Track B (zero-cloud mirror):** every cloud step has a local equivalent — ADLS
containers → local folders `raw/ staging/ curated/`; Azure SQL → a DuckDB file. The
architecture shape stays identical, so the learning transfers. Track B swap noted per
week.

---

## 3. Cloud decision — settled: Azure

Reasoning (understand it, don't just accept it):

1. **Power BI is Microsoft.** Tightest, best-documented path is Azure SQL → Power BI.
2. **The German enterprise/Mittelstand market skews Azure** (or on-prem SQL Server — same
   skills). Job ads pairing "Datenmodellierung" + "Power BI" are overwhelmingly Microsoft
   stack.
3. **The free tier fits.** New Azure account ≈ €170–200 credit for 30 days + always-free
   allowances. This project's realistic spend fits inside that.
4. **Serverless Azure SQL** teaches cloud cost mechanics viscerally: auto-pauses after
   1 h idle, per-second billing while awake.

**Concrete stack:**

| Concern | Service | Why |
|---|---|---|
| Data lake | Azure Data Lake Storage Gen2 (storage account, hierarchical namespace on) | Real object storage; containers, blobs, tiers, immutability, partitioning |
| ETL compute | Python + Polars, run locally weeks 1–7 | Don't pay for compute the laptop can do. Cloud-scheduled run is a Week 12 stretch. |
| Warehouse / serving layer | Azure SQL Database, serverless, Gen5 1–2 vCore, auto-pause 1 h | Cheap, real T-SQL, native Power BI connector, teaches keys/indexes/columnstore |
| BI | Power BI Desktop → Power BI Service | The 42% skill |
| RAG backend | Same Azure SQL DB, read-only login + an LLM API | Reuses the star schema as the knowledge base |
| Secrets | `.env` locally (git-ignored); Azure Key Vault as a stretch | Never commit a connection string |
| Infra provisioning | Azure Portal + saved `az` CLI scripts; Bicep as a stretch | Learn the primitives before the abstraction |

---

## 4. Target architecture

```
  SOURCE                 LAYER 1: LAKE (ADLS Gen2)              LAYER 2: WAREHOUSE        LAYER 4
                                                                (Azure SQL serverless)

 BNetzA CSV  ──ingest──▶  raw/ladesaeulen/                     ┌────────────────┐
 (54 MB,                    ingest_date=2026-09-08/            │  dim_date      │      ┌───────────┐
  semicolons,                ladesaeulenregister.csv          │  dim_location  │      │ Power BI  │
  BOM, junk    (byte-for-byte, immutable, + manifest.json)    │  dim_operator  │◀────▶│  report   │
  header,                        │                            │  dim_conn_type │      │ (4a)      │
  wide)                          │ parse + typecast + rename   │  dim_station   │      └───────────┘
                                 ▼                            │  fact_connector│
                          staging/ladesaeulen/                │  fact_station  │      ┌───────────┐
                            stations_wide.parquet    ──load──▶ └────────────────┘◀────▶│ text-to-  │
                                 │                                     ▲               │ SQL / RAG │
                                 │ unpivot 6 connector groups          │               │ (4b)      │
                                 ▼                            ┌────────┴────────┐      └───────────┘
                          staging/ladesaeulen/                │ LAYER 3          │
                            connectors_long.parquet           │ dq_rules        │
                                 │                            │ dq_results      │
                                 │ build dims + facts         │ quarantine      │
                                 ▼                            │ data dictionary │
                          curated/  (dims + facts as parquet) │ (docs in repo)  │
                                                              └─────────────────┘
```

**Medallion / multi-hop pattern (raw → staging → curated):**

- **Raw is immutable and never edited.** Reprocess = re-run from raw. Partitioned by
  `ingest_date` so a later re-download doesn't overwrite history.
- **Staging is disposable.** Deterministic transforms only — same raw file in, byte-identical staging out.
- **Curated is the contract.** The only thing downstream (warehouse, Power BI) may depend on.

---

## 5. The star schema

### Grain statements (put these on a sticky note)

- **`fact_connector`: one row per physical charging connector** (a single plug — the
  thing hidden in `Steckertypen1..6`). Expected ~209,136 rows.
- **`fact_station`: one row per charging station** (`Ladeeinrichtung` — one source row
  after dedup). Expected ~116,443 minus duplicates.

Two facts at different grains sharing conformed dimensions — textbook Kimball, and this
dataset demonstrates it perfectly. `fact_station` exists so "how many charging sites"
never accidentally counts connectors.

```
                         ┌──────────────────┐
                         │     dim_date     │
                         │──────────────────│
                         │ date_key    (PK) │   ← surrogate int, yyyymmdd
                         │ full_date        │
                         │ year, quarter    │
                         │ month, month_de  │
                         │ iso_week         │
                         │ is_weekend       │
                         └───┬──────────┬───┘
                             │          │
   ┌──────────────────┐      │          │      ┌────────────────────────┐
   │   dim_operator   │      │          │      │   dim_connector_type   │
   │──────────────────│      │          │      │────────────────────────│
   │ operator_key (PK)│      │          │      │ connector_type_key (PK)│
   │ name_raw         │      │          │      │ type_raw               │
   │ name_clean       │      │          │      │ type_standard          │  Typ 2 / CCS /
   │ operator_group   │      │          │      │ current_type           │  CHAdeMO / Schuko…
   │ operator_type    │      │          │      │ charge_mode            │  AC/DC, Normal/Schnell
   └────┬─────────────┘      │          │      └───────────┬────────────┘
        │            ┌───────┴───────┐  │  ┌───────────────┴──┐
        │            │ FACT_CONNECTOR│  │  │   FACT_STATION   │
        ├───────────▶│───────────────│◀─┼─▶│──────────────────│◀──────┐
        │            │ connector_bk  │  │  │ station_key  (FK)│       │
   ┌────┴───────────┐│ date_key   FK │  └─▶│ date_key     (FK)│       │
   │  dim_location  ││ location_key FK│◀─┐  │ location_key (FK)│◀──┐   │
   │────────────────││ operator_key FK│  │  │ operator_key (FK)│   │   │
   │ location_key PK││ conn_type_key FK│ │  │ num_charge_points│   │   │
   │ latitude       ││ station_key  FK│  │  │ num_connectors   │   │   │
   │ longitude      ││───────────────│  │  │ total_power_kw   │   │   │
   │ plz, ort       ││ rated_power_kw │  │  │ public_access    │   │   │
   │ kreis          ││ is_fast_charge │  │  │ station_count = 1│   │   │
   │ bundesland     ││ connector_cnt=1│  │  └──────────────────┘   │   │
   │ region         │└───────────────┘  │                         │   │
   └────────────────┘                   │   ┌──────────────────┐   │   │
        conformed ────────────────────────▶│   dim_station     │───┘   │
        (shared by both facts)         │   │──────────────────│       │
                                       │   │ station_key  (PK)│       │
                                       │   │ station_bk       │  ─────┘ degenerate-ish
                                       │   │ station_type     │        business key
                                       │   │ num_charge_points│
                                       │   │ address rollup   │
                                       └───│ commissioning_dt │
                                           └──────────────────┘
```

### Dimension notes

| Dimension | Natural key | Teaching point |
|---|---|---|
| `dim_date` | the date itself | Pre-generated calendar 1990→2030. Never derive year/quarter in a query — join. Covers the 1992 earliest commissioning. |
| `dim_connector_type` | `type_raw` string | Small, near-enumerable reference dimension. Every dirty raw string maps to exactly one `type_standard` or explicitly to `Unbekannt`. |
| `dim_location` | rounded (lat, lon) + plz + street | Where the 41,093 shared-coordinate rows get resolved. `bundesland` from a PLZ→Bundesland lookup or reverse geocode. Out-of-Germany points quarantined. |
| `dim_operator` | `name_raw` | The 11,755-operators problem. Hand-curate a crosswalk for the top ~50 by station count, rolling `name_raw` → `operator_group` (e.g. every `EnBW …` variant → `EnBW`). Owned, dated, reviewable. |
| `dim_station` | constructed `station_bk` | Keeps station attributes out of `fact_connector`. |

### Measure classification (this IS the modelling skill)

| Measure | Additivity | What you must teach yourself |
|---|---|---|
| `connector_count`, `station_count` | Fully additive | Safe to `SUM` across every dimension |
| `rated_power_kw` (installed capacity) | Additive across location/operator/type; not meaningful to sum "over time" for one connector | Only a commissioning date exists, no monthly snapshot. "Capacity added in Q3 2025" is additive; "capacity of a connector across quarters" is nonsense. |
| `is_fast_charge` | It's a flag — never sum it. `COUNT` of fast chargers is additive. | Flags vs measures |
| points per station, avg power | Non-additive | Must be `SUM(x)/SUM(y)` in DAX, never an average of averages |

---

## 6. Repository structure

```
ladeatlas-deutschland/
├── README.md
├── pyproject.toml
├── .env.example              # documented, committed
├── .gitignore                # .env, .parquet, .venv
├── infra/
│   ├── 01_resource_group.sh
│   ├── 02_storage_account.sh
│   ├── 03_sql_server.sh
│   └── notes.md              # what each resource is, what it costs
├── src/
│   ├── ingest.py            # raw download + manifest
│   ├── parse.py             # raw → staging wide
│   ├── unpivot.py           # staging wide → connectors long
│   ├── build_dims.py
│   ├── build_facts.py
│   ├── load_warehouse.py
│   └── dq_check.py
├── sql/
│   ├── ddl/                 # CREATE TABLE for star + dq tables
│   └── analysis/            # queries you validate Power BI against
├── rag/
│   ├── schema_context.md
│   ├── examples.jsonl       # question → SQL pairs
│   ├── pipeline.py
│   └── eval/
│       ├── gold.jsonl
│       └── run_eval.py
├── powerbi/
│   └── ladeatlas.pbix
└── docs/
    ├── data_profile.md         # Week 1
    ├── data_dictionary.md      # Week 1, finalised Week 8
    ├── grain_statement.md      # Week 5
    ├── source_to_target.md     # Week 8
    ├── dq_rules.md             # Week 8
    ├── operator_crosswalk.csv  # Week 6
    └── findings.md             # Week 10
```

---

## 7. Week by week

Each week: **Concepts** (what I teach) → **Build** (what you do) → **Deliverable** →
**Done when** → **Stretch**.

### Week 1 — Ground truth & profiling
_No cloud yet. Learn the data before touching it._

- **Concepts:** data profiling; character encoding (BOM, UTF-8 vs Latin-1/Windows-1252);
  delimiters; locale (German decimal comma, date formats); schema inference vs schema
  contract; "look at the data" as a discipline.
- **Build:** a profiling script that, for all 47 columns, reports dtype, null rate,
  distinct count, min/max, top-10 values, and reproduces every anomaly — 209,136
  connectors, 41,093 shared coordinates, 3 out-of-bbox, 3 over 1,000 kW, 22 pre-2010,
  11,755 operators, 22,500 NRW stations.
- **Deliverable:** `docs/data_profile.md` (1–2 pages) + `docs/data_dictionary.md` v0,
  one plain sentence per column.
- **Done when:** you can explain every column unprompted, and you regenerated the anomaly
  numbers yourself.
- **Stretch:** diff the BNetzA schema against their PDF documentation; note undocumented
  columns.

### Week 2 — Cloud foundations & the raw zone

- **Concepts:** Azure account / subscription / resource group / region; storage account;
  ADLS Gen2 & hierarchical namespace; containers vs blobs; access tiers (hot/cool/archive)
  & storage cost model; immutability of raw; partitioning by ingest date; idempotency;
  manifests & content hashing.
- **Build:** create a resource group + storage account with `raw/ staging/ curated/`
  containers. `src/ingest.py`: download the BNetzA CSV, upload byte-for-byte to
  `raw/ladesaeulen/ingest_date=YYYY-MM-DD/`, write `manifest.json` (source URL,
  retrieved-at, SHA-256, byte size, raw line count).
- **Deliverable:** file in the cloud + manifest; 3 sentences on why raw is immutable and
  date-partitioned.
- **Done when:** delete the local copy, pull it back from `raw/`, SHA-256 matches.
- **Track B:** `raw/` is a local folder; manifest is the same.
- **Stretch:** a lifecycle rule moving blobs older than 90 days to Cool.

### Week 3 — Parsing & the cleaned zone (still wide)

- **Concepts:** deterministic parsing; skipping the 10 junk rows; header normalisation
  (snake_case, English); type casting; locale-aware number/date parsing in code;
  whitespace trimming; columnar formats — why Parquet (compression, predicate pushdown,
  embedded schema) vs CSV; schema-as-contract.
- **Build:** `src/parse.py`: raw CSV → `staging/ladesaeulen/stations_wide.parquet`. Still
  one row per station. Columns renamed, decimal commas → floats, dates → real dates,
  strings trimmed. Add `_ingest_id` and `_row_hash`. Write the schema to a file.
- **Deliverable:** staging Parquet + explicit schema file (column, type, nullable).
- **Done when:** row count = raw count − documented drops; nothing that should be
  numeric/date is still a string; re-running gives a byte-identical file.
- **Stretch:** validate against the schema with Pandera or a Polars assertion set.

### Week 4 — The unpivot (wide → long) — the modelling exercise

- **Concepts:** tidy data; wide vs long; the repeated-column-group anti-pattern; unpivot /
  melt / unnest; declaring grain; handling empty repeated slots.
- **Build:** `src/unpivot.py`: turn `Steckertypen1..6` + `Nennleistung Stecker1..6` (and
  any other `…1..6` groups) into one row per connector. Drop empty slots. Output
  `staging/ladesaeulen/connectors_long.parquet`. Carry the station business key.
- **Deliverable:** connector-grain dataset + a hand-drawn before/after diagram.
- **Done when:** count of non-empty connector slots in source == row count in the long
  table (~209,136); you can state the grain in one sentence.
- **Stretch:** detect and log rows where `Steckertyp` is filled but `Nennleistung` is null
  (or vice versa).

### Week 5 — Dimensional modelling I: theory + `dim_date`, `dim_connector_type`

- **Concepts:** Kimball method; fact vs dimension; star vs snowflake; declaring the grain
  first; surrogate vs natural keys; additive / semi-additive / non-additive measures;
  conformed dimensions. Read: Kimball's Dimensional Modeling Techniques list.
- **Build:** `dim_date` (generated calendar 1990–2030, German month & quarter labels, ISO
  week, weekend flag, `date_key` = yyyymmdd int). `dim_connector_type` (curated list of
  standard types + a `type_raw → type_standard` crosswalk covering every distinct raw
  value).
- **Deliverable:** two dimension tables + `docs/grain_statement.md` (grain of both facts,
  one sentence each).
- **Done when:** every distinct raw connector-type string maps to exactly one standard
  value or explicitly to `Unbekannt` — zero unmapped.
- **Stretch:** add `charge_mode` (Normalladung ≤ 22 kW AC / Schnellladung DC or > 22 kW)
  and defend the threshold.

### Week 6 — Dimensional modelling II: `dim_location`, `dim_operator`

- **Concepts:** conformed dimension design; deriving a natural key from messy data;
  standardisation; fuzzy matching (`rapidfuzz`); crosswalk / mapping tables; SCD types
  0/1/2 (conceptually — you implement Type 1). The 41,093 shared-coordinate rows and the
  11,755 operators both land here.
- **Build:**
  - `dim_location`: dedupe on rounded (lat, lon) + PLZ + street. Add `bundesland`
    (PLZ→Bundesland lookup, or reverse geocode). Flag/quarantine the 3 out-of-Germany
    points. Decide and document: one physical address = one location row even if 5
    stations sit there (yes — location is conformed and reused).
  - `dim_operator`: `name_raw` → `name_clean` (trim, case, legal-form normalisation) →
    `operator_group` via `docs/operator_crosswalk.csv`, hand-curated for the top ~50
    operators by station count, each with `owner` and `last_reviewed`. Everyone else →
    `operator_group = name_clean`.
- **Deliverable:** both dimensions + the committed crosswalk CSV.
- **Done when:** top-50 crosswalk covers a majority of stations; every station resolves to
  a location and an operator; out-of-Germany rows are in quarantine, not `dim_location`.
- **Stretch:** classify `operator_type` (energy utility / automotive / municipal / retail
  / dedicated CPO) for the top 50.

### Week 7 — Build the facts, load the star into Azure SQL

- **Concepts:** lake vs warehouse — why a relational serving layer; serverless SQL
  economics (per-second billing, auto-pause, cold-start latency); primary & foreign keys
  as enforced contracts; indexing basics — clustered vs nonclustered, columnstore indexes
  for fact tables; surrogate-key assignment; load patterns (truncate-and-reload vs
  incremental — you do truncate-and-reload).
- **Build:** create the Azure SQL server + serverless DB (Gen5, 1–2 vCore, auto-pause
  1 h). `sql/ddl/` for all dims + both facts with PK/FK constraints and a clustered
  columnstore index on each fact. `src/build_facts.py` assembles `fact_connector` and
  `fact_station` with all FKs resolved to surrogate keys. `src/load_warehouse.py` loads
  curated Parquet → Azure SQL.
- **Deliverable:** queryable star schema in the cloud + an ER diagram.
- **Done when:** zero orphan foreign keys; "connectors commissioned per year per
  Bundesland" matches a DuckDB cross-check on the Parquet.
- **Track B:** DuckDB file instead of Azure SQL; same DDL (minor syntax differences — a
  good exercise).
- **Stretch:** make `dim_operator` SCD Type 2 so an operator rename keeps history.

### Week 8 — Data quality & governance layer

- **Concepts:** the six DQ dimensions (completeness, validity, consistency, uniqueness,
  accuracy, timeliness); rule catalogues; quarantine vs reject vs flag vs auto-fix;
  test-driven data; lineage; the data dictionary as a living document; ownership.
- **Build:**
  - `dq_rules` table + `docs/dq_rules.md`: ~10 documented rules, each with `id`,
    description (DE + EN), severity, action, owner, last_reviewed. Minimum set:
    1. Coordinates inside Germany bbox (~lat 47.2–55.1, lon 5.8–15.1) → quarantine (the 3)
    2. `0 < rated_power_kw ≤ 1000` → flag the 3 over 1,000
    3. Commissioning date not in the future, not before 1990 → flag the 22 pre-2010, keep
    4. PLZ is 5 digits in a valid German range
    5. Connector type ∈ accepted enumeration → else `Unbekannt` + flag
    6. Operator not null / not "unbekannt"
    7. Referential integrity: every fact FK resolves
    8. Station business key unique after dedup
    9. **The judgment rule** for the 41,093 shared coordinates — e.g. "same rounded
       lat/lon + same operator + same commissioning date + same connector configuration
       ⇒ duplicate (keep one); otherwise co-located distinct stations (keep all)." Write
       the rationale.
    10. `Steckertyp` present ⇔ `Nennleistung` present
  - `src/dq_check.py` writes results to a `dq_results` table (`rule_id`, `run_id`,
    `rows_checked`, `rows_failed`, sample failing keys). Rejects → a `quarantine` table.
  - Finalise `docs/data_dictionary.md`; write `docs/source_to_target.md` (every target
    column ← source column + transformation).
- **Deliverable:** DQ run report + governance doc pack.
- **Done when:** every rule has all six attributes; the checker runs green or with
  warnings you can each explain; every shared-coordinate row is classified.
- **Stretch:** wire into Great Expectations or `dbt test` instead of hand-rolled checks.

### Week 9 — Power BI I: semantic model & core report

- **Concepts:** Import vs DirectQuery (and why Import here); modelling a star in Power BI;
  relationships, cardinality, single- vs bi-directional filtering; calculated columns vs
  measures (and why you almost always want measures); DAX basics (`CALCULATE`, `SUM`,
  `DIVIDE`); basic time intelligence.
- **Build:** (on the chosen Windows environment) connect Power BI Desktop to Azure SQL.
  Relationships: both facts → `dim_date`, `dim_location`, `dim_operator`; `fact_connector`
  → `dim_connector_type`, `dim_station`. Core measures: `Connector Count`, `Station
  Count`, `Total Rated Power (kW)`, `Fast-Charge Share %`, `Connectors Added YoY %`.
  Visuals: a map (stations by lat/lon), a buildout-over-time line, a Bundesland bar.
- **Deliverable:** a one-page report.
- **Done when:** map, trend, and Bundesland bar cross-filter each other correctly; every
  total matches the equivalent query in `sql/analysis/`.
- **Stretch:** a disconnected "power threshold" slicer parameter driving the fast-charge
  definition dynamically.

### Week 10 — Power BI II: the analytical story & gap analysis

- **Concepts:** report design for an audience (inverted pyramid, one message per page);
  drill-through & bookmarks; per-capita normalisation (population per Bundesland);
  defining "a gap" quantitatively; publishing to the Power BI Service; scheduled refresh +
  gateway concepts.
- **Build:** a "drill by Bundesland" page; a "coverage gaps" page (connectors per 100k
  inhabitants, fast-charge deserts by PLZ region, DC share). Publish to the Service. Set
  up scheduled refresh, or document precisely why it's manual. Write `docs/findings.md` —
  three defensible findings with supporting visuals.
- **Deliverable:** published report + findings memo.
- **Done when:** a stranger opens the report and can answer "where is Germany behind on
  charging infrastructure?" in 30 seconds.
- **Stretch:** a simple linear projection of when each Bundesland hits a target
  connectors-per-capita at its current build rate.

### Week 11 — RAG / text-to-SQL I

- **Concepts:** why text-to-SQL is a retrieval problem (retrieve schema context, not
  documents); schema linking; few-shot prompting with curated examples; the guardrail
  surface — read-only DB login, SELECT-only parsing, mandatory `LIMIT`, statement
  timeout, table allow-list; prompt-injection risk.
- **Build:** `rag/schema_context.md` (tables, columns, example values, join paths,
  business definitions like "fast charger ⇒ DC or ≥ 22 kW"). `rag/examples.jsonl` — ~15
  question→SQL pairs. `rag/pipeline.py`: embed schema chunks + examples → retrieve
  relevant tables/columns/examples → LLM generates SQL → validate (parses, only
  allow-listed tables, is a SELECT) → execute on a read-only login → LLM writes a
  German-language answer citing the numbers.
  - _Pick the LLM/API deliberately here — review current model options and pricing before
    committing._
- **Deliverable:** a CLI that answers 5 sample questions correctly.
- **Done when:** the 5 questions produce correct SQL and correct numbers; a "drop table" /
  "ignore instructions" prompt is safely refused.
- **Stretch:** show the generated SQL to the user for confirmation before executing
  (human-in-the-loop).

### Week 12 — RAG II: evaluation + project wrap

- **Concepts:** eval-driven development; execution accuracy (does the query return the
  right answer?) vs exact-match on SQL text; gold datasets; error analysis by failure
  class; portfolio framing; cloud cost teardown.
- **Build:** `rag/eval/gold.jsonl` — 20 questions with verified answers.
  `rag/eval/run_eval.py` — reports execution accuracy and categorises failures (schema
  linking miss / wrong aggregation / wrong filter / hallucinated column). Then: final
  `README.md` (architecture diagram, how to run from a clean checkout, "what I learned"),
  and a cost teardown — pause or delete every Azure resource, screenshot the final bill.
- **Deliverable:** eval report + finished repo README + architecture diagram.
- **Done when:** you can state execution accuracy as a number and explain each failure
  class; the whole pipeline runs end-to-end from a fresh `git clone`.
- **Stretch:** schedule the ingest→load pipeline as an Azure Function or Container App on
  a monthly trigger.

---

## 8. Cost estimate

| Item | If careful | If sloppy |
|---|---|---|
| ADLS Gen2 (a few GB) | < €1 total | < €2 |
| Azure SQL serverless (paused when idle) | €5–15 total | €40+ if never paused |
| Windows VM for Power BI (stopped between sessions) | ~€3 | €30+ if left running |
| LLM API tokens (Weeks 11–12) | €2–5 | €10 |
| **Total** | **~€15–25** — inside the free credit | €90+ |

Track B is €0. The cost discipline is part of the curriculum.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Power BI needs Windows | Flagged Week 0; decision forced by Week 8; three costed options |
| Scope creep in RAG | Weeks 11–12 explicitly droppable; core piece ends Week 10 |
| Azure bill surprise | Serverless + auto-pause + Week 12 teardown + Track B escape hatch |
| The dedup judgment call has no "right" answer | Treated as a documented DQ rule with written rationale, not a blocker |
| Getting stuck for a whole week | Every week has a self-checkable "Done when"; bring blockers to the teacher |
| BNetzA changes the file format | Raw zone is date-partitioned and immutable; re-ingest doesn't break history |

---

## 10. First move (Week 1)

1. Set up the repo, `pyproject.toml`, `.gitignore`, virtualenv.
2. Download the BNetzA CSV once, by hand, put it somewhere local.
3. Start `docs/data_profile.md`. Open the file in a hex viewer and find the BOM. Open it
   in a text editor and find the 10 junk rows. Load it with Polars (figure out the
   separator, encoding, and skip-rows from what you observed).
4. Come back with: the column-by-column data dictionary v0, and any anomaly numbers you
   could not reproduce.

Then show the Week 1 profiling output for review before touching Azure.
