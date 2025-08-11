# PandaAlpha · 项目计划（最终版）

> 路线：**看得见数据 → 被叫醒 → 覆盖更广 → 可解释评分 → 谨慎给结论 → 稳定性**。
> 每阶段明确**产出**与**KR（门槛）**；未达标则收窄范围（先小样本/Top50 再扩）。

## 概览：阶段与里程碑

* **A｜数据通道 + 可视化底座**（5–7 天）→ 看得见数据
* **X｜观测 + 告警（Server酱）**（与 A 同周 +1 天）→ 被叫醒
* **B｜小宇宙 + 市场总览**（4–5 天）→ 覆盖更广
* **C｜P-Score 观察榜**（3–4 天）→ 可解释评分
* **D｜T+1 推荐 + 回测 v0**（5–7 天）→ 谨慎给结论
* **E｜质量 Q + 校准（可选）**（5–7 天）→ 稳定性

---

## 阶段 A｜数据通道 + 可视化底座（5–7 天）

### A-0 项目骨架与环境（0.5 天）

* **做什么**：初始化后端（FastAPI + APScheduler + `SQLAlchemyJobStore(sqlite:///data/meta.sqlite)`）、前端（Next.js + Tailwind + shadcn/ui）、数据目录（Parquet/SQLite）、`.env` 管理。
* **依赖**：无。
* **产出**：仓库结构；`GET /health` 与 `GET /api/status` 返回 200。
* **KR**：本地起服可访问；`/api/status` 返回空水位线与作业列表。

### A-1 数据适配器（TuShare 主源；AkShare 备源）（1.5–2 天）

* **做什么**：拉取 `trade_cal/daily/adj_factor/daily_basic/stock_basic`，按规范落 **分区式 Parquet**；主键统一 **`ts_code`**；更新 `watermark.parquet`。
* **落盘路径**：

  * `data/parquet/prices_daily/year=YYYY/month=MM/day=DD/part-*.parquet`
  * `data/parquet/daily_basic/year=YYYY/month=MM/day=DD/part-*.parquet`
  * `data/watermark.parquet`、`data/meta.sqlite`
* **依赖**：TuShare Token。
* **产出**：Adapter、频控与重试、增量拉取、失败补偿队列。
* **KR**：任选 3 只股票，近 1 年数据完整；日历与行情对齐；DuckDB 分区裁剪有效。

### A-2 核心指标展示（1 天）

* **做什么**：服务端计算展示用指标：MA5/10/20、**年化波动 `vol_ann`**；换手取 `daily_basic.turnover_rate`。**不落“metrics”数据集**（持久化至 C 阶段）。
* **依赖**：A-1。
* **产出**：指标计算模块（与 C 阶段复用）。
* **KR**：随机 3 只股票，SQL/即时计算一致。

### A-3 API：`/api/prices` `/api/metrics` `/api/watchlist`（0.5–1 天）

* **做什么**：实现三端点，统一分页 `page,limit`；读接口返回 `Cache-Control: max-age=300` 与 `ETag`；错误包 `{error:{code,message,details?}}`；

  * **ETag 计算**：`ETag = sha1(data_snapshot_id + normalized_query)`，其中多标的 `ts_code` 需**拆分→去重→排序**后参与 `normalized_query`。
  * `/api/metrics` 逐日行返回；`/api/prices` 支持 `include_basic=true` 左连 `daily_basic`。
* **依赖**：A-2。
* **产出**：OpenAPI；契约测试。
* **KR**：P95 < 150ms（本地/小样本）；错误返回规范。

### A-4 前端：Watchlist & Stock Detail（1.5–2 天）

* **做什么**：

  * Watchlist：表格（价/涨跌幅/量/**换手**/MA/`vol_ann`）+ 虚拟滚动；
  * Stock Detail：K 线（ECharts，`dynamic({ssr:false})`）+ MA + 量柱 + 十字线 + dataZoom；
  * 主题与 shadcn/ui 风格统一。
* **依赖**：A-3。
* **产出**：两页可用 UI。
* **阶段 A 总 KR**：

  * 收盘后 ≤ **30 分钟** 页面可见更新；
  * 抽查 3 股，前/后端指标一致；
  * `/api/status` 显示“日更成功/失败”。

---

## 阶段 X｜观测 + 告警（与 A 同周 +1 天）

