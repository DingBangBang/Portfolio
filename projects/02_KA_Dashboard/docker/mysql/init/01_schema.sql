# 本地起个 MySQL 让 ka_tier.py --use-db 有数可取。
# 只建了最核心的一张快照表，业务库那几十张表在仓库里没法还原，也没必要。

CREATE DATABASE IF NOT EXISTS retail DEFAULT CHARSET utf8mb4;
USE retail;

-- KA 指标快照：每天每个 cid 一行，交易额是近 30 天的，资产是当日的
CREATE TABLE IF NOT EXISTS ba_ka_snapshot (
    stat_date            DATE           NOT NULL,
    cid                  VARCHAR(32)    NOT NULL,
    last_30d_trade_val   DECIMAL(20, 2) DEFAULT 0,
    total_auc            DECIMAL(20, 2) DEFAULT 0,
    PRIMARY KEY (stat_date, cid),
    KEY idx_cid (cid)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 造几条不同量级的数据，够验证分层规则跑得通就行
INSERT INTO ba_ka_snapshot (stat_date, cid, last_30d_trade_val, total_auc) VALUES
    ('2023-06-01', '647592000000000001',  5200000.00,  1800000.00),  -- 应该进 ka3
    ('2023-06-01', '647592000000000002',  320000.00,   90000.00),    -- ka2
    ('2023-06-01', '647592000000000003',  45000.00,    12000.00),    -- ka1
    ('2023-06-01', '647592000000000004',  3000.00,     200.00),      -- ka0
    ('2023-06-01', '647592000000000005',  0.00,        260000.00),   -- 不交易但躺着资产
    ('2023-06-02', '647592000000000001',  1200000.00,  2800000.00),  -- ka3 掉到 ka2，模拟降级
    ('2023-06-02', '647592000000000002',  980000.00,   500000.00),   -- ka2 升 ka3
    ('2023-06-02', '647592000000000003',  45000.00,    12000.00),
    ('2023-06-02', '647592000000000004',  3000.00,     200.00),
    ('2023-06-02', '647592000000000005',  0.00,        260000.00);
