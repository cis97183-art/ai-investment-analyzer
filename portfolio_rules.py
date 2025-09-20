# portfolio_rules.py

# ==================================
# 規則一：風險偏好標的篩選規則 (單一規則版)
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
# 規則二：投資組合建構規則 (維持不變)
# ==================================
PORTFOLIO_CONSTRUCTION_RULES = {
    '純個股': {
        'min_assets': 5,
        'max_assets': 10,
        'max_industry_assets': 2,
        'hhi_limit': 0.25
    },
    '純 ETF': {
        'min_assets': 2,
        'max_assets': 4,
    },
    '混合型': {
        'core_etfs': 2,
        'satellite_stocks': 5,
        'core_weight': 0.7,
        'hhi_limit': 0.3,
        'max_industry_assets': 2
    }
}