# 0. PandaAlpha 系统需求概述
构建一个 **个人量化投资分析与决策支持系统**，支持 A 股市场，核心功能包括：

* **实时数据获取**（股价、成交量、换手率、基本面指标等）
* **指标计算与可视化**（价量指标、核心因子）
* **量化策略回测**（验证指标有效性）
* **AI 辅助分析**（结合传统量化与大模型给出综合评价）
* **告警通知**（触发条件时推送消息，支持多通知服务商）

# 1. 技术栈（稳定且能扩展）

* 后端：**Python + FastAPI**（类型友好，自动文档）([FastAPI][1])
* 数据：**Parquet + DuckDB**（直接读写 Parquet，谓词下推，单机快）([DuckDB][2])
* 元数据：**SQLite**（记录 run/任务/告警/指纹）
* 调度：**APScheduler**（日更/汇总/自检定时任务，支持持久化）([PyPI][3])
* 前端：**Next.js(React) + Tailwind + shadcn/ui**
* 图表：**ECharts（K线/大数据/联动） + Recharts（报表类轻图）**（通过适配层可切换）
* 回测/指标：**vectorbt**（快速日频回测）→ 如需更贴近 A股制度并行接 **RQAlpha**；绩效用 **quantstats/empyrical**；技术指标用 **ta**。([VectorBT][4], [vectorbt.pro][5], [GitHub][6])
* 告警：\*\*Server酱（sctapi.ftqq.com）\*\*作为首个通知实现，抽象 Notifier 接口，后续可并行 Telegram/Email/Bark。([sct.ftqq.com][7])

---

# 2. 数据源（主备明确，能落地）

* **主源 TuShare Pro**：日行情 `daily`、交易日历 `trade_cal`、复权 `adj_factor`、换手/估值等 `daily_basic`、公司基本信息/行业 `stock_basic`；后续可接财报/预告/快报。使用需注册 Token（`ts.set_token(...)` / `ts.pro_api(token)`）。([CRAN][8])
* **备源 AkShare**：开源金融数据接口，主源断档时的备用适配器。([GitHub][9])

> 说明：我们**不用 CSV 当存储/接口**；所有落盘皆 Parquet，统一经 DuckDB 读取（快 & 简洁）。([DuckDB][2])

---

# 3. 架构总览（解耦可插拔）

```
/app
  /adapters        # tushare_adapter.py / akshare_adapter.py
  /metrics         # turnover, ma, volatility（核心指标）
  /signals         # p_mom_63d, p_rev_5d, p_score, (q_quality, e_score)
  /backtest        # engines: vectorbt_engine.py, (rqalpha_engine.py)
  /observability   # collectors/evaluator（指标采集、阈值判断）
  /notifiers       # base.py, serverchan.py, (telegram.py, email.py)
  /api             # FastAPI routers
  scheduler.py     # APScheduler: daily(19:00)/summary(19:40)/selfcheck(23:00)
  settings.py      # Pydantic Settings (.env)
  main.py
/data
  /parquet/**      # prices_daily, daily_basic, signals_daily, reco_daily...
  meta.sqlite      # runs, jobs, alerts, selfcheck, fingerprints
/config
  alert_rules.yaml # 阈值、聚合、抑制、路由(到哪个 SendKey)
  universe.yaml    # Top200 规则
  reco.yaml        # TopN、持有期、退出条件
```

---

# 4. 前端页面 & 图表策略（适配层可切换）

* **Watchlist**：表格（价、涨跌幅、成交、**换手**、MA5/10/20、波动）
* **Stock Detail**：K线+MA+量柱+十字线+缩放（**ECharts**）
* **Market Dashboard**：Top/Bottom 榜、行业分布（ECharts）；轻图可用 Recharts
* **Recommendations**：推荐/预警/变更，解释卡（≥3条证据+退出）
* **Backtest**：参数→结果（权益曲线、回撤、分层收益、两档成本）— Recharts 足够
* **Calibration**（可选）：高/中/低分档未来收益单调性（Recharts）
* **Status & Alerts**：任务状态、数据质量、告警列表（可 Ack）

> 图表实现：`ui/charts/*` 做适配层：`CandleChart`→ECharts；`LineChart/BarChart`→Recharts。以后想全换只动适配层即可。

---

# 5. API（对前端稳定）

