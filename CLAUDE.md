# Market Agent 项目指南

## 项目概述
这是一个部署在 Google Cloud Run 上的市场分析 Agent，使用 Gemini API 生成每日市场研报，并上传到 Google Cloud Storage。

## 技术栈
- Python 3.11
- Google Gemini API (google-genai)
- Google Cloud Run (容器化部署)
- Google Cloud Storage (报告存储)
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
└── CLAUDE.md         # 本文件
```

## 环境变量
| 变量名 | 说明 |
|--------|------|
| GEMINI_API_KEY | Gemini API 密钥 |
| GCS_BUCKET | Cloud Storage bucket 名称 |

## 本地开发
```bash
# 激活虚拟环境
source ~/.venv/google-ai/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行
functions-framework --target=main_handler --source=market_agent.py
```

## 部署命令
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

## 常用测试
```bash
# 测试 Cloud Run 端点
curl https://market-agent-oay2s5c5qa-uc.a.run.app

# 查看生成的报告
curl https://storage.googleapis.com/market-reports-bucket/Market_Update_$(date +%Y-%m-%d).txt

# 手动触发 Scheduler
gcloud scheduler jobs run market-agent-daily --location=us-central1

# 查看 Cloud Run 日志
gcloud run services logs read market-agent --region=us-central1 --limit=50
```
