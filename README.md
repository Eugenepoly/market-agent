# Market Agent

A multi-agent market analysis system powered by Google Gemini. Automatically generates daily market reports, monitors VIP social media accounts, tracks fund flows, and analyzes on-chain data.

## Features

- **Daily Market Reports** - AI-generated analysis of your portfolio (NVDA, GOOGL, TSLA, GLD, BTC, FCX)
- **VIP Social Monitoring** - Track key influencers on X/Twitter and Truth Social (Elon Musk, Trump, etc.)
- **Fund Flow Analysis** - Options data (Put/Call ratios), institutional holdings, insider trading
- **On-chain Monitoring** - Whale transactions, exchange reserves, funding rates
- **Email Delivery** - HTML-formatted reports sent to your inbox
- **Social Draft Generation** - Auto-generate X/Twitter posts (with human approval)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Daily Workflow                          │
├─────────────────────────────────────────────────────────────┤
│  1. DataCollectionAgent  →  Collect VIP/Fund/Onchain data  │
│  2. ReportAgent          →  Generate market report + Email  │
│  3. DeepAnalysisAgent    →  Deep dive analysis (optional)   │
│  4. SocialAgent          →  Generate tweet draft            │
│  5. Human Approval       →  Review and approve/reject       │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key
- Gmail account (for email delivery)

### Installation

```bash
# Clone the repository
git clone https://github.com/Eugenepoly/market-agent.git
cd market-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
RUN_LOCAL=true

# Email (optional)
EMAIL_ENABLED=true
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_RECIPIENTS=recipient1@gmail.com,recipient2@gmail.com
```

### Usage

```bash
# Run full daily workflow
python main.py workflow daily

# Generate report only
python main.py agent report

# Send latest report via email
python main.py email send

# Quick fund flow check
python main.py agent fundflow --quick

# Monitor VIP social accounts
python main.py agent monitor --quick
```

## Cloud Deployment

Deploy to Google Cloud Run:

```bash
gcloud run deploy market-agent \
  --source=. \
  --region=us-central1 \
  --allow-unauthenticated \
  --timeout=300
```

Set up Cloud Scheduler for daily runs:

```bash
gcloud scheduler jobs create http market-agent-daily \
  --schedule="0 8 * * *" \
  --time-zone="America/New_York" \
  --uri="https://YOUR_SERVICE_URL/workflow/daily" \
  --http-method=POST
```

## Data Sources

| Source | Data |
|--------|------|
| Yahoo Finance | Options, Put/Call ratios, price data |
| Finviz | Institutional holdings, insider trading |
| Coinglass | Fear & Greed index, funding rates |
| Nitter | X/Twitter posts (via proxy) |
| Truth Social | Political commentary |

## Project Structure

```
market_agent/
├── main.py              # CLI & HTTP entry point
├── agents/              # AI agents (Report, Analysis, Social, etc.)
├── collectors/          # Data collectors (Yahoo, Finviz, Coinglass)
├── prompts/             # LLM prompt templates
├── workflows/           # Workflow definitions
├── services/            # Email service
└── CLAUDE.md            # Detailed internal documentation
```

## License

MIT

## Author

Eugene Cao
