# SQLite Schema

資料庫路徑：`data/queue.db`

```sql
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  event_id TEXT,
  repo TEXT,
  issue_number INTEGER,
  pr_number INTEGER,
  task_type TEXT,
  mode TEXT,
  status TEXT,
  payload_json TEXT,
  created_at TEXT,
  started_at TEXT,
  finished_at TEXT,
  result_json TEXT
);

CREATE TABLE processed_events (
  event_id TEXT PRIMARY KEY,
  received_at TEXT
);
```

## Job 狀態

- `queued`
- `running`
- `done`
- `failed`