* `GET /api/prices?sid&start&end`：日价序列
* `GET /api/metrics?sid&window`：换手、MA、波动
* `GET /api/watchlist` / `POST /api/watchlist`
* `GET /api/universe?month`、`GET /api/market/summary?date`
* `GET /api/signals?date&sid`、`GET /api/rankings/p_score?date`
* `GET /api/daily?date`：三件套（推荐/预警/变更）
* `POST /api/backtest` → `{run_id}`；`GET /api/backtest/{run_id}`：指标+曲线+指纹
* `GET /api/status`、`GET /api/alerts`、`POST /api/ack`（观测/告警）

---

# 6. 调度（默认时区按你本地，时间可调）

* **19:00** `daily_job()`：拉数据→写 Parquet→计算指标/信号→生成三件套
* **19:40** `summary_job()`：根据 `alert_rules.yaml` 汇总 P2 告警并推送
* **23:00** `selfcheck_job()`：重跑最近7天配置，对比指标差（阈内 PASS）

> APScheduler 支持数据库持久化与“错过任务补跑”，重启后能追补任务。([PyPI][3], [BetterStack][10])

---

# 7. 观测 & 告警（Server酱 + 可插拔）

## 7.1 监控指标（默认阈值，可改）

* 运行/SLO：

  * `daily_job_slo`：19:30 前未产出 → **P1 立即告警**
  * `selfcheck_pass_rate`（近7天）<95% → P2
* 数据质量：

  * `data_freshness` 滞后>1交易日 → **P1**
  * `universe_coverage` <95% 或 `missing_ratio` >1% → P2
* 产出/策略：

  * `reco_count` < TopN\*40% → P2
  * `capacity_violation`（ST/停牌/涨跌停未屏蔽）>0 → **P1**
* 市场/事件（可选）：极端波动/负面事件 → P2

## 7.2 Notifier 抽象（Server酱为首个实现）

* 接口：`Notifier.send({severity, title, body, tags, dedupe_key})`
* **Server酱**：调用 `https://sctapi.ftqq.com/<SendKey>.send`，传 `title`/`desp`（正文 Markdown 可），即可把消息推送到个人微信/客户端。SendKey 在官网获取并写入 `.env`。([sct.ftqq.com][7])
* 策略：**P1 即时**、**P2 19:40 汇总**、P3 仅入库；`dedupe_key` + 抑制窗口（如60分钟同键只发一次）。
* 可插拔：后续加 `TelegramNotifier/Email/Bark` 共存，按 `alert_rules.yaml` 路由到不同通道。

---

# 8. 回测引擎（拼装为主，必要时再仿真）

* **默认 VectorbtEngine**：`Portfolio.from_signals` 快速回测，entries/exits + `shift(1)`实现 T+1，手续费两档（15/30bps），禁入/不可成交用掩码。([VectorBT][4])
* **可选 RQAlphaEngine**：需要更贴近 A股制度时（涨跌停/停牌/费用/滑点/日历），并行接 RQAlpha，同一 API 契约返回。([GitHub][11])
* 绩效：`quantstats/empyrical` 生成年化/波动/Sharpe/回撤等（前端取数呈现）。([GitHub][6])
* 指纹：每次回测返回 `data_snapshot_id / code_hash / config_hash / seed`，前端展示，便于复现。

---

# 9. 分阶段实施（每步“要做/依赖/输出/KR/风险&备选”）

## 阶段 A（5–7 天）｜数据通道 + 可视化底座（**先看见**）

* **要做**：TuShare Adapter（`trade_cal/daily/adj_factor/daily_basic/stock_basic`）→ Parquet；DuckDB 查询；Watchlist & Stock Detail；APScheduler 19:00 日更；`/api/prices /metrics /watchlist`。([CRAN][8])
* **依赖**：TuShare Token、.env、字段映射与复权口径
* **输出**：自选股表格 + 个股图；任务状态
* **KR**：收盘后 ≤**30分钟** 更新；三股抽查指标与后端 SQL 一致
* **风险&备选**：主源断档→AkShare Adapter 临时兜底([GitHub][9])

## 阶段 B（4–5 天）｜小宇宙 + 市场总览（**只看，不下结论**）

* **要做**：月度 Top200 宇宙；`/api/universe /api/market/summary`；Market Dashboard（Top/Bottom、行业分布）
* **KR**：覆盖率 ≥**95%**；缺失率 ≤**1%**（清单可导出）

## 阶段 C（3–4 天）｜P-Score 观察榜（**不做交易结论**）

