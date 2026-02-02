"""Watchlist configuration for monitoring."""

# =============================================================================
# 大V监控列表 (VIP Accounts)
# =============================================================================

VIP_ACCOUNTS = {
    "x": [
        {"handle": "elonmusk", "name": "Elon Musk", "category": "tech_leader"},
        {"handle": "realDonaldTrump", "name": "Donald Trump", "category": "political"},
        {"handle": "cabortz", "name": "CZ (Binance)", "category": "crypto"},
        {"handle": "VitalikButerin", "name": "Vitalik Buterin", "category": "crypto"},
        {"handle": "michael_saylor", "name": "Michael Saylor", "category": "crypto"},
        {"handle": "CathieDWood", "name": "Cathie Wood", "category": "investor"},
        {"handle": "jimcramer", "name": "Jim Cramer", "category": "media"},
    ],
    "truth_social": [
        {"handle": "realDonaldTrump", "name": "Donald Trump", "category": "political"},
    ],
}

# =============================================================================
# 持仓监控列表 (Portfolio Watchlist)
# =============================================================================

WATCHLIST = {
    "stocks": [
        {"symbol": "NVDA", "name": "NVIDIA", "category": "ai_chip"},
        {"symbol": "GOOGL", "name": "Alphabet", "category": "ai_platform"},
        {"symbol": "TSLA", "name": "Tesla", "category": "ev_energy"},
        {"symbol": "FCX", "name": "Freeport-McMoRan", "category": "commodities"},
        {"symbol": "GLD", "name": "SPDR Gold Trust", "category": "safe_haven"},
    ],
    "crypto": [
        {"symbol": "BTC", "name": "Bitcoin", "category": "crypto_major"},
        {"symbol": "ETH", "name": "Ethereum", "category": "crypto_major"},
    ],
    "indices": [
        {"symbol": "SPY", "name": "S&P 500 ETF", "category": "index"},
        {"symbol": "QQQ", "name": "Nasdaq 100 ETF", "category": "index"},
        {"symbol": "DXY", "name": "US Dollar Index", "category": "currency"},
        {"symbol": "VIX", "name": "Volatility Index", "category": "volatility"},
    ],
}

# =============================================================================
# 关键词监控 (Keywords for Alerts)
# =============================================================================

ALERT_KEYWORDS = {
    "market_moving": [
        "fed", "fomc", "rate cut", "rate hike", "inflation",
        "recession", "crash", "rally", "all-time high", "ath",
        "breaking", "urgent", "just announced",
    ],
    "crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto",
        "sec", "etf", "halving", "whale", "dump", "pump",
    ],
    "stocks": [
        "earnings", "guidance", "buyback", "dividend",
        "merger", "acquisition", "ipo", "delisting",
    ],
    "geopolitical": [
        "war", "sanctions", "tariff", "china", "russia",
        "opec", "oil", "embargo",
    ],
}

# =============================================================================
# 数据源配置 (Data Source Settings)
# =============================================================================

COLLECTOR_CONFIG = {
    # Nitter 实例列表 (X/Twitter 爬取)
    "nitter_instances": [
        "https://nitter.net",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
    ],

    # 采集频率 (分钟)
    "poll_interval_minutes": 60,

    # 每次采集保留的帖子数量
    "max_posts_per_account": 10,

    # 数据保留天数
    "data_retention_days": 7,
}

# =============================================================================
# 链上监控配置 (On-chain Monitoring)
# =============================================================================

ONCHAIN_CONFIG = {
    # 大额交易阈值
    "min_btc_value": 100,      # BTC 最小值
    "min_eth_value": 1000,     # ETH 最小值
    "min_usdt_value": 10_000_000,  # USDT 最小值 (1000万)

    # 已知巨鲸地址 (可添加更多)
    "whale_addresses": {
        "btc": [
            # Binance Cold Wallet
            "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
            # Bitfinex Cold Wallet
            "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",
        ],
        "eth": [
            # Binance
            "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
            # Wrapped BTC
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        ],
    },

    # 监控的交易所 (用于识别交易所地址)
    "exchanges": [
        "binance", "coinbase", "kraken", "okx", "bybit",
        "bitfinex", "huobi", "kucoin", "gemini",
    ],
}
