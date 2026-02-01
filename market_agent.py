import os
from dotenv import load_dotenv

# 加载本地 .env 文件 (Cloud Run 会使用环境变量)
load_dotenv()

import functions_framework
from google import genai
from google.genai import types
from google.cloud import storage
import datetime

# 配置区
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "market-reports-bucket")

@functions_framework.http
def main_handler(request):
    # 1. 初始化 Gemini
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 2. 检索信息
    prompt = """
### 角色：全球宏观策略分析师 (Global Macro Strategist)

### 第一阶段：动态市场扫描 (Dynamic Discovery)
1. 检索过去 24 小时内，全球市场中波动率（Volatility）或成交量（Volume）最异常的 3 个板块。
2. 识别出当前市场情绪的"风暴眼"资产（无论是 A 股、美股、大宗商品还是加密货币）。

### 第二阶段：结构化深度分析
针对上述发现的"风暴眼"以及我的核心仓位（NVDA, GOOGL, TSLA, FCX, GLD, BTC），请按照以下逻辑进行研报输出：

#### 1. 预期差分析 (The Delta)
- 哪些信息是市场完全没料到的？（例如：某项提名超出了掉期市场的定价，或某公司的资本开支计划突变）。
- 区分"已被定价的噪音"与"未被定价的信号"。

#### 2. 跨资产连锁反应 (Cross-Asset Contagion)
- 如果发现某个资产大涨/大跌，请推演其对其他资产的冲击。
- 示例：如果 DXY（美元指数）走强，对 BTC 的流动性和 FCX 的边际成本意味着什么？

#### 3. 交易心理分析 (Positioning & Sentiment)
- 观察目前的社交媒体、期权市场（Put/Call Ratio）和投行研报，判断当前是"一致性预期"还是"分歧点"。
- 顶级交易员提醒：当所有人都在看多时，风险通常在积累。

### 第三阶段：研报输出要求
# 每日交易者逻辑更新 [日期]

## 📊 今日市场焦点 (Market Heatmap)
[列出 AI 自动发现的 3 个最值得关注的异动点，并说明理由]

## 🔍 核心资产增量跟踪 (Core Assets Check)
- **AI/平台 (NVDA/GOOGL/...)**: [仅写增量，不写废话]
- **宏观/避险 (GLD/BTC/Fed/...)**: [分析流动性变化]
- **实物 (FCX/...)**: [分析供需逻辑]

## ⚡ 交易行动/风险点 (Actionable Insights)
- **多头/空头假设修正**: [例如：由于 Warsh 提名，建议将 BTC 回调买入位下调 X%]
- **待观察指标 (KPIs)**: [明天最需要关注的具体数据点]

## 💡 NotebookLM 补充建议
[建议将哪些具体数据点作为新 Source 录入，以修正原有的 2026 估值模型]
""".replace("[日期]", str(datetime.date.today()))

    # 启用 Google Search 工具获取实时数据
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )
    report_md = response.text

    # 3. 上传到 Cloud Storage (覆盖同名文件)
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)

    filename = f"Market_Update_{datetime.date.today()}.txt"
    blob = bucket.blob(filename)
    blob.upload_from_string(report_md, content_type='text/plain; charset=utf-8')

    # 生成公开访问链接
    public_url = f"https://storage.googleapis.com/{GCS_BUCKET}/{filename}"

    return f"Success: {filename} uploaded to {public_url}", 200
