# 概览：阶段与里程碑

- **A ｜数据通道 + 可视化底座**（5–7 天）→ 看得见数据
- **X ｜观测 + 告警（Server 酱）**（与 A 同周 1 天）→ 被叫醒
- **B ｜小宇宙 + 市场总览**（4–5 天）→ 覆盖更广
- **C ｜ P-Score 观察榜**（3–4 天）→ 可解释评分
- **D ｜ T+1 推荐 + 回测 v0**（5–7 天）→ 谨慎给结论
- **E ｜质量 Q + 校准（可选）**（5–7 天）→ 稳定性

> 每阶段都有**阶段 KR（门槛）**，不达标就收窄范围（先自选/Top50，再扩）。

---

# 阶段 A ｜数据通道 + 可视化底座（5–7 天）

## A-0 项目骨架与环境

- 做什么：后端 FastAPI + APScheduler；前端 Next.js + Tailwind + shadcn/ui；数据目录（Parquet/SQLite）；`.env` 管理。
- 依赖：无。
- 产出：仓库结构、可启动的空 API 与空页面。
- KR：本地 `GET /health` 200；前端起得来。
- 预估：0.5 天

## A-1 数据适配器（TuShare 主源；AkShare 备源）

- 做什么：拉 `trade_cal/daily/adj_factor/daily_basic/stock_basic`，落 **Parquet**；统一 `sid/ts_code`；DuckDB 能查。
- 依赖：TuShare Token；字段口径说明。
- 产出：`prices_daily.parquet`、`daily_basic.parquet`、`securities.parquet`。
- KR：任意 3 只股票，最近一年数据完整；日历与行情对齐。
- 预估：1.5–2 天

## A-2 核心指标计算（metrics）

- 做什么：换手率（直接用 `daily_basic` 字段或口径换算）、MA5/10/20、5/20 日年化波动；写 `metrics_daily.parquet`。
- 依赖：A-1。
- 产出：指标表 + DuckDB 视图。
- KR：随机 3 只股票，SQL 现场计算与落库一致。
- 预估：1 天

## A-3 API：/prices /metrics /watchlist

- 做什么：FastAPI 三个只读端点，分页/缓存；错误处理；基本契约测试。
- 依赖：A-2。
- 产出：Swagger 文档可访问；契约测试通过。
- KR：P95 延时 < 150ms（本地/小样本）；错误返回规范。
- 预估：0.5–1 天

## A-4 前端页面：Watchlist & Stock Detail（ECharts K 线）

- 做什么：Watchlist 表格（价/涨跌幅/量/**换手**/MA/波动）；个股详情（K 线 + MA + 量柱 + 十字线 + dataZoom）。
- 依赖：A-3。
- 产出：两页可用 UI；主题配色与 shadcn/ui 卡片风格统一。
- KR（阶段 A 总 KR）：

  - 收盘后 ≤ **30 分钟** 页面可见更新；
  - 抽查 3 只股票，前/后端指标一致；
  - 任务状态条能看到“日更成功/失败”。

- 预估：1.5–2 天

---

# 阶段 X ｜观测 + 告警（与 A 同周 1 天）

## X-1 监控指标采集与评估

- 做什么：采集 `daily_job_slo/selfcheck_pass_rate/data_freshness/universe_coverage/missing_ratio`；按 `alert_rules.yaml` 出告警事件。
- 依赖：A-3。
- 产出：`alerts` 表、评估器。
- KR：能在后台触发一条 P1/P2 测试告警。
- 预估：0.5 天

## X-2 Notifier 抽象 + Server 酱接入

- 做什么：`Notifier` 接口；`ServerChanNotifier`（SendKey/.env）；P1 即时、P2 19:40 汇总；去重/抑制（60 分钟）。
- 依赖：X-1。
- 产出：可配置的告警通道 + 汇总任务。
- KR：

  - **P1（SLO 未达或数据断档） < 60s** 收到推送；
  - P2 汇总为**一条**日报；
  - `/api/alerts /api/ack` 可查看并确认。

- 预估：0.5 天

## X-3 前端：Status & Alerts

- 做什么：状态总览、小卡片（今日任务/数据新鲜度/覆盖率），告警列表（过滤/确认）。
- 依赖：X-2。
- 产出：Status & Alerts 页面。
- KR：可一键 Ack，落库状态变化。
- 预估：0.5 天

---

# 阶段 B ｜小宇宙 + 市场总览（4–5 天）

