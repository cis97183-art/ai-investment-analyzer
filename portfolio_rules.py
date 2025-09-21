# portfolio_rules.py (最終版 - 使用中文鍵值)

"""
機構級投資組合建構與優化策略框架規則庫
"""

# ==============================================================================
# 規則零：基礎排雷篩選 (Universal Exclusion Rules)
# ==============================================================================
UNIVERSAL_EXCLUSION_RULES = {
    'min_market_cap_billion': 50,      # 最低市值要求(億)
    'min_listing_years': 1,            # 最低上市/成立年資
    'min_free_cash_flow_per_share': 0, # 最低每股自由現金流(僅對個股)
    'exclude_etf_types': ['槓桿及反向型ETF', '槓桿及反向型期貨ETF'] # 排除的ETF類型
}

# ==============================================================================
# 第一部分 A：個股標的池篩選規則 (平行篩選)
# 【核心修正】鍵值改為中文，與 app.py 中的選項直接對應
# ==============================================================================
STOCK_SCREENING_RULES = {
    '保守型': {
        'description': "尋找波動低、財務穩健、能提供穩定現金流的龍頭企業。",
        'conditions': {
            'std_dev_rank_max': 0.3,     # 波動率排名在前 30% (低波動)
            'beta_max': 1.0,             # Beta值小於等於1
            'dividend_streak_min': 10,   # 連續配息超過10年
            'free_cash_flow_min': 0      # 每股自由現金流大於0
        },
        'sort_by': ['成交價現金殖利率', '市值(億)'],
        'ascending': [False, False]
    },
    '穩健型': {
        'description': "尋找與市場同步、體質優良、具備均衡成長潛力的中大型企業。",
        'conditions': {
            'std_dev_rank_min': 0.3,     # 波動率排名在 30% 至 70% 之間
            'std_dev_rank_max': 0.7,
            'avg_roe_min': 5.0,          # 近3年平均ROE大於5%
            'revenue_growth_min': 0      # 近12個月營收成長大於0
        },
        'sort_by': ['近3年平均ROE(%)', '市值(億)'],
        'ascending': [False, False]
    },
    '積極型': {
        'description': "尋找高成長潛力、能引領產業趨勢的企業。",
        'conditions': {
            'std_dev_rank_min': 0.7,     # 波動率排名在後 30% (高波動)
            'beta_min': 1.1,             # Beta值大於1.1
            'revenue_growth_min': 15.0   # 近12個月營收成長大於15%
        },
        'sort_by': ['累月營收年增(%)', '最新單季ROE(%)'],
        'ascending': [False, False]
    }
}

# ==============================================================================
# 第一部分 B：ETF 標的池篩選規則 (屬性分類)
# 【核心修正】鍵值改為中文，方便內部呼叫
# ==============================================================================
ETF_SCREENING_RULES = {
    '市值型': {
        'description': "追蹤大盤指數（如台灣50、S&P 500）的ETF。",
        'keywords': ['台灣50', 'MSCI台灣', 'S&P 500', 'US 500', '臺灣ESG永續', '公司治理', '道瓊', 'NASDAQ', '費城半導體']
    },
    '高股息型': {
        'description': "以高現金殖利率為主要策略的ETF。",
        'keywords': ['高股息', '高息', '優息']
    },
    '主題/產業型': {
        'description': "專注於特定領域（如半導體、科技、AI）的ETF。",
        'keywords': ['半導體', '科技', 'AI', '5G', '電動車', '潔淨能源', '元宇宙', '供應鏈', '資訊', '網路', '智能', '綠能', '金融', 'REITs']
    },
    '政府公債': {
        'description': "投資於高信用評級政府公債的ETF。",
        'keywords': ['公債', '美債']
    },
    '投資級公司債': {
        'description': "投資於高信用評級企業債的ETF。",
        'keywords': ['公司債', '金融債', '產業債', '企業債', '投等債']
    }
}

# ==============================================================================
# 第二部分：客製化投資組合建構策略
# 【核心修正】所有鍵值均改為中文
# ==============================================================================
PORTFOLIO_CONSTRUCTION_RULES = {
    '純個股': {
        '保守型': {
            'source_pool': '保守型',
            'num_assets': (8, 10),
            'diversification': {'max_per_industry': 2},
            'weighting_strategy': 'factor',
            'weighting_factor': '成交價現金殖利率'
        },
        '穩健型': {
            'source_pool': '穩健型',
            'num_assets': (5, 8),
            'diversification': {'max_per_industry': 2},
            'weighting_strategy': 'factor',
            'weighting_factor': '近3年平均ROE(%)'
        },
        '積極型': {
            'source_pool': '積極型',
            'num_assets': (5, 7),
            'diversification': {'notes': '可集中於2-3個高成長產業'},
            'weighting_strategy': 'factor',
            'weighting_factor': '累月營收年增(%)'
        },
    },
    '純ETF': {
        '保守型': {
            'asset_allocation': {'Stocks': 0.3, 'Bonds': 0.7},
            'stock_source_pools': ['高股息型'],
            'bond_source_pools': ['政府公債', '投資級公司債'],
            'num_assets_per_category': 2 # 每類別選2支
        },
        '穩健型': {
            'asset_allocation': {'Stocks': 0.6, 'Bonds': 0.4},
            'stock_source_pools': ['市值型', '主題/產業型'],
            'bond_source_pools': ['政府公債'],
            'num_assets_per_category': 2
        },
        '積極型': {
            'asset_allocation': {'Stocks': 0.9, 'Bonds': 0.1},
            'stock_source_pools': ['市值型', '主題/產業型'],
            'bond_source_pools': ['政府公債'],
            'num_assets_per_category': 2
        }
    },
    '混合型': {
        '保守型': {
            'core_satellite_split': {'core': 0.7, 'satellite': 0.3},
            'core_etf_pools': ['政府公債', '投資級公司債', '高股息型'],
            'satellite_stock_pool': '保守型',
            'num_core_etfs': 2,
            'num_satellite_stocks': (3, 5)
        },
        '穩健型': {
            'core_satellite_split': {'core': 0.6, 'satellite': 0.4},
            'core_etf_pools': ['市值型'],
            'satellite_stock_pool': '穩健型',
            'num_core_etfs': 2,
            'num_satellite_stocks': (3, 5)
        },
        '積極型': {
            'core_satellite_split': {'core': 0.5, 'satellite': 0.5},
            'core_etf_pools': ['主題/產業型'],
            'satellite_stock_pool': '積極型',
            'num_core_etfs': 2,
            'num_satellite_stocks': (2, 4)
        }
    }
}