* **要做**：用 **ta / vectorbt** 指标计算 `p_mom_63d / p_rev_5d / p_score`，写 `signals_daily.parquet`；`/api/rankings/p_score`；前端榜单+评分轨迹。([VectorBT][4])
* **KR**：评分与“肉眼趋势”一致；无未来数据错位

## 阶段 **X**（与 A 同周1天）｜观测 + 告警（**Server酱**上线）

* **要做**：采集 A/B/C 指标→评估阈值→生成告警；`ServerChanNotifier` 用 SendKey 调 `.../<SendKey>.send`；P1 即时、P2 19:40 汇总、可 Ack。([sct.ftqq.com][7])
* **KR**：日更失败/数据断档 **<60s** 即收到 P1；P2 合并为一条日报；前端可 Ack

## 阶段 D（5–7 天）｜T+1 推荐 + 回测 v0（**拼装**）

* **要做**：

  * 推荐 v0：P-Score TopN（10–25），禁入 ST/停牌/涨跌停；解释卡≥3证据+退出；
  * 回测 v0：**vectorbt** from\_signals + `shift(1)`，手续费 15/30 bps；`/api/daily /api/backtest`；前端 Recommendations & Backtest（分层收益、回撤、两档成本）。([VectorBT][4])
* **KR**：连续 **5 个交易日** 19:30 前有三件套；3–5 年回测“高>低”单调；禁入零漏
* **风险&备选**：要制度级仿真→并行接 **RQAlphaEngine**（同一 API 输出）([GitHub][11])

## 阶段 E（可选 5–7 天）｜质量 Q & 校准

* **要做**：`q_quality`（ROE 稳定 + 现净一致性）→ `pq_score`；用 **statsmodels** 做 IC/t 值；前端 Calibration（三档未来20日）。
* **KR**：`pq_score` 回撤不劣于 `p_score`；单调性基本成立

---

# 10. 配置示例（摘录）

**.env.sample**

```
TUSHARE_TOKEN=你的token
SERVERCHAN_SENDKEY=SCUxxxxxxxxxxxxxxxx
TZ=Asia/Shanghai
```

**config/alert\_rules.yaml（节选）**

```yaml
slo:
  daily_job_deadline: "19:30"
  selfcheck_pass_rate_threshold: 0.95
severity:
  P1: [daily_job_slo, data_freshness, capacity_violation]
  P2: [universe_coverage, missing_ratio, reco_count, backtest_regression]
routing:
  - when: P1
    notifiers: [serverchan]
  - when: P2
    notifiers: [serverchan]
dedupe_window_minutes: 60
summary_time: "19:40"
```

**config/reco.yaml（节选）**

```yaml
topN: 20
hold_days: 10
exit:
  max_drawdown_pct: 0.10
  evidence_reverse: true
ban_list: ["ST", "停牌", "涨跌停"]
```

---

# 11. 依赖与安装（最小可跑）

```bash
# 后端
pip install fastapi uvicorn[standard] pydantic-settings
pip install duckdb pyarrow pandas
pip install apscheduler
pip install tushare akshare
pip install vectorbt numpy numba
pip install quantstats empyrical
# 前端（示例）
# npx create-next-app@latest ... + tailwind + shadcn/ui
```

> 以上库均有活跃文档/生态，近年持续维护：FastAPI、DuckDB、APScheduler、vectorbt/RQAlpha、QuantStats 等。([FastAPI][1], [DuckDB][2], [PyPI][3], [VectorBT][4], [GitHub][11])

---

# 12. 风险与备选

* **数据断档**：切到 AkShare Adapter（仅行情/指标），源恢复后切回。([GitHub][9])
* **回测性能**：vectorbt 已向量化/Numba 加速；仍慢时收窄时间窗或并行。([VectorBT][12])
* **制度仿真**：需要更真实→接 RQAlpha 并行引擎（相同 API 结果）。([GitHub][11])
* **告警轰炸**：用 `dedupe_key` + 抑制窗口 + P2 汇总；仅 P1 即时。

---

# 13. 完成定义（DoD）

* **A**：网页可见自选股核心指标；≤30 分钟更新；三股抽查一致
* **B**：宇宙覆盖 ≥95%，缺失 ≤1%
* **C**：P-Score 榜上线、无未来数据
* **X**：Server酱告警可用；P1 即时、P2 汇总、前端可 Ack
* **D**：三件套 + 回测页；分层“高>低”；禁入零漏
* **E**（可选）：`pq_score` 稳定不弱于 `p_score`；单调性基本成立