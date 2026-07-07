# Postgres Demo

This demo branch shows the first five profiling features against Postgres:

- case convention and case-collision risk
- whitespace and format-pattern profile
- normalized join compatibility
- inferred foreign-key relationships
- table growth and freshness profile

## Seed Local Postgres

Create a local database named `data_profiling_demo`, then run:

```powershell
python demo/seed_postgres.py --database-url postgresql+psycopg://USER:PASSWORD@localhost:5432/data_profiling_demo
```

The seed creates:

- small tables: `customers`, `orders`
- scale tables: `customers_scale` with 100k rows, `orders_scale` with 250k rows

## Small Feature Demo

```powershell
python -m db_profiler profile `
  --database-url postgresql+psycopg://USER:PASSWORD@localhost:5432/data_profiling_demo `
  --schema public `
  --config config/demo.postgres.yml `
  --output output/demo_profile.json
```

Open `output/demo_profile.json` and show:

- `tables.customers.custom_profiles.case_profile`
- `tables.customers.custom_profiles.format_profile`
- `relationships.normalized_join_candidates`
- `relationships.inferred_candidates`
- `tables.customers.growth_freshness_profile`

## Scale Demo

```powershell
python -m db_profiler profile `
  --database-url postgresql+psycopg://USER:PASSWORD@localhost:5432/data_profiling_demo `
  --schema public `
  --config config/demo.postgres.scale.yml `
  --output output/demo_profile_large.json
```

In `output/demo_profile_large.json`, show:

- `source_row_count`
- `sample_count`
- `sample_row_limit`
- `load_metadata.load_duration_seconds`
- `metadata.performance.total_profile_duration_seconds`

The point of the scale demo is that the profiler gets exact database-side row counts while sampling rows for expensive pandas/YData profiling.
