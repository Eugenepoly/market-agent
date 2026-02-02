# Market Agent 项目指南

## 项目概述
这是一个多 Agent 协作的市场分析系统，支持：
- 每日市场研报生成
- 深度分析（支持指定主题或自动提取）
- 社交媒体推文草稿生成（需人工审核）
- **大V社交监控**（X/Twitter、Truth Social）

支持本地运行和 Cloud Run 部署两种模式。

## 技术栈
- Python 3.11
- Google Gemini API (google-genai) + Google Search 工具
- Google Cloud Run (容器化部署)
- Google Cloud Storage (Cloud 模式报告存储)
- Google Cloud Scheduler (定时触发，美东时间每天 5PM)
- Flask (HTTP 路由)

## 项目结构
```
market_agent/
├── main.py                    # 统一入口 (HTTP + CLI)
├── config.py                  # 配置管理
├── watchlist.py               # 监控列表配置 (大V、持仓、关键词)
├── core/
│   ├── __init__.py
│   ├── orchestrator.py        # 工作流编排器
│   ├── state.py               # 状态管理
│   └── base_agent.py          # Agent 基类
├── agents/
│   ├── __init__.py
│   ├── report_agent.py        # 报告生成 Agent
│   ├── deep_analysis_agent.py # 深度分析 Agent
│   ├── social_agent.py        # 社交发布 Agent
│   └── monitor_agent.py       # VIP 监控 Agent
├── collectors/                # 数据采集层
│   ├── __init__.py
│   ├── base_collector.py      # 采集器基类
│   ├── social/                # 社交媒体采集
│   │   ├── x_collector.py     # X/Twitter (Nitter + Gemini)
│   │   └── truth_collector.py # Truth Social
│   ├── market/                # 市场数据采集
│   │   ├── finviz_collector.py   # 机构持仓、内部人交易
│   │   └── yahoo_collector.py    # 期权数据、Put/Call
│   ├── crypto/                # 加密资金流
│   │   └── coinglass_collector.py # 恐惧贪婪、资金费率、清算
│   └── news/                  # [TODO] 新闻采集
├── workflows/
│   ├── __init__.py
│   └── daily_workflow.py      # 每日工作流定义
├── storage/
│   ├── __init__.py
│   └── storage.py             # 存储抽象层
├── prompts/
│   ├── __init__.py
│   ├── report_prompt.py       # 报告提示词
│   ├── deep_analysis_prompt.py
│   └── social_prompt.py
├── data/                      # 采集数据存储 (不上传)
│   ├── social_posts/          # 原始帖子 (保留3小时)
│   ├── monitor/               # VIP监控分析报告
│   └── fund_flows/            # 资金流向数据
├── requirements.txt
├── Dockerfile
├── .env                       # 本地环境变量 (不上传)
├── .env.example               # 环境变量模板
├── .gitignore
├── .gcloudignore
├── reports/                   # 本地报告输出目录 (不上传)
├── market_agent.py            # [已废弃] 旧版入口
└── CLAUDE.md                  # 本文件
```

## Agent 说明

| Agent | 功能 | 输入 | 输出 | 需审核 |
|-------|------|------|------|--------|
| ReportAgent | 生成每日市场研报 | 无 | 市场报告 | 否 |
| DeepAnalysisAgent | 深度分析 | 报告 + 主题(可选) | 深度分析 | 否 |
| SocialAgent | 生成推文草稿 | 报告/分析 | X 推文草稿 | **是** |
| MonitorAgent | VIP 社交监控 | 无 | 监控报告 + 告警 | 否 |
| FundFlowAgent | 资金流向分析 | 无 | 机构/期权/加密资金流分析 | 否 |

## 环境变量
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| GEMINI_API_KEY | Gemini API 密钥 | (必填) |
| GEMINI_MODEL | Gemini 模型名称 | gemini-2.0-flash |
| GCS_BUCKET | Cloud Storage bucket 名称 | market-reports-bucket |
| RUN_LOCAL | 是否本地运行模式 | false |
| LOCAL_OUTPUT_DIR | 本地报告输出目录 | ./reports |
| WORKFLOW_STATE_DIR | 工作流状态存储目录 | ./.workflow_state |
| PENDING_APPROVAL_DIR | 待审核草稿目录 | ./pending_social_content |
| APPROVED_DRAFTS_DIR | 已审核草稿目录 | ./approved_social_content |

