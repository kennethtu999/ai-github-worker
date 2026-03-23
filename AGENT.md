# AGENT.md — ai-github-worker

## 專案定位

**ai-github-worker** 是一個全自主、無人介入的 AI 工程代理人（Autonomous AI Agent），運作於單一 Docker 容器內。它持續監聽 GitHub 事件，自主理解需求、產生程式碼、通過品質關卡，並建立可審查的 Pull Request——全程不需要人工干預。

---

## 核心原則

### 1. 自主性（Autonomy）
- 代理人從接收 webhook 到建立 PR，完整閉環執行，不等待人工指令。
- 所有決策（分支命名、commit message、PR 描述）均由代理人自行產出。
- 使用 `--ask-for-approval never` 確保 Codex 執行期間不中斷等待確認。

### Git 操作流程（依序執行）

每次 job 均嚴格遵守以下四步驟：

1. **同步 base branch** — `git checkout ${DEFAULT_BASE_BRANCH} && git pull origin ${DEFAULT_BASE_BRANCH}`，確保從最新版本開始作業。
2. **建立 feature branch** — 依 GitHub 單號命名：
   - Issue job：`feature/{issue_number}`
   - PR review job：`review/pr-{pr_number}`
3. **Commit 變更** — Codex 修改並通過所有品質關卡後，`git add -A` + `git commit`，commit message 格式：
   - Issue：`feat(ai): resolve issue #{issue_number}`
   - PR：`fix(ai): address review for PR #{pr_number}`
4. **建立 Pull Request** — push branch 後透過 GitHub API 開啟 PR，base 為 `${DEFAULT_BASE_BRANCH}`，並於原 issue 回寫完成 comment。

### 2. 嚴謹性（Rigor）
- 每次程式碼變更皆須通過完整品質關卡才能 push：
  1. `npm run lint` — 靜態分析零錯誤
  2. `npm test -- --watch=false` — 單元測試全綠
  3. `npm run build-storybook` — 元件文件構建成功
- 任一關卡失敗則整個 job 標記為 `failed`，不產出 PR，並回寫錯誤摘要至 GitHub。

### 3. 可追溯性（Traceability）
- 每筆 job 有唯一 `job_id`，對應 branch `ai/{job_id}`、DB 記錄、Codex 執行 log（`data/codex_logs/`）與 worker log（`data/worker_logs/`）。
- Webhook 事件透過 `processed_events` 去重，確保冪等性。
- 全程狀態變更（`queued → running → done/failed`）皆寫入 SQLite。

### 4. 隔離性（Isolation）
- 每次 job 獨立 clone 到 `repos/{job_id}`，執行完畢後清理，互不干擾。
- `data/worker.lock` 保證同一時間只有一個 worker 在執行（serialized execution）。

---

## 系統架構快覽

```
GitHub Webhook
      │
      ▼
webhook_server.py   ← FastAPI，驗證 HMAC-SHA256 簽章
      │ 寫入
      ▼
SQLite (data/queue.db)
      │
      ▼ 每 5 秒輪詢
scheduler.py        ← claim job，建立 worker.lock，啟動 subprocess
      │
      ▼
run_job.py          ← 核心 Worker
  ├── git clone (SSH)
  ├── git checkout ${DEFAULT_BASE_BRANCH} && git pull origin ${DEFAULT_BASE_BRANCH}
  ├── git checkout -b feature/{issue_number}  (或 review/pr-{pr_number})
  ├── 組合 prompt（issue title/body 或 PR content）
  ├── codex exec --ask-for-approval never [--model <name>]
  ├── npm ci / lint / test / build-storybook
  ├── git add -A && git commit -m "feat(ai): resolve issue #{issue_number}"
  ├── git push -u origin feature/{issue_number}
  ├── 建立 PR（issue job）
  ├── GitHub comment 回寫結果
  └── 更新 DB → 移除 lock → 清理 workspace
```

---

## 執行環境

| 項目 | 值 |
|------|-----|
| 進入點 | `python /app/app/main.py` |
| Webhook 埠 | `8080`（可覆寫 `WEBHOOK_PORT`） |
| Queue 儲存 | `data/queue.db`（SQLite） |
| Branch 格式 | `feature/{issue_number}` / `review/pr-{pr_number}` |
| Base branch | `main`（可覆寫 `DEFAULT_BASE_BRANCH`） |
| Worker 排程 | 每 5 秒（可覆寫 `SCHEDULER_INTERVAL_SECONDS`） |
| Codex log | `data/codex_logs/{job_id}-{utc}.log` |

---

## 關鍵環境變數

```env
GITHUB_TOKEN              # 建立 PR 與回寫 comment
GITHUB_WEBHOOK_SECRET     # 驗證 webhook 簽章
CODEX_API_KEY             # Codex / OpenAI API key
WORKER_DRY_RUN=true       # 跳過實際 Codex 執行，用於測試
CODEX_LOGS_DIR            # 覆寫 Codex log 目錄
DEFAULT_BASE_BRANCH       # PR 的目標 branch
```

---

## Webhook 支援事件

| 事件 | Action | 行為 |
|------|--------|------|
| `issues` | `opened` / `reopened` / `labeled` | 建立 issue job，執行完後開 PR |
| `pull_request` | `opened` | 建立 PR review job |

---

## 對代理人（AI）的行為要求

當此專案以 AI agent 身份被呼叫時，應遵守下列規範：

1. **不跳過品質關卡**：lint、test、storybook 是硬性要求，不可省略或 bypass。
2. **精確的 commit message**：遵循 Conventional Commits 格式（`feat:`, `fix:`, `refactor:` 等）。
3. **最小化變動範圍**：只修改 issue/PR 明確要求的部分，不重構無關程式碼。
4. **錯誤必須回報**：任何步驟失敗，以標準格式回寫 GitHub comment，不靜默失敗。
5. **冪等操作**：重新執行相同 job 不應產生副作用（若 branch 已存在則重置）。
6. **安全第一**：不將 token、key 或 secret 寫入程式碼或 commit，不 bypass webhook 簽章驗證。

---

## 目錄結構概覽

```
app/
  main.py             ← 啟動 FastAPI + scheduler thread
  webhook_server.py   ← Webhook 接收與驗證
  scheduler.py        ← 排程與 lock 管理
  run_job.py          ← Worker 主流程
  codex_runner.py     ← Codex exec 封裝
  github_client.py    ← GitHub API（PR / comment）
  job_parser.py       ← 解析 webhook payload
  workspace.py        ← Git clone / branch 管理
  db.py               ← SQLite CRUD
  config.py           ← 環境變數集中管理
  prompts/            ← Codex prompt 模板
data/                 ← queue.db、lock、logs（runtime，不提交）
repos/                ← 暫存 clone（runtime，不提交）
docs/                 ← 架構與設定文件
scripts/              ← 開發與測試工具
```

---

## 驗收基準

一個成功的端對端執行必須滿足：

- [ ] Webhook 收到後，job 寫入 DB（`queued`）
- [ ] Scheduler 在 5 秒內 claim job（`running`）
- [ ] Codex 無人介入完成修改
- [ ] lint / test / storybook 全部通過
- [ ] `ai/{job_id}` branch 成功 push
- [ ] PR 建立並包含變更摘要
- [ ] GitHub comment 回寫 `✅ Job completed`
- [ ] DB 狀態更新為 `done`，lock 移除，workspace 清理
