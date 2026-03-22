# Codex CLI 設定

## 安裝

Dockerfile 會依官方 Codex CLI 文件安裝 npm 套件 `@openai/codex`，並驗證：

```bash
codex --help
```

## 認證

官方支援兩種方式：

1. `CODEX_API_KEY`：適合 CI / 自動化
2. `codex login` 後的 `~/.codex/auth.json`：適合 ChatGPT 帳號登入

### 方式 A：API Key

```bash
export CODEX_API_KEY=your_codex_api_key
```

`docker-compose.yml` 會把它傳入容器。

### 方式 B：沿用 host 的 Codex 登入

先在 host 執行：

```bash
codex login
```

本專案會掛載：

```text
~/.codex:/root/.codex
```

因此容器可直接使用既有登入狀態。

## Worker 呼叫方式

`app/codex_runner.py` 使用：

```bash
codex exec --full-auto --sandbox workspace-write - < prompt.txt
```

說明：

1. `exec`：官方 non-interactive 模式
2. `--full-auto`：適合自動化流程
3. `--sandbox workspace-write`：允許在 repo workspace 內修改檔案
4. `- < prompt.txt`：從標準輸入讀取 prompt

prompt 來源為 `app/prompts/{mode}.txt`，並附上 webhook payload。
