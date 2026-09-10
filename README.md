# Ladeatlas Deutschland

A data engineering learning project built on the Bundesnetzagentur *Ladesäulenregister* —
Germany's register of publicly accessible EV charging infrastructure. It ingests the raw
register into cloud storage, models it as a Kimball star schema, adds a documented
data-quality and governance layer, and serves the result through a Power BI report and a
text-to-SQL (RAG) interface.

Full plan, week by week: [docs/project-spec.md](docs/project-spec.md).

## Status

**Week 1 — data profiling.** Understanding the raw file before anything is built on it.

## Stack

Python 3.12 · Polars · DuckDB · Azure (ADLS Gen2, Azure SQL serverless) · Power BI

## Layout

| Path | Purpose |
|------|---------|
| `infra/` | Azure provisioning scripts (`az` CLI) + cost notes |
| `src/` | Pipeline steps: ingest → parse → unpivot → build dims/facts → load |
| `sql/ddl/` | `CREATE TABLE` statements for the star schema and DQ tables |
| `sql/analysis/` | Validation queries (the numbers Power BI must match) |
| `rag/` | Text-to-SQL pipeline, schema context, evaluation harness |
| `powerbi/` | The `.pbix` report |
| `docs/` | Spec, data profile, data dictionary, DQ rules, findings |
| `data/` | Local raw/staging/curated files — git-ignored, never committed |