### X-1 监控指标采集与评估（0.5 天）

* **做什么**：采集 `daily_job_deadline/selfcheck_pass_rate/data_freshness/universe_coverage/missing_ratio`；按 `alert_rules.yaml` 评估。
* **依赖**：A-3。
* **产出**：`alerts` 表与评估器。
* **KR**：可触发 P1/P2 测试告警（后端模拟）。

### X-2 Notifier 抽象 + Server酱接入（0.5 天）

* **做什么**：`Notifier` 接口；`ServerChanNotifier`（SendKey/.env）；P1 即时、P2 **19:40** 汇总；去重/抑制 60 分钟。
* **依赖**：X-1。
* **产出**：可配置告警通道 + 汇总任务。
* **KR**：

  * **P1**（SLO 未达或数据断档）< **60s** 到达；
  * P2 汇总为**一条**日报；
  * `/api/alerts` 支持筛选（`severity/state/from/to`）与分页，返回 `{page,limit,total,items}`；`/api/ack` 可确认。

### X-3 前端：Status & Alerts（0.5 天）

* **做什么**：Status 总览（任务/新鲜度/覆盖率）、告警列表（过滤/确认）。
* **依赖**：X-2。
* **产出**：Status & Alerts 页面。
* **KR**：可一键 Ack，状态入库更新。

---

## 阶段 B｜小宇宙 + 市场总览（4–5 天）

### B-1 宇宙生成（Top200 月度）（0.5 天）

* **做什么**：近 60 日**成交额均值**排序；剔除 `ST` 与上市 ≤ 30 日；落盘：
  `data/parquet/universe_monthly/month=YYYY-MM/part-*.parquet`（含 `ts_code/rank/avg_turnover`）。
* **依赖**：A-1。
* **产出**：宇宙快照 + 月更任务。
* **KR**：覆盖率统计正确；切月生效。

### B-2 市场总览 API（0.5 天）

* **做什么**：`/api/universe?month`、`/api/market/summary?date`（Top/Bottom/行业聚合）。

  * 统一：`adv_decl` 未涨跌字段名 **`unch`**；`pct_chg` **为小数**（`0.07 = +7%`）。
* **依赖**：B-1。
* **产出**：端点 + 契约测试。
* **KR**：P95 < 200ms（小样）。

### B-3 前端：Market Dashboard（1–1.5 天）

* **做什么**：ECharts 榜单（Top/Bottom）、行业条形/饼图、宇宙覆盖/缺失率展示。
* **依赖**：B-2。
* **产出**：大盘页。
* **阶段 B 总 KR**：覆盖率 ≥ **95%**；缺失率 ≤ **1%**（含缺失清单）。

---

## 阶段 C｜P-Score 观察榜（3–4 天）

### C-1 指标/信号计算与持久化（0.5–1 天）

* **做什么**：计算 `p_mom_63d/p_rev_5d`，合成 `p_score` 与 `vol_ann`；落盘：
  `data/parquet/signals_daily/year=YYYY/month=MM/day=DD/part-*.parquet`（含 `mask_untradable`）。
* **依赖**：A-2。
* **产出**：信号数据集。
* **KR**：时间对齐无“未来数据”（shift 校验）。

### C-2 API & 排行（0.5 天）

* **做什么**：

  * `GET /api/signals?date=YYYY-MM-DD&ts_code=...`（**默认返回** `mask_untradable` 字段）
  * `GET /api/rankings/p_score?date=YYYY-MM-DD&top=N&with_history=true|false`（**`with_history=false` 时不返回 `history` 字段**）
* **依赖**：C-1。
* **产出**：端点 + 契约测试。
* **KR**：Top 榜/个股轨迹可取。

### C-3 前端展示（1–1.5 天）

* **做什么**：Dashboard 增加 P-Score 榜；Stock Detail 增加评分轨迹小图。
* **依赖**：C-2。
* **产出**：两处 UI。
* **阶段 C 总 KR**：P-Score 榜与肉眼趋势一致；无错位。

---

## 阶段 D｜T+1 推荐 + 回测 v0（5–7 天）

### D-1 推荐规则与禁入（1 天）

