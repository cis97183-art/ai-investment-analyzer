# portfolio_rules.py (最終規則版)

# ==================================
# 規則一：風險偏好標的篩選規則 (維持不變)
# ==================================
SCREENING_RULES = {
    '保守型': {
        'rule': lambda df: (df['一年(σ年)'] < 25) & (df['一年(β)'] < 1.0) & (df['現金股利連配次數'] > 3) & (df['成交價現金殖利率'] > 0),
        'sort_by': ['市值(億)', '最新季度負債總額佔比(%)'],
        'ascending': [False, True]
    },
    '穩健型': {
        'rule': lambda df: (df['一年(σ年)'] >= 15) & (df['一年(σ年)'] < 40) & (df['一年(β)'] >= 0.6) & (df['一年(β)'] < 1.4) & (df['近3年平均ROE(%)'] > 0),
        'sort_by': ['近3年平均ROE(%)', '累月營收年增(%)'],
        'ascending': [False, False]
    },
    '積極型': {
        'rule': lambda df: (df['一年(σ年)'] > 30) & (df['一年(β)'] > 1.1) & (df['累月營收年增(%)'] > 10),
        'sort_by': ['累月營收年增(%)', '最新單季ROE(%)'],
        'ascending': [False, False]
    }
}

# ==================================
# 規則二：客製化投資組合建構規則 (全新結構)
# ==================================
PORTFOLIO_CONSTRUCTION_RULES = {
    '保守型': {
        '純個股': {
            'num_assets_min': 8, 'num_assets_max': 10, 'max_industry_assets': 2,
            'weighting_method': '因子加權', 'weighting_factor': '成交價現金殖利率',
            'hhi_limit': 0.20
        },
        '純 ETF': {
            'num_assets_min': 2, 'num_assets_max': 3,
            'weighting_method': '波動率倒數加權', # Custom logic
            'required_etf_type': '債券ETF'
        },
        '混合型': {
            'core_etfs': 1, 'satellite_stocks': 5, 'core_weight': 0.7,
            'core_etf_type': ['債券ETF', '高股息ETF'],
            'hhi_limit': 0.25, 'max_industry_assets': 2
        }
    },
    '穩健型': {
        '純個股': {
            'num_assets_min': 5, 'num_assets_max': 8, 'max_industry_assets': 2,
            'weighting_method': '因子加權', 'weighting_factor': '近3年平均ROE(%)',
            'hhi_limit': 0.25
        },
        '純 ETF': {
            'num_assets_min': 2, 'num_assets_max': 4,
            'weighting_method': '平均權重',
            'required_etf_type': '國內成分股ETF'
        },
        '混合型': {
            'core_etfs': 1, 'satellite_stocks': 5, 'core_weight': 0.6,
            'core_etf_type': ['國內成分股ETF'],
            'hhi_limit': 0.30, 'max_industry_assets': 2
        }
    },
    '積極型': {
        '純個股': {
            'num_assets_min': 5, 'num_assets_max': 7, 'max_industry_assets': 3,
            'weighting_method': '因子加權', 'weighting_factor': '累月營收年增(%)',
            'hhi_limit': 0.35 # HHI 僅供參考
        },
        '純 ETF': {
            'num_assets_min': 2, 'num_assets_max': 3,
            'weighting_method': '集中加權', # Custom logic
            'required_etf_type': None # 專注主題式
        },
        '混合型': {
            'core_etfs': 1, 'satellite_stocks': 5, 'core_weight': 0.6,
            'core_etf_type': ['科技相關ETF'], # e.g., '國外成分股ETF' or specific keywords
            'hhi_limit': None, # HHI 僅供參考, 應高於 0.3
            'max_industry_assets': 3
        }
    }
}