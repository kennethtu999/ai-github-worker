# 執行流程

## 1. 事件進入

1. GitHub 發送 webhook 到 `/webhook`
2. 驗證簽章成功後，檢查 `processed_events`
3. 未處理事件轉成 job，寫入 `jobs`（`queued`）

## 2. 排程啟動 worker

1. scheduler 每 5 秒執行一次
2. 若無 `data/worker.lock`，claim 一筆 queued job
3. 更新 job 為 `running`，建立 lock，啟動 `run_job.py`

## 3. Worker 固定步驟

1. 建立 `/repos/{job_id}`
2. clone repo
3. checkout `ai/{job_id}`
4. 讀取 issue title/body 或 PR 內容，組成 prompt
5. 以 `codex exec --ask-for-approval never` 無人介入執行 Codex
6. `npm ci`
7. `npm run lint`
8. `npm test -- --watch=false`
9. `npm run build-storybook`
10. commit + push
11. 若來源是 issue，建立 PR
12. GitHub comment 回寫結果
13. 更新 DB status（done/failed）
14. 刪除 lock
15. 清理 workspace

## 4. 回寫格式

成功：

```text
✅ Job completed
Branch: ai/{job_id}
Checks: lint/test/storybook passed
```

失敗：

```text
❌ Job failed
Step: <step>
Error: <summary>
```
