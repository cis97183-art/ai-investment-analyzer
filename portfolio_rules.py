# portfolio_rules.py

"""
機構級投資組合建構與優化策略框架規則庫
"""

# ==============================================================================
# 規則零：基礎排雷篩選 (Universal Exclusion Rules)
# ==============================================================================
UNIVERSAL_EXCLUSION_RULES = {
    'min_market_cap_billion': 50,  # 市值最小要求（億）
    'min_listing_years': 1,        # 最少上市（櫃）年資
    # 更新規則：排除近4季每股自由現金流為負的個股
    'min_free_cash_flow_per_share': 0, 
    'exclude_etf_types': ['槓桿及反向型ETF', '槓桿及反向型期貨ETF'] # 排除的ETF類型
}

# ==============================================================================
# 第一部分 A：個股標的池篩選規則 (平行篩選)
# ==============================================================================
STOCK_SCREENING_RULES = {
    'Conservative': {
        'description': "尋找波動低、財務穩健、能提供穩定現金流的龍頭企業。",
        'conditions': {
            'std_dev_rank_max': 0.3, # 一年標準差 (σ年) 在整體市場中排名前 30% 低
            'beta_max': 1.0,         # 一年 Beta (β) < 1.0
            'dividend_streak_min': 10, # 現金股利連續發放次數 > 10次
            'free_cash_flow_min': 0  # 最新近4季每股自由現金流(元) > 0
        },
        'sort_by': ['成交價現金殖利率', '市值(億)'],
        'ascending': [False, False]
    },
    'Moderate': {
        'description': "尋找與市場同步、體質優良、具備均衡成長潛力的中大型企業。",
        'conditions': {
            'std_dev_rank_min': 0.3, # 一年標準差 (σ年) 在整體市場中排名介於 30%
            'std_dev_rank_max': 0.7, # 至 70% 之間
            'avg_roe_min': 5.0,      # 近3年平均ROE(%) > 5%
            'revenue_growth_min': 0  # 累月營收年增(%) > 0%
        },
        'sort_by': ['近3年平均ROE(%)', '市值(億)'],
        'ascending': [False, False]
    },
    'Aggressive': {
        'description': "尋找高成長潛力、能引領產業趨勢的企業。",
        'conditions': {
            'std_dev_rank_min': 0.7, # 一年標準差 (σ年) 在整體市場中排名後 30% 高
            'beta_min': 1.1,         # 一年 Beta (β) > 1.1
            'revenue_growth_min': 15.0 # 累月營收年增(%) > 15%
        },
        'sort_by': ['累月營收年增(%)', '最新單季ROE(%)'],
        'ascending': [False, False]
    }
}

# ==============================================================================
# 第一部分 B：ETF 標的池篩選規則 (屬性分類)
# ==============================================================================
ETF_SCREENING_RULES = {
    'MarketCap': {
        'description': "追蹤大盤指數（如台灣50、S&P 500）的ETF。",
        'keywords': ['台灣50', 'MSCI台灣', 'S&P 500', 'US 500', '臺灣ESG永續', '公司治理', '道瓊', 'NASDAQ', '費城半導體']
    },
    'HighDividend': {
        'description': "以高現金殖利率為主要策略的ETF。",
        'keywords': ['高股息', '高息', '優息']
    },
    'Thematic/Sector': {
        'description': "專注於特定領域（如半導體、科技、AI）的ETF。",
        'keywords': ['半導體', '科技', 'AI', '5G', '電動車', '潔淨能源', '元宇宙', '供應鏈', '資訊', '網路', '智能', '綠能', '金融', 'REITs']
    },
    'GovernmentBond': {
        'description': "投資於高信用評級政府公債的ETF。",
        'keywords': ['公債', '美債']
    },
    'CorporateBond': {
        'description': "投資於高信用評級企業債的ETF。",
        'keywords': ['公司債', '金融債', '產業債', '企業債', '投等債']
    }
}

# ==============================================================================
# 第二部分：客製化投資組合建構策略
# ==============================================================================
PORTFOLIO_CONSTRUCTION_RULES = {
    # --------------------------------------------------------------------------
    # 純個股投資組合
    # --------------------------------------------------------------------------
    'Stocks': {
        'Conservative': {
            'source_pool': 'Conservative',
            'num_assets': (8, 10),
            'diversification': {'max_per_industry': 2},
            'weighting_strategy': 'factor',
            'weighting_factor': '成交價現金殖利率',
            'hhi_limit': 0.20
        },
        'Moderate': {
            'source_pool': 'Moderate',
            'num_assets': (5, 8),
            'diversification': {'max_per_industry': 2},
            'weighting_strategy': 'factor',
            'weighting_factor': '近3年平均ROE(%)',
            'hhi_limit': 0.25
        },
        'Aggressive': {
            'source_pool': 'Aggressive',
            'num_assets': (5, 7),
            'diversification': {'notes': '可集中於2-3個高成長產業'},
            'weighting_strategy': 'factor',
            'weighting_factor': '累月營收年增(%)',
            'hhi_limit': (0.25, 0.35)
        },
    },
    # --------------------------------------------------------------------------
    # 純ETF投資組合
    # --------------------------------------------------------------------------
    'ETF': {
        'Conservative': {
            'asset_allocation': {'Stocks': 0.3, 'Bonds': 0.7},
            'stock_source_pools': ['HighDividend'],
            'bond_source_pools': ['GovernmentBond', 'CorporateBond'],
            'weighting_strategy': 'risk_parity_bonds' # 債券部位中，波動較低的ETF權重較高
        },
        'Balanced': {
            'asset_allocation': {'Stocks': 0.6, 'Bonds': 0.4},
            'stock_source_pools': ['MarketCap', 'Thematic/Sector'],
            'bond_source_pools': ['GovernmentBond'],
            'weighting_strategy': 'sharpe_or_equal' # 市值型為核心，平均或偏重夏普
        },
        'Aggressive': {
            'asset_allocation': {'Stocks': 0.9, 'Bonds': 0.1},
            'stock_source_pools': ['MarketCap', 'Thematic/Sector'],
            'bond_source_pools': ['GovernmentBond'],
            'weighting_strategy': 'thematic_focused' # 明顯傾向主題型ETF
        }
    },
    # --------------------------------------------------------------------------
    # 混合型投資組合
    # --------------------------------------------------------------------------
    'Hybrid': {
        'Conservative': {
            'core_satellite_split': {'core': 0.7, 'satellite': 0.3},
            'core_etf_pools': ['GovernmentBond', 'CorporateBond', 'HighDividend'],
            'satellite_stock_pool': 'Conservative',
            'num_satellite_stocks': (3, 5)
        },
        'Balanced': {
            'core_satellite_split': {'core': 0.6, 'satellite': 0.4},
            'core_etf_pools': ['MarketCap'],
            'satellite_stock_pool': 'Moderate',
            'num_satellite_stocks': (3, 5)
        },
        'Aggressive': {
            'core_satellite_split': {'core': 0.5, 'satellite': 0.5},
            'core_etf_pools': ['Thematic/Sector'],
            'satellite_stock_pool': 'Aggressive',
            'num_satellite_stocks': (2, 4)
        }
    }
}
