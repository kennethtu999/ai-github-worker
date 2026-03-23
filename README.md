# Docker AI MVP（單容器）

以單一容器完成 GitHub webhook -> SQLite queue -> Codex 自動處理 issue -> 發出 PR 的最小可行流程。

## 功能摘要

1. 支援 webhook：issues（opened/reopened/labeled）、pull_request（opened）
2. 使用 SQLite（`data/queue.db`）作為唯一 queue
3. scheduler 每 5 秒 claim 一筆 job，透過 `data/worker.lock` 保證單工 worker
4. issue webhook 進來後，worker 會以 issue title/body 驅動 Codex 無人介入執行，成功後自動 push branch 並發 PR
5. 每次 `codex exec` 的輸出都會保留在 `data/codex_logs/`（可用 `CODEX_LOGS_DIR` 覆寫）
6. 可在 issue 或 PR 內文加入 `/model <model_name>` 指定本次 Codex 模型

## Webhook 與 Clone

1. webhook 會帶入 `repository` 資訊
2. 目前 worker 至少會使用 `repository.full_name`
3. clone 採 HTTPS + `GITHUB_TOKEN`（PAT）
4. PAT 需具備 repo 讀寫權限（至少要能 clone / push / 建立 PR / issue comment）

## 快速啟動（Podman）

```bash
cp local.env.example local.env
# 編輯 local.env
./create.sh
curl http://localhost:8080/healthz
```

若你已在 host 上完成 `codex login`，容器也可透過掛載的 `~/.codex` 直接沿用登入狀態。

`local.env` 不會被提交，適合放 token、webhook secret、`CODEX_API_KEY` 與本機路徑。

若要保留每次 Codex 執行記錄，可設定 `CODEX_LOGS_DIR`。預設會寫到 `data/codex_logs`，檔名格式為 `{job_id}-{utc_timestamp}.log`。

若要指定單次 job 的模型，可在 issue 或 PR 內文任一行加入：

```text
/model gpt-5.3-codex
```

worker 會在執行時套用 `codex exec --model <model_name>`。

## 常用指令

```bash
./create.sh
./stop.sh
./destroy.sh
```

1. `create.sh`：build image，建立或啟動 container
2. `stop.sh`：停止 container
3. `destroy.sh`：停止並刪除 container

## 一鍵 Dry-Run 驗證（推薦）

```bash
python scripts/e2e_dry_run_check.py \
  --secret "$GITHUB_WEBHOOK_SECRET" \
  --repo your-org/your-repo \
  --db data/queue.db \
  --timeout 30
```

成功條件：

1. webhook 回傳 queued 並產生 `job_id`
2. job 在 timeout 內轉為 `done`
3. 腳本輸出 JSON，且 exit code 為 0

## GitHub Webhook 設定

1. URL：`http://<your-host>:8080/webhook`
2. Content type：`application/json`
3. Secret：`GITHUB_WEBHOOK_SECRET`
4. Events：Issues、Pull requests

## 驗收目標（MVP）

1. GitHub Issue -> webhook -> SQLite
2. scheduler 啟動 worker
3. worker 讀取 issue 內容並 clone Angular repo
4. Codex 在無人介入下完成修改
5. lint/test/storybook 成功
6. push `ai/{job_id}` 並建立 PR
7. GitHub comment 回寫結果
8. 全程只用一個容器執行（目前以 Podman 啟動）

## 文件

1. `docs/architecture.md`
2. `docs/git-access.md`
3. `docs/codex-setup.md`
4. `docs/sqlite-schema.md`
5. `docs/run-flow.md`

## 其他

1. `docker-compose.yml` 仍保留作為參考配置
2. 正式啟動方式以 `create.sh` + Podman 為主
