# -*- coding: utf-8 -*-
"""配置文件读取。

项目里就一个 yaml + 两个环境变量，没必要上 pydantic-settings 那一套。
真实路径不想提交，所以仓库里只放 config.example.yaml。
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 兜底默认值：缺 yaml / yaml 装不上时也能直接跑样例数据
DEFAULTS = {
    "data_path": str(BASE_DIR / "sample_data" / "events_sample.csv"),
    "output_dir": str(BASE_DIR / "outputs"),
    "chunk_size": 500000,
}


def load_config(path=None):
    """读配置。优先级：环境变量 > config.yaml > config.example.yaml > 默认值。

    之前偷懒把路径写死在脚本里，换台机器就得改代码，吃过一次亏。
    """
    cfg_path = Path(path or os.getenv("EDA_CONFIG", BASE_DIR / "config.yaml"))
    if not cfg_path.exists():
        cfg_path = BASE_DIR / "config.example.yaml"

    cfg = dict(DEFAULTS)
    if cfg_path.exists():
        try:
            import yaml

            with open(cfg_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            cfg.update({k: v for k, v in loaded.items() if v is not None})
        except Exception as e:  # yaml 没装 / 文件写坏了，就闭嘴用默认值
            print("[warn] 读 %s 失败(%s)，先用默认配置跑" % (cfg_path, e))

    # 临时换数据文件用环境变量，不用改 yaml
    cfg["data_path"] = os.getenv("EDA_DATA_PATH", cfg["data_path"])
    cfg["chunk_size"] = int(os.getenv("EDA_CHUNK_SIZE", cfg["chunk_size"]))
    return cfg
