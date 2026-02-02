"""Prompt template for the Deep Analysis Agent."""

import datetime
from typing import Optional


def get_deep_analysis_prompt(report: str, topic: Optional[str] = None) -> str:
    """Get the deep analysis prompt.

    Args:
        report: The market report from ReportAgent.
        topic: Optional specific topic to analyze. If None, auto-extract from report.

    Returns:
        The formatted prompt string.
    """
    date = datetime.date.today()

    if topic:
        topic_instruction = f"""
### 指定分析主题
用户指定了以下主题进行深度分析：
**{topic}**

请围绕这个主题进行全面深入的分析。
"""
    else:
        topic_instruction = """
### 自动识别分析主题
请从上述市场报告中识别出最值得深入分析的 1-2 个点，选择标准：
1. 市场预期差最大的事件或资产
2. 可能引发跨资产连锁反应的催化剂
3. 当前市场尚未充分定价的风险或机会
"""

    return f"""
### 角色：深度研究分析师 (Deep Research Analyst)

### 输入：今日市场报告
```
{report}
```

{topic_instruction}

### 分析框架

#### 1. 背景与上下文 (Context)
- 这个主题/事件的历史背景是什么？
- 类似情况在历史上如何演绎？
- 当前与历史情境的关键差异是什么？

#### 2. 多空博弈分析 (Bull vs Bear)
**多头论点 (Bull Case)**：
- 支持上涨的 3 个核心论据
- 潜在催化剂和时间节点

**空头论点 (Bear Case)**：
- 支持下跌的 3 个核心论据
- 主要风险和触发条件

**概率评估**：
- 多头情景概率: X%
- 空头情景概率: Y%
- 判断依据

#### 3. 关键指标监控 (Key Metrics)
列出未来 1-2 周需要重点监控的 5 个具体指标：
- 指标名称
- 当前值
- 阈值/预警线
- 数据来源

#### 4. 交易策略建议 (Trade Ideas)
基于以上分析，提供具体可操作的交易建议：
- 方向 (做多/做空/观望)
- 入场条件
- 目标价位
- 止损位置
- 仓位建议

#### 5. 风险提示 (Risk Disclosure)
- 该分析可能出错的 3 个原因
- 黑天鹅事件风险

### 输出格式
# 深度分析报告 [{date}]

## 分析主题
[主题名称]

## 核心观点 (一句话总结)
[...]

## 详细分析
[按上述框架展开]

## 行动建议
[具体操作建议]
""".format(date=date)
