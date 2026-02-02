# Market Agent 项目指南

## 项目概述
这是一个市场分析 Agent，使用 Gemini API 生成每日市场研报。支持本地运行和 Cloud Run 部署两种模式。

## 技术栈
- Python 3.11
- Google Gemini API (google-genai) + Google Search 工具
- Google Cloud Run (容器化部署)
- Google Cloud Storage (Cloud 模式报告存储)
- Google Cloud Scheduler (定时触发，美东时间每天 5PM)

## 项目结构
```
market_agent/
├── market_agent.py    # 主程序入口
├── requirements.txt   # Python 依赖
├── Dockerfile         # 容器构建配置
├── .env              # 本地环境变量 (不上传)
├── .env.example      # 环境变量模板
├── .gitignore        # Git 忽略配置
├── .gcloudignore     # Cloud 部署忽略配置
├── reports/          # 本地报告输出目录 (不上传)
└── CLAUDE.md         # 本文件
```

## 环境变量
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| GEMINI_API_KEY | Gemini API 密钥 | (必填) |
| GCS_BUCKET | Cloud Storage bucket 名称 | market-reports-bucket |
| RUN_LOCAL | 是否本地运行模式 | false |
| LOCAL_OUTPUT_DIR | 本地报告输出目录 | ./reports |

## 运行模式

### 本地运行 (方式一：直接运行)
```bash
# 激活虚拟环境
source ~/.venv/google-ai/bin/activate

# 直接运行 (自动使用本地模式)
python market_agent.py
```
报告将保存到 `./reports/` 目录。

### 本地运行 (方式二：functions-framework)
```bash
source ~/.venv/google-ai/bin/activate

# 设置 RUN_LOCAL=true 在 .env 中
functions-framework --target=main_handler --source=market_agent.py

# 然后访问
curl http://localhost:8080
```

### Cloud 部署
```bash
# 部署到 Cloud Run (不要设置 RUN_LOCAL)
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

## Cloud 资源
- **Cloud Run 服务**: market-agent (us-central1)
- **Cloud Storage Bucket**: market-reports-bucket (公开可读)
- **Cloud Scheduler**: market-agent-daily (每天美东 5PM 触发)
- **服务账号**: my-notebooklm-bot@gen-lang-client-0051485402.iam.gserviceaccount.com

## 代码修改规范
1. API 密钥必须通过环境变量读取，禁止硬编码
2. 修改代码后需要重新部署 Cloud Run
3. 修改 prompt 后建议先本地测试再部署
4. 使用 `types.Tool(google_search=types.GoogleSearch())` 启用网络搜索
5. 本地/Cloud 模式通过 `RUN_LOCAL` 环境变量切换

## 常用命令
```bash
# === 本地测试 ===
python market_agent.py
cat reports/Market_Update_$(date +%Y-%m-%d).txt

# === Cloud 测试 ===
curl https://market-agent-oay2s5c5qa-uc.a.run.app
curl https://storage.googleapis.com/market-reports-bucket/Market_Update_$(date +%Y-%m-%d).txt

# === 运维命令 ===
gcloud scheduler jobs run market-agent-daily --location=us-central1
gcloud run services logs read market-agent --region=us-central1 --limit=50
```