* **做什么**：按 `reco.yaml`（TopN/持有期/退出条件）生成每日推荐；禁入：`ST/停牌/涨跌停`；推荐卡 ≥3 证据（动量分位、短反分位、换手/`vol_ann`）。
* **依赖**：C-1。
* **产出**：`/api/daily` 三件套；（是否额外落 `reco_daily/changelog_daily/alerts_daily` 为实现细节，可选）。
* **KR**：禁入规则**零漏**。

### D-2 回测引擎（vectorbt，T+1 + 顺延 bfill）（2–3 天）

* **做什么**：

  * T+1：`entries/exits + shift(1)`；
  * 顺延：用 `open.shift(-1)`，对 `mask_untradable.shift(-1)` 置 `NaN` 后 **`bfill`** 到下一可成交日；**尾日因 `shift(-1)` 产生的 NaN 直接丢弃**；
  * 费用：支持 `fees_bps: {buy,sell}`（兼容单值）；`slippage_bps`；
  * 指标：`quantstats/empyrical`。
* **依赖**：D-1。
* **产出**：

  * `POST /api/backtest`（接受双边或单值费用）、
  * `GET /api/backtest/{run_id}`（权益/回撤/分层/成交统计〔拒单/顺延天数〕/指纹）。
* **KR**：3–5 年能跑；分层“高>低”单调。

### D-3 前端：Recommendations & Backtest（2–3 天）

* **做什么**：三件套（表格 + 解释卡）；回测参数表单 + 图表（权益/回撤/分层）。
* **依赖**：D-1/D-2。
* **产出**：两页 UI。
* **阶段 D 总 KR**：

  * 连续 **5 个交易日** 19:30 前产出三件套；
  * 每条推荐 ≥3 证据 + 退出条件；
  * 回测分层“高>低”单调。

> 需要订单级撮合/部分成交：追加 **D-4 RQAlphaEngine（2–3 天）**，契约一致。

---

## 阶段 E（可选）｜质量 Q + 校准（5–7 天）

### E-1 Q 因子（简化）（2 天）

* **做什么**：构造 `q_quality`（ROE 稳定 + 现净一致性），与 `p_score` 合成 `pq_score`；更新 `signals_daily`。
* **依赖**：财务数据字段。
* **产出**：信号更新。
* **KR**：`pq_score` 回撤不劣于 `p_score`。

### E-2 校准页（1–2 天）

* **做什么**：用 statsmodels 计算 IC/t 值与分层收益；前端展示高/中/低 **20 日** 单调性。
* **依赖**：E-1。
* **产出**：Calibration 页。
* **阶段 E 总 KR**：单调性基本成立。

---

## 横切事项（各阶段通用）

* **API 契约**：统一分页 `page,limit`；读接口返回 `Cache-Control: max-age=300` 与 `ETag`。

  * **ETag**：`ETag = sha1(data_snapshot_id + normalized_query)`；多标的 `ts_code` 参与 `normalized_query` 时需**拆分→去重→排序**以保证幂等。
  * **错误包**：`{error:{code,message,details?}}`（常见：`InvalidParam/NotFound/RateLimited/Internal`）。
* **命名口径**：仅使用 `ts_code`；年化波动统一 `vol_ann`；涨跌字段统一 `adv_decl.unch`；`pct_chg` 为**小数**。
* **数据质量**：阶段结束更新 `watermark.parquet`；`/api/status` 展示 `watermarks` 与 `jobs`。
* **测试**：单测（字段映射/复权/日历），集成（`daily_job` 全链路），金标集（100 只 × 3 年），回测曲线阈值（MSE/MaxAE）。
* **安全与合规**：本地默认；对外启用 `X-API-Key` 与 CORS 白名单；数据仅用于个人研究，遵守源站 TOS。

---

## 风险与应对

* **主源断档/限流**：切 AkShare；失败补偿队列 + 指数退避。
* **小文件过多**：月度 compact；行组 128–256MB；列裁剪 + 谓词下推。
* **顺延口径差异**：VectorbtEngine 采用 **bfill**；需订单级撮合时切 RQAlphaEngine。
* **指标口径误判**：UI 明示口径（复权、`pct_chg` 为小数、停牌容差与 `tick_size=0.01`）。

---

## 出口条件（Go/No-Go）

* **A/B/C** 达成且 KR 通过；
* **X** P1 即时、P2 汇总与 ACK 可用；
* **D** 回测分层“高>低”单调、三件套连续 5 天产出；
* 合规与安全检查通过。