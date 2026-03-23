# 架構說明（MVP）

本系統以單一 Docker 容器提供三個核心能力：

1. Webhook Server：接收 GitHub 事件並寫入 SQLite queue。
2. Scheduler：每 5 秒輪詢 queue，若無 lock 則啟動一個 worker。
3. Worker：收到 issue job 後，以 issue title/body 啟動 Codex，在無人介入下完成修改、檢查、push 與 PR 建立。

## 元件關係

- `app/webhook_server.py`
  - 驗證 `X-Hub-Signature-256`
  - 支援 `issues(opened/reopened/labeled)`、`pull_request(opened)`
  - 使用 `processed_events` 去重
  - 寫入 `jobs`（`status=queued`）

- `app/scheduler.py`
  - 檢查 `data/worker.lock`
  - claim 一筆 queued job，更新為 running
  - subprocess 啟動 `app/run_job.py`

- `app/run_job.py`
  - 建立 `repos/{job_id}` workspace
  - `git clone git@github.com:org/repo.git`
  - 建分支 `ai/{job_id}`
  - 以 issue / PR 內容組合 prompt
  - 呼叫 `codex exec --ask-for-approval never --sandbox workspace-write -`
  - 執行 npm 檢查與 build
  - commit/push，issue job 必須成功建立 PR
  - 回寫 GitHub comment / PR
  - 更新 DB 狀態、移除 lock、清理 workspace
