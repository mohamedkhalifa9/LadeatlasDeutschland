"""
Week 1 profiling — BNetzA Ladesäulenregister.

Reads the raw CSV, fixes the locale-specific types (German decimal commas,
DD.MM.YYYY dates), profiles every column, and reproduces the anomalies
documented in docs/data_profile.md against the real numbers.
"""

import polars as pl
from pathlib import Path

# Show full tables in the terminal instead of truncating wide/tall output.
pl.Config.set_tbl_rows(-1)
pl.Config.set_tbl_cols(-1)


# --- Load -------------------------------------------------------------
# 10 junk/preamble rows before the real header; ';' delimiter (German CSV
# convention, since ',' is the decimal separator); schema inference off so
# every column comes in as a plain string until we cast the ones we need.
file_path = Path(__file__).parent.parent / "data" / "raw" / "Ladesaeulenregister_BNetzA_2026-09-01.csv"
print(file_path)

df = pl.read_csv(
    file_path,
    separator=";",
    skip_rows=10,
    infer_schema=False,
)

print(df.columns)
print(df.shape)


# --- Type cleanup -------------------------------------------------------
# Coordinates and power rating use German decimal commas ("48,442398"),
# read in as plain strings. Convert to floats before any numeric comparison.
decimal_comma_cols = ["Breitengrad", "Längengrad", "Nennleistung Ladeeinrichtung [kW]"]
df = df.with_columns(
    pl.col(decimal_comma_cols)
    .str.strip_chars()
    .str.replace(",", ".", literal=True)
    .cast(pl.Float64)
)

# Commissioning date is "DD.MM.YYYY" as a string; parse it so we can filter by year.
df = df.with_columns(
    pl.col("Inbetriebnahmedatum").str.to_date("%d.%m.%Y")
)


# --- Column profile: null rate + cardinality per column ------------------
summary = pl.DataFrame({
    "column": df.columns,
    "n_unique": df.select(pl.all().n_unique()).row(0),
    "nulls": df.null_count().row(0),
})
print(summary)


# --- Anomaly checks, reproducing the numbers in docs/data_profile.md -----

# Status: two values exist; "In Wartung" stations may need excluding later.
print(df["Status"].unique())

# NRW station count.
print(df.filter(pl.col("Bundesland") == "Nordrhein-Westfalen").height)

# Total connectors: sum of non-null Steckertypen values across all 6 slots
# (the wide-format repeated group that Week 4's unpivot will turn into rows).
connector_cols = [f"Steckertypen{i}" for i in range(1, 7)]
total_connectors = sum(df[c].is_not_null().sum() for c in connector_cols)
print(total_connectors)

# Coordinates outside Germany's bounding box: likely corrupted single values,
# not stations genuinely located abroad (see docs/data_profile.md).
outside = df.filter(
    ~pl.col("Breitengrad").is_between(47.27, 55.06)
    | ~pl.col("Längengrad").is_between(5.87, 15.04)
)
print(outside.height)
print(outside.select(
    "Betreiber", "Ort", "Bundesland",
    "Breitengrad", "Längengrad", "Ladeeinrichtungs-ID",
    "Straße", "Hausnummer", "Postleitzahl",
))
print(outside.is_duplicated())  # confirms these are distinct records, not dupes

# Stations rated above 1,000 kW.
high_power = df.filter(pl.col("Nennleistung Ladeeinrichtung [kW]") > 1000)
print(high_power.height)
print(high_power.select("Betreiber", "Ort", "Nennleistung Ladeeinrichtung [kW]"))

# Commissioned before 2010.
before_2010 = df.filter(pl.col("Inbetriebnahmedatum").dt.year() < 2010)
print(before_2010.height)

# Rows sharing the same lat/lon/operator: group, then count the "excess"
# rows beyond one-per-group (see docs/data_profile.md for the definition).
keys = ["Breitengrad", "Längengrad", "Betreiber"]
group_sizes = df.group_by(keys).len()
shared_groups = group_sizes.filter(pl.col("len") > 1)
print(shared_groups.height)          # number of shared groups
print(shared_groups["len"].sum())    # total rows across those groups
