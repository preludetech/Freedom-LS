# Database Strategy for xAPI Event Storage

Scale estimate: ~5k DAU x ~50 events/user = ~250k events/day = ~90M events/year.

## 1. PostgreSQL Capabilities for Event Data

PostgreSQL handles this scale comfortably. The practical concern is not write speed but data accumulation and query cost over time.

**Performance thresholds:**
- Under 100M rows: fine with proper indexing
- 100M-500M rows: requires partitioning, careful index design
- 500M+: significant tuning effort; consider dedicated analytics tooling

**Key strategies:**

- **Range partitioning by month** on timestamp. Partition pruning keeps queries fast; dropping old partitions is instant vs expensive DELETEs. Use `pg_partman` to automate creation/retention. Ref: [PostgreSQL Partitioning Docs](https://www.postgresql.org/docs/current/ddl-partitioning.html), [pg_partman](https://github.com/pgpartman/pg_partman)

- **JSONB for flexible payloads.** Promote hot fields (actor, verb, object_type) to typed columns; keep full xAPI statement in JSONB. Use GIN index with `jsonb_path_ops` (16% overhead vs 79% for default). Note: GIN does NOT accelerate `->>` extractions -- use expression B-tree indexes for those. Ref: [Indexing JSONB (Crunchy Data)](https://www.crunchydata.com/blog/indexing-jsonb-in-postgres)

- **Indexing:** B-tree on `(timestamp, actor_id, verb)` for common queries. Partial indexes for specific event types (e.g. `WHERE verb = 'completed'`). BRIN indexes are lightweight for append-only timestamp columns.

- **Archival:** Two-tier retention -- raw events for 12-24 months, pre-aggregated summaries indefinitely. Detach + dump old partitions before dropping. Ref: [When to Partition (Tiger Data)](https://www.tigerdata.com/learn/when-to-consider-postgres-partitioning)

## 2. TimescaleDB as an Extension

TimescaleDB adds automatic time-partitioning (hypertables), 10-20x compression on older chunks, continuous aggregates, and built-in retention policies -- all as a PostgreSQL extension, not a separate database.

**Value add:** Eliminates manual partition management; compression saves significant storage; continuous aggregates simplify dashboards.

**Complexity cost:** Extra extension dependency; Django integration via community [django-timescaledb](https://pypi.org/project/django-timescaledb/) library (thin, less maintained); hypertables cannot have foreign keys TO them and require time column in unique constraints; hosting provider must support the extension.

**Verdict:** Not needed at launch. Can be added later without schema changes (converting partitioned table to hypertable is straightforward). Worth adding when raw storage exceeds ~100GB or continuous aggregates become valuable. Ref: [TimescaleDB with Django](https://medium.com/pyzilla/mastering-time-series-data-in-django-with-timescaledb-4f233d856504)

## 3. When PostgreSQL Is NOT Enough

**Warning signs:** aggregation queries over 100M+ rows take 10-30s; autovacuum can't keep pace with inserts; analytics queries degrade transactional workload.

**Alternatives:**

| Solution | Best For | Complexity |
|---|---|---|
| **ClickHouse** | Billions of rows, sub-second aggregations, 10-100x faster than PG for analytics | High -- separate DB, no Django ORM, no ACID, needs data pipeline |
| **DuckDB** | Embedded analytics on exported Parquet files | Low -- no server, but separate from live data |
| **BigQuery/Redshift** | Cloud-native analytics warehouse | Medium -- managed but vendor lock-in |

ClickHouse becomes meaningfully faster at ~1M+ rows for analytical queries and is 10-100x faster at 100M+. But it adds a second database, a data pipeline, and has no Django ORM support.

**FLS threshold:** At ~90M events/year, PostgreSQL is comfortable for 3-5+ years. Revisit at 500M+ total events or if real-time dashboards on large windows become a requirement. Ref: [ClickHouse vs PostgreSQL (PostHog)](https://posthog.com/blog/clickhouse-vs-postgres), [ClickHouse vs PG 2026 (Tinybird)](https://www.tinybird.co/blog/clickhouse-vs-postgresql-with-extensions)

## 4. Django ORM Considerations

**Partitioned tables:** Django ORM reads/writes work transparently against the parent table. Schema management is the issue -- use `django-postgres-extra` (has `pgpartition` management command) or `RunSQL` migrations for partition DDL. Composite primary keys (required by PG for partitioned tables) need `django-postgres-extra` or manual handling. Ref: [django-postgres-extra partitioning](https://django-postgres-extra.readthedocs.io/en/master/table_partitioning.html), [PG Partitioning in Django (pganalyze)](https://pganalyze.com/blog/postgresql-partitioning-django)

**Bulk writes:** Use `bulk_create(batch_size=1000)` -- reduces round-trips dramatically. Bypasses `save()` and signals, which is fine for event logging.

**Async writes -- recommended pattern:**
1. Accept event via API endpoint, validate, push to Celery task
2. Celery worker buffers events, calls `bulk_create()` every few seconds or every N events
3. This keeps HTTP responses fast and DB writes efficient

**Simpler alternative** (no Celery): middleware that collects events during request and `bulk_create()`s at end of request cycle. Sufficient at this scale.

**JSONB queries** work well via Django's `JSONField`: `filter(statement__contains={...})` uses GIN index; `filter(statement__result__score__gt=0.8)` works for key lookups.

**Always filter by timestamp** in queries to enable partition pruning.

## 5. Recommendation for FLS

**Use plain PostgreSQL 17 with monthly range partitioning.**

1. **No new infrastructure** -- same database as the rest of FLS
2. **Schema:** typed columns for hot fields (timestamp, actor, verb, object_type, object_id, course_id) + JSONB for full statement
3. **Partitioning:** monthly by timestamp, managed by `pg_partman` or `django-postgres-extra`
4. **Indexing:** B-tree composite on common query patterns, GIN with `jsonb_path_ops` on JSONB, partial indexes as needed
5. **Writes:** async via Celery + `bulk_create()`, or simpler middleware-based buffering
6. **Retention:** raw events 12-24 months, pre-aggregated summaries indefinitely, drop old partitions
7. **Future path:** add TimescaleDB for compression/continuous aggregates if storage exceeds ~100GB; consider ClickHouse only if user base grows 100x

This approach handles ~90M events/year with no new dependencies beyond `pg_partman` or `django-postgres-extra`, and provides a clear upgrade path if scale demands change.