## 运行模式

### 本地 CLI 运行

```bash
# 激活虚拟环境
source ~/.venv/google-ai/bin/activate

# === 工作流命令 ===

# 运行每日工作流（完整流水线）
python main.py workflow daily

# 跳过深度分析
python main.py workflow daily --skip-analysis

# 指定深度分析主题
python main.py workflow daily --topic "BTC与美元指数关系"

# 查看工作流状态
python main.py workflow status <workflow_id>

# 审核通过
python main.py workflow approve <workflow_id>

# 审核拒绝
python main.py workflow reject <workflow_id> --reason "需要修改"

# 列出所有工作流
python main.py workflow list

# === 单独运行 Agent ===

# 只运行报告 Agent
python main.py agent report

# 运行深度分析 Agent（需要先有报告）
python main.py agent analysis --report-file ./reports/Market_Update_2024-01-01.txt
python main.py agent analysis --report-file ./reports/xxx.txt --topic "NVDA估值"

# 运行社交 Agent（需要报告，可选分析）
python main.py agent social --report-file ./reports/xxx.txt
python main.py agent social --report-file ./reports/xxx.txt --analysis-file ./reports/analysis/xxx.txt

# === VIP 监控 ===

# 快速检查（只采集+关键词检测，不调用LLM）
python main.py agent monitor --quick

# 完整分析（采集 + LLM 分析市场影响）
python main.py agent monitor

# === 资金流向 ===

# 快速检查（期权P/C、恐惧贪婪指数、资金费率）
python main.py agent fundflow --quick

# 完整分析（机构持仓、期权、加密资金流）
python main.py agent fundflow
```

### 本地 HTTP 运行 (functions-framework)
```bash
source ~/.venv/google-ai/bin/activate

# 启动服务
functions-framework --target=main_handler --source=main.py --port=8080

# 测试 API
curl http://localhost:8080                           # 健康检查 / 兼容旧版
curl -X POST http://localhost:8080/workflow/daily    # 启动每日工作流
curl http://localhost:8080/workflow/{id}/status      # 查询状态
curl -X POST http://localhost:8080/workflow/{id}/approve  # 审核通过
curl -X POST http://localhost:8080/workflow/{id}/reject   # 审核拒绝
```

### Cloud 部署
```bash
# 部署到 Cloud Run
gcloud run deploy market-agent \
  --source=. \
  --region=us-central1 \
  --allow-unauthenticated \
  --timeout=300 \
  --service-account=my-notebooklm-bot@gen-lang-client-0051485402.iam.gserviceaccount.com

# 更新环境变量
gcloud run services update market-agent \
  --region=us-central1 \
  --set-env-vars="GEMINI_API_KEY=xxx,GCS_BUCKET=market-reports-bucket"
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 健康检查 / 兼容旧版（只运行报告） |
| `/workflow/daily` | POST | 启动每日工作流 |
| `/workflow/{id}/status` | GET | 查询工作流状态 |
| `/workflow/{id}/approve` | POST | 审核通过 |
| `/workflow/{id}/reject` | POST | 审核拒绝 |
| `/workflows` | GET | 列出所有工作流 |
| `/agent/report` | POST | 单独运行报告 Agent |
| `/agent/deep-analysis` | POST | 单独运行深度分析 Agent |
| `/agent/social` | POST | 单独运行社交 Agent |
| `/agent/monitor` | POST | 运行 VIP 监控 Agent |
| `/agent/fundflow` | POST | 运行资金流向 Agent |

### 请求示例

```bash
# 启动每日工作流（带选项）
curl -X POST http://localhost:8080/workflow/daily \
  -H "Content-Type: application/json" \
  -d '{"skip_analysis": false, "topic": "BTC走势分析"}'

# 单独运行深度分析
curl -X POST http://localhost:8080/agent/deep-analysis \
  -H "Content-Type: application/json" \
  -d '{"report": "报告内容...", "topic": "NVDA"}'

# 拒绝并说明原因
curl -X POST http://localhost:8080/workflow/{id}/reject \
  -H "Content-Type: application/json" \
  -d '{"reason": "语气需要调整"}'