## B-1 宇宙生成（Top200 月度）

- 做什么：基于近 60 日成交额计算 Top200，写 `universe_month.parquet`；APScheduler 月更任务。
- 依赖：A-1。
- 产出：宇宙快照。
- KR：覆盖率统计正确；切换月份 OK。
- 预估：0.5 天

## B-2 市场总览 API

- 做什么：`/api/universe?month`、`/api/market/summary?date`（Top/Bottom/行业聚合）。
- 依赖：B-1。
- 产出：两个端点 + 测试。
- KR：P95 < 200ms（小样）。
- 预估：0.5 天

## B-3 前端：Market Dashboard

- 做什么：ECharts 榜单（Top/Bottom）、行业条形/饼图、宇宙覆盖率与缺失率。
- 依赖：B-2。
- 产出：市场大盘页。
- KR（阶段 B 总 KR）：

  - 宇宙覆盖率 ≥ **95%**；
  - 缺失率 ≤ **1%**（有缺失清单）。

- 预估：1–1.5 天

---

# 阶段 C ｜ P-Score 观察榜（3–4 天）

## C-1 指标计算（用 ta / vectorbt）

- 做什么：`p_mom_63d`、`p_rev_5d`，合成 `p_score`；写 `signals_daily.parquet`。
- 依赖：A-2。
- 产出：信号表。
- KR：时间对齐无“未来数据”（shift 校验）。
- 预估：0.5–1 天

## C-2 API & 排行

- 做什么：`/api/signals?date&sid`、`/api/rankings/p_score?date`。
- 依赖：C-1。
- 产出：端点 + 契约测试。
- KR：TOP 榜/个股曲线可取。
- 预估：0.5 天

## C-3 前端展示

- 做什么：Market Dashboard 增加 P-Score 榜；Stock Detail 增加评分轨迹小图。
- 依赖：C-2。
- 产出：两处 UI。
- KR（阶段 C 总 KR）：P-Score 榜与肉眼趋势一致；无错位。
- 预估：1–1.5 天

---

# 阶段 D ｜ T+1 推荐 + 回测 v0（5–7 天）

## D-1 推荐规则与禁入

- 做什么：`reco.yaml`（TopN、持有期、退出条件、禁入：ST/停牌/涨跌停）；推荐卡 ≥3 证据（动量分位、短反分位、换手/波动）。
- 依赖：C-1。
- 产出：`reco_daily`、`alerts_daily`、`changelog_daily`（均 Parquet）。
- KR：禁入规则**零漏**。
- 预估：1 天

## D-2 回测引擎（vectorbt）

- 做什么：`VectorbtEngine` 封装：entries/exits + `shift(1)` 实现 T+1；手续费两档（15/30bps）；掩码处理不可成交日；指标用 quantstats/empyrical。
- 依赖：D-1。
- 产出：`POST /api/backtest`、`GET /api/backtest/{run_id}`；指纹（data/code/config/seed）。
- KR：3–5 年数据能跑；分层“高>低”单调；指标齐全。
- 预估：2–3 天

## D-3 前端：Recommendations & Backtest

- 做什么：推荐三件套（表格 + 解释卡）；回测参数表单 + 图表（权益/回撤/分层/两档成本）。
- 依赖：D-1/D-2。
- 产出：两页 UI。
- KR（阶段 D 总 KR）：

  - 连续 **5 个交易日** 19:30 前有三件套；
  - 三件套每条推荐都有 ≥3 证据 + 退出条件；
  - 回测分层“高>低”基本单调。

- 预估：2–3 天

> 需要更逼真的制度仿真：另起任务 **D-4 RQAlphaEngine（可并行，2–3 天）**，同一 API 契约返回结果。

---

# 阶段 E（可选）｜质量 Q + 校准（5–7 天）

## E-1 Q 因子（简化）

- 做什么：ROE 稳定性、现净一致性 → `q_quality`；与 `p_score` 合成 `pq_score`。
- 依赖：TuShare 财务口径字段。
- 产出：更新 `signals_daily`。
- KR：`pq_score` 回撤不劣于 `p_score`。
- 预估：2 天

## E-2 校准页

- 做什么：用 statsmodels 计算 IC/t 值与分层回归；前端画高/中/低 20 日收益曲线。
- 依赖：E-1。
- 产出：Calibration 页面。
- KR（阶段 E 总 KR）：单调性基本成立。
- 预估：1–2 天
