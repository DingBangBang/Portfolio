# 定时任务配置说明（默认手动触发）

> 本项目**不自动注册定时任务**。下面两种方式任选其一，确认无误后再手动启用。

## 前置配置

```bash
cd projects/04_Customer_Analysis_BA
conda activate customer_analysis_ba
cp .env.example .env          # 填入 SMTP 等配置（不要提交 .env）
```

手动完整跑一次，确认无误：

```bash
./scripts/run_daily.sh
# 或
conda run -n customer_analysis_ba python main.py
```

## 方式一：cron（Linux / macOS）

```bash
crontab -e
# 每天 09:00 运行（路径替换为你的绝对路径）
0 9 * * * /Users/dingbangchu/.cline/worktrees/93aa2/Portfolio/projects/04_Customer_Analysis_BA/scripts/run_daily.sh
```

> macOS 上 cron 可能受“完全磁盘访问权限”限制；若失败，改用 launchd。

## 方式二：launchd（macOS 推荐）

将 `com.bonnie.cex-analytics.plist` 放到 `~/Library/LaunchAgents/`，内容如下（路径请替换）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.bonnie.cex-analytics</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/dingbangchu/.cline/worktrees/93aa2/Portfolio/projects/04_Customer_Analysis_BA/scripts/run_daily.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/cex-analytics.out.log</string>
  <key>StandardErrorPath</key><string>/tmp/cex-analytics.err.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
```

启用 / 停用（**默认不执行**，需要时再运行）：

```bash
launchctl load  ~/Library/LaunchAgents/com.bonnie.cex-analytics.plist
launchctl unload ~/Library/LaunchAgents/com.bonnie.cex-analytics.plist
```

## 编排工具

本地采用 **`main.py` 作为轻量编排器**（数据生成 → DuckDB → dbt run/test → 建模分析 → 报表 → 三源通知）。
选择理由：无需常驻服务、依赖少、可直接被 cron/launchd 调用；若后续要上生产，可把 `main.py` 的步骤拆成 Airflow DAG。