```

## 工作流说明

### 每日工作流 (daily)
```
1. ReportAgent.run() → 生成市场报告 → 保存到 Storage
2. [可选] DeepAnalysisAgent.run() → 深度分析 → 保存
3. SocialAgent.run() → 生成推文草稿
4. 暂停，等待审核 (status: waiting_approval)
5. 用户审核 → approve/reject
6. 如果通过 → 保存推文草稿到 approved_social_content 目录供用户复制
```

### 审核流程
- **本地模式**: 生成草稿后显示在终端，同时保存到 `pending_social_content/` 目录
- **Cloud 模式**: 草稿保存到 GCS pending 目录，调用 `/workflow/{id}/approve` 审核

## 监控配置 (watchlist.py)

### 大V监控列表
```python
VIP_ACCOUNTS = {
    "x": [
        {"handle": "elonmusk", "name": "Elon Musk", "category": "tech_leader"},
        {"handle": "realDonaldTrump", "name": "Donald Trump", "category": "political"},
        {"handle": "cz_binance", "name": "CZ", "category": "crypto"},
        # ... 添加更多
    ],
    "truth_social": [
        {"handle": "realDonaldTrump", "name": "Donald Trump", "category": "political"},
    ],
}
```

### 持仓监控列表
```python
WATCHLIST = {
    "stocks": [
        {"symbol": "NVDA", "name": "NVIDIA", "category": "ai_chip"},
        {"symbol": "GOOGL", "name": "Alphabet", "category": "ai_platform"},
        # ...
    ],
    "crypto": [
        {"symbol": "BTC", "name": "Bitcoin", "category": "crypto_major"},
        {"symbol": "ETH", "name": "Ethereum", "category": "crypto_major"},
    ],
}
```

### 告警关键词
```python
ALERT_KEYWORDS = {
    "market_moving": ["fed", "fomc", "rate cut", "inflation", ...],
    "crypto": ["bitcoin", "btc", "ethereum", "sec", "etf", ...],
    "stocks": ["earnings", "guidance", "buyback", ...],
}
```

### 数据保留策略
- 每小时保存一份采集数据
- 同一小时内重复运行会覆盖
- 最多保留最近 3 小时的数据，自动清理旧文件

## Cloud 资源
- **Cloud Run 服务**: market-agent (us-central1)
- **Cloud Storage Bucket**: market-reports-bucket (公开可读)
- **Cloud Scheduler**: market-agent-daily (每天美东 5PM 触发)
- **服务账号**: my-notebooklm-bot@gen-lang-client-0051485402.iam.gserviceaccount.com

## 代码修改规范
1. API 密钥必须通过环境变量读取，禁止硬编码
2. 修改代码后需要重新部署 Cloud Run
3. 修改 prompt 后建议先本地测试再部署
4. Agent 使用 `types.Tool(google_search=types.GoogleSearch())` 启用网络搜索
5. 本地/Cloud 模式通过 `RUN_LOCAL` 环境变量切换
6. 新增 Agent 需要：
   - 在 `agents/` 下创建文件，继承 `BaseAgent`
   - 在 `prompts/` 下创建对应的 prompt 模块
   - 在 `agents/__init__.py` 中导出
   - 在 `main.py` 的 `create_orchestrator()` 中注册

## 常用命令
```bash
# === 本地测试 ===
python main.py workflow daily
python main.py agent report
python main.py agent monitor --quick    # VIP 快速监控
python main.py agent monitor            # VIP 完整分析
python main.py agent fundflow --quick   # 资金流快速检查
python main.py agent fundflow           # 资金流完整分析
cat reports/Market_Update_$(date +%Y-%m-%d).txt

# === Cloud 测试 ===
curl -X POST https://market-agent-oay2s5c5qa-uc.a.run.app/workflow/daily
curl -X POST https://market-agent-oay2s5c5qa-uc.a.run.app/agent/monitor
curl https://storage.googleapis.com/market-reports-bucket/Market_Update_$(date +%Y-%m-%d).txt

# === 运维命令 ===
gcloud scheduler jobs run market-agent-daily --location=us-central1
gcloud run services logs read market-agent --region=us-central1 --limit=50
```
