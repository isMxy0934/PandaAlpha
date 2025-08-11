# PandaAlpha 1.0 · 系统需求与技术规范（最终版）


## 0. 术语与口径（强制）

* **主键**：`ts_code`（亦称 `sid`，两者等价；统一字段名使用 `ts_code`），如 `000001.SZ | 600000.SH`
* **交易日字段**：`trade_date`，格式 `YYYY-MM-DD`（时区 **Asia/Shanghai**）
* **复权口径**：持久化 **不复权价**（`*_raw`）+ `adj_factor`；查询与指标默认 **后复权**（`adj=backward`），支持 `none|forward|backward`
* **T+1**：信号日在 `D`，在 `D+1` 以**开盘价**撮合；买入当日不可卖
* **不可成交掩码**：

  * **停牌**：`volume = 0` 且**价格不变在容差内**，容差：`|close_raw - pre_close| ≤ max(tick_size, 0.0005 * pre_close)`；**默认 `tick_size=0.01` 元**（可配置）
  * **涨跌停**：按板块规则（可配 `limit_up_pct/limit_dn_pct`）相对昨收判定
  * **无量**：`volume = 0`
* **`is_trading` 定义**：当日为交易日且 `volume > 0` 时为 `True`，否则 `False`（含全日停牌/无量）
* **Universe**：默认“月度 Top200”，按近 60 交易日**成交额均值**排序，剔除 `ST` 与上市 ≤ 30 日
* **行业口径**：默认 TuShare `stock_basic.industry`；如改用申万（AkShare），需在 `meta.sqlite.dicts` 记录 **`mapping_provider/version/updated_at`** 并在前端展示
* **单位与取值**：

  * `turnover_rate`：百分比 `%`；`vol_ann`：年化波动（无量纲，小数）；`fees_bps/slippage_bps`：基点（`1 bps = 0.01%`）
  * `amount`：人民币元；`volume`：股

---

## 1. 目标与范围

* **核心功能**：数据获取→指标/信号→回测→推荐（T+1）→可视化→观测与告警
* **非目标（1.0）**：分钟级数据、实盘交易/委托通道、多账户风控

---

## 2. 技术栈与依赖

* 后端：Python 3.10+、**FastAPI**
* 存储：**Parquet + DuckDB**（列存、谓词下推）
* 元数据库：**SQLite**（`meta.sqlite`：runs/jobs/alerts/snapshots/mappings）
* 调度：**APScheduler**（持久化 jobstore、错过补跑、互斥）
* 回测/指标：**vectorbt + ta + quantstats/empyrical**；可并行 **RQAlpha**
* 前端：**Next.js + Tailwind + shadcn/ui**；图表：**ECharts**（重）+ **Recharts**（轻）
* 告警：**Server酱（sctapi.ftqq.com）**
* **依赖版本建议（兼容稳定）**：`numpy<2`, `numba==0.59.*`, `empyrical==0.5.5`, `quantstats==0.0.62`, `pyarrow>=12`

---

## 3. 目录结构

```
/app
  /adapters            # tushare_adapter.py / akshare_adapter.py
  /datasource          # IO & schema utilities
  /metrics             # ma/turnover/vol_ann/...
  /signals             # p_mom_63d, p_rev_5d, p_score, (q_quality, pq_score)
  /backtest            # vectorbt_engine.py, (rqalpha_engine.py)
  /observability       # collectors & evaluator（SLO/质量）
  /notifiers           # base.py, serverchan.py, (telegram.py, email.py)
  /api                 # FastAPI routers & models
  scheduler.py  settings.py  main.py
/data
  /parquet/
    prices_daily/      # year=YYYY/month=MM/day=DD/part-*.parquet
    daily_basic/       # year=YYYY/month=MM/day=DD/part-*.parquet
    signals_daily/     # year=YYYY/month=MM/day=DD/part-*.parquet
    universe_monthly/  # month=YYYY-MM/part-*.parquet
  meta.sqlite
  watermark.parquet
/config
  alert_rules.yaml  universe.yaml  reco.yaml
/doc
  requirement.md  plan.md
```

---

## 4. 数据与分区规范

### 4.1 分区与压缩

* **分区路径**：统一 `year=YYYY/month=MM/day=DD`（月度数据：`month=YYYY-MM`）
* **压缩/编码**：`ZSTD`、字典编码、行组 128–256MB；开启 **BloomFilter**（`ts_code`）
* **BloomFilter 注记**：已在 **`pyarrow>=12`** 下验证

  * Writer 封装（不同版本参数名略异）：`pa.parquet.write_table(..., bloom_filter_enabled=True, bloom_filter_columns=['ts_code'])`
* **幂等写入**：写 `*.parquet.tmp` → 校验覆盖率/行数 → 原子 `rename` → 更新 `watermark.parquet`（`table,last_dt,rowcount,hash`）→ 月度 compact

### 4.2 表模式（统一来源）

**prices\_daily**（不含 `turnover_rate`，避免口径重复）

| 列名                                      | 类型           | 说明                 |
| --------------------------------------- | ------------ | ------------------ |
| ts\_code                                | STRING(dict) | 主键1                |
| trade\_date                             | DATE         | 主键2（Asia/Shanghai） |
| open\_raw/high\_raw/low\_raw/close\_raw | FLOAT32      | 不复权价               |
| pre\_close                              | FLOAT32      | 昨收（不复）             |
| adj\_factor                             | FLOAT32      | 复权因子               |
| volume                                  | INT64        | 股                  |
| amount                                  | FLOAT64      | 元                  |
| is\_trading                             | BOOL         | 交易日且 `volume>0`    |

> `adj=backward` 时 API 仅返回复权后的 `open/high/low/close`；`volume/amount` 原样（不复权）

**daily\_basic**（SOT：换手/估值）

| 列名                 | 类型      | 说明      |
| ------------------ | ------- | ------- |
| ts\_code           | STRING  | 主键1     |
| trade\_date        | DATE    | 主键2     |
| turnover\_rate     | FLOAT32 | %（唯一来源） |
| pe/pe\_ttm/pb/ps   | FLOAT32 | 估值      |
| total\_mv/circ\_mv | FLOAT64 | 市值      |

**signals\_daily**

| ts\_code | trade\_date | p\_mom\_63d | p\_rev\_5d | p\_score | vol\_ann | mask\_untradable | notes |
| -------- | ----------- | ----------- | ---------- | -------- | -------- | ---------------- | ----- |

---

## 5. 数据源与拉取策略

* **主源** TuShare Pro：`daily`、`trade_cal`、`adj_factor`、`daily_basic`、`stock_basic`
* **备源** AkShare：行情/行业兜底

**频控/重试**：限速表；`tenacity` 指数退避 `0.5→1→2…`（最多 5 次）
**增量**：`trade_cal` + `watermark.last_dt` 游标；全量首拉后仅补新增交易日
**失败补偿**：`meta.sqlite.fail_queue`（endpoint/params/retries/last\_error）
**脱敏**：日志掩码 Token；`.env` 不入库

**停牌/涨跌停推断**：按 §0 容差/板块规则；前端“口径说明”提示潜在误差

---

## 6. 指标与信号

* **MA(n)**：后复权收盘 `close` 简单移动均线
* **年化波动 `vol_ann`**：`std(daily_ret) * sqrt(252)`（避免与 `volume` 混淆）
* **换手率**：`daily_basic.turnover_rate`（服务端按 `(ts_code, trade_date)` 左连接）
* **动量 `p_mom_63d`**：`close/close.shift(63) - 1`
* **反转 `p_rev_5d`**：`-(close/close.shift(5) - 1)`
* **综合 `p_score`**：`rank_z(p_mom_63d) + 0.5 * rank_z(p_rev_5d)`
* **去极值/标准化**：1%–99% winsorize 后 Z-Score；缺失记录于 `notes`

---

## 7. Universe 与行业

* **构建**：每月首个交易日 18:00；近 60 日成交额均值排序；剔除 `ST`、上市 ≤ 30 日
* **输出**：`universe_monthly/month=YYYY-MM/part-*.parquet`
* **行业映射版本**：记录至 `meta.sqlite.dicts (mapping_provider/version/updated_at)` 并在前端展示

---

## 8. 回测引擎与顺延实现

* **撮合**：`D` 触发，`D+1` **开盘价**成交；不可成交（涨跌停/停牌/无量）→ **订单顺延**至下一可成交日；调仓“先卖后买”
* **T+1**：买入当日不可卖
* **费用/滑点**：

  * 支持**双边费率**：`fees_bps: {"buy":15,"sell":15}`；
  * 兼容单值：`fees_bps: 15`（解释为单边=15，双边=各 15）；
  * `slippage_bps` 默认 5
* **仓位**：等权或分数加权；最大持仓 `topN`
* **日历**：以上/深合并交易日历
* **指纹**：`data_snapshot_id/code_hash/config_hash/seed`

**VectorbtEngine 的“顺延 = bfill”实现**

1. `price_next_open = open.shift(-1)`
2. 若 `mask_untradable.shift(-1) == True`，将 `price_next_open` 置 `NaN`
3. 对 `price_next_open` **后向填充 `bfill`**，将 `NaN` 段填到**下一可成交日的开盘价**
4. 用 `Portfolio.from_signals(prices=price_next_open_bfilled, ...)` 计算；entries/exits 标注在 `D`
5. 统计输出“拒单次数/顺延天数”

> 如需订单级撮合/部分成交等强约束，改用 **RQAlphaEngine**（对外契约一致）

---

## 9. API 契约（稳定对前端）

**通用**

* 日期：`YYYY-MM-DD`；时区：`Asia/Shanghai`
* 缓存：读接口返回 `Cache-Control: max-age=300` 与 `ETag`

  * **ETag 计算**：`ETag = sha1(data_snapshot_id + normalized_query)`（`normalized_query` 为排序去空白后的 query 串）
* 错误包（统一）：`{ "error": { "code": "InvalidParam", "message": "xxx", "details": {...}? } }`
* 分页：`page, limit`（`page` 从 1 起）

### 9.1 公共模型（Pydantic 摘要）

```python
class PriceRow(BaseModel):
    ts_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    amount: float | None = None
    turnover_rate: float | None = None  # include_basic=true 时出现

class Alert(BaseModel):
    alert_id: str
    dedupe_key: str
    severity: Literal["P1","P2","P3"]
    title: str
    body: str
    tags: list[str] = []
    state: Literal["open","acked","resolved"]
    created_at: datetime

```

### 9.2 Endpoints

#### GET `/api/prices`

* **Query**：`ts_code`(必填, 逗号分隔可多值), `start`, `end`, `adj=none|forward|backward`(默认 backward), `include_basic=true|false`(默认 false)
* **说明**：`adj=backward` 时仅返回复权后的 `open/high/low/close`；`volume/amount` 原样（不复权）。`include_basic=true` 时以 `(ts_code, trade_date)` 左连 `daily_basic`（追加 `turnover_rate` 等）
* **200**：

```json
{
  "adj": "backward",
  "rows": [
    {"ts_code":"000001.SZ","trade_date":"2025-07-01","open":10.23,"high":10.55,"low":10.10,"close":10.40,
     "volume":12345600,"amount":123456789.0},
    {"ts_code":"600000.SH","trade_date":"2025-07-01","open":9.01,"high":9.35,"low":8.97,"close":9.12,
     "volume":9876543,"amount":87654321.0,"turnover_rate":1.20}
  ]
}
```

#### GET `/api/metrics`

* **Query**：`ts_code`, `window`(默认 20), `metrics`（如 `ma,vol_ann,turnover`）, `start`, `end`
* **200**（逐日行，含时间索引）：

```json
{
  "ts_code": "000001.SZ",
  "rows": [
    {"trade_date":"2025-07-01","ma20":10.10,"vol_ann":0.23,"turnover":1.20}
  ]
}
```

#### GET `/api/watchlist`  /  POST `/api/watchlist`

* `GET`：分页 `page,limit`；`POST`：`{"ts_codes":["000001.SZ","600000.SH"]}`

#### GET `/api/universe?month=YYYY-MM`

```json
{
  "month":"2025-07",
  "size":200,
  "rows":[{"ts_code":"000001.SZ","rank":1,"avg_turnover":2.34}]
}
```

#### GET `/api/market/summary?date=YYYY-MM-DD`
* adv_decl 中未涨跌字段统一命名为 unch。

* pct_chg 为小数（例如 0.07 = +7%）。
```json
{
  "date": "2025-07-01",
  "adv_decl": { "adv": 1800, "decl": 2200, "unch": 500 },
  "turnover_total": 1234000000000.0,
  "by_industry": [
    { "industry": "银行", "adv": 20, "decl": 12, "turnover": 123000000000.0, "pct_chg": 0.006 }
  ],
  "top": [
    { "ts_code": "000001.SZ", "pct_chg": 0.07, "turnover": 12000000000.0 }
  ],
  "bottom": [
    { "ts_code": "600000.SH", "pct_chg": -0.06, "turnover": 8000000000.0 }
  ]
}

```

#### GET `/api/signals?date=YYYY-MM-DD&ts_code=...`

```json
{
  "ts_code":"000001.SZ",
  "rows":[{"trade_date":"2025-07-01","p_mom_63d":0.12,"p_rev_5d":-0.02,"p_score":1.30,"vol_ann":0.23,"mask_untradable":false}]
}
```

#### GET `/api/rankings/p_score?date=YYYY-MM-DD&top=20&with_history=true|false`

```json
{
  "date":"2025-07-01",
  "top":[{"ts_code":"000001.SZ","p_score":2.10,"evidence":["mom↑","rev↑","universe∈Top200"]}],
  "history":[
    {"ts_code":"000001.SZ","rows":[{"trade_date":"2025-06-28","p_score":1.95},{"trade_date":"2025-06-29","p_score":2.00}]}
  ]
}
```

#### GET `/api/daily?date=YYYY-MM-DD`

```json
{
  "reco":[{"ts_code":"000001.SZ","score":3.25,"evidence":["mom↑","rev↑","universe∈Top200"],"exit":"max_drawdown_pct=0.10"}],
  "alerts":[{"alert_id":"A1","dedupe_key":"...","severity":"P1","title":"daily_job delayed","body":"...","state":"open"}],
  "changelog":[{"ts_code":"000001.SZ","change":"enter_universe"}]
}
```

#### POST `/api/backtest`

* **Body**：

```json
{
  "universe_id":"top200",
  "start":"2020-01-01","end":"2025-08-01",
  "signals":["p_score"],"ranking":"desc","topN":20,
  "price":"open_next",
  "fees_bps":{"buy":15,"sell":15},     // 兼容单值：fees_bps: 15
  "slippage_bps":5,
  "t_plus_one":true
}
```

* **202**：`{"run_id":"bt_20250811_001"}`

#### GET `/api/backtest/{run_id}`

```json
{
  "run_id":"bt_20250811_001",
  "equity":[{"trade_date":"2025-07-01","nav":1.234}],
  "drawdown":[{"trade_date":"2025-07-01","dd":-0.045}],
  "by_quantile":[{"bucket":"Q1","ret_ann":0.21}],
  "executions":{"rejected":3,"deferred_days":7},
  "fingerprint":{"data_snapshot_id":"...","code_hash":"...","config_hash":"...","seed":123}
}
```

#### GET `/api/status`

```json
{
  "watermarks":[{"table":"prices_daily","last_dt":"2025-08-08","rowcount":1234567,"hash":"abcd..."}],
  "jobs":[{"id":"daily_job","last_run":"2025-08-08T19:25:00+08:00","state":"ok","next_run":"2025-08-09T19:00:00+08:00"}]
}
```

#### GET `/api/alerts`

* **Query**：`page,limit,severity(P1|P2|P3),state(open|acked|resolved),from,to`
* **200**：

```json
{
  "page": 1,
  "limit": 50,
  "total": 123,
  "items": [
    {
      "alert_id": "A1",
      "dedupe_key": "...",
      "severity": "P1",
      "title": "daily_job delayed",
      "body": "...",
      "state": "open",
      "created_at": "2025-08-08T19:35:00+08:00"
    }
  ]
}

```

#### POST `/api/ack`

```json
{"ok":true}
```

---

## 10. 调度、幂等与就绪

* **时区**：`TZ=Asia/Shanghai`（Pydantic Settings 注入）
* **APScheduler**：`SQLAlchemyJobStore(url="sqlite:///data/meta.sqlite")`、`coalesce=true`、`misfire_grace_time=3600`
* **互斥**：文件锁或 `meta.sqlite.locks`（单实例，不并发）
* **错过补跑**：仅补最近 1 个交易日
* **就绪探针**：`daily_job` 前检查主源可用（当日样本数 ≥ Universe 覆盖阈值 95%）
* **幂等键**：`(table, trade_date)`；原子替换 + `watermark` 更新
* **月度 compact**：`month=YYYY-MM`

**默认调度（可配）**

* **19:00** `daily_job()`：拉数→落盘→指标/信号→三件套
* **19:40** `summary_job()`：P2 汇总与推送
* **23:00** `selfcheck_job()`：重跑近 7 天，对比指标差（阈内 PASS）

---

## 11. 观测与告警（Server酱）

* **指标与阈值**

  * **运行/SLO**：`daily_job_deadline`（19:30 未产出 → **P1**）；`selfcheck_pass_rate`（近 7 天）<0.95 → **P2**
  * **数据质量**：`data_freshness` 滞后>1 交易日 → **P1**；`universe_coverage`<95% 或 `missing_ratio`>1% → **P2**
  * **策略产出**：`reco_count < TopN*0.4` → **P2**；`capacity_violation>0` → **P1**
* **去重键**：`dedupe_key = sha1(severity|title|body_key_fields|date)`；抑制窗口 60 分钟（同键只发一次）
* **状态机**：`open → sent → acked → resolved`；发送回执落 `meta.sqlite.alert_sends`
* **路由**：`P1 即时`、`P2 19:40 汇总`、`P3 仅入库`
* **配置示例** `config/alert_rules.yaml`

  ```yaml
  slo:
    daily_job_deadline: "19:30"
    selfcheck_pass_rate_threshold: 0.95
  severity:
    P1: [daily_job_deadline, data_freshness, capacity_violation]
    P2: [universe_coverage, missing_ratio, reco_count]
  routing:
    - when: P1
      notifiers: [serverchan]
    - when: P2
      notifiers: [serverchan]
  dedupe_window_minutes: 60
  summary_time: "19:40"
  ```

---

## 12. 前端规范（Next.js + 图表）

* **SSR 与图表**：ECharts 组件使用 `dynamic(...,{ ssr:false })` 避免水合错误
* **适配层**：`ui/charts/*`：`CandleChart`→ECharts，`Line/Bar`→Recharts（后续可替换实现不动调用）
* **性能**：Watchlist 虚拟滚动；K 线页预拉取 `T-250`；接口分页 + `ETag`
* **可解释性**：推荐卡展示 ≥3 条证据与退出条件

---

## 13. 配置样例

**`.env.sample`**

```
TUSHARE_TOKEN=你的token
SERVERCHAN_SENDKEY=SCUxxxxxxxxxxxx
TZ=Asia/Shanghai
```

**`config/reco.yaml`**

```yaml
topN: 20
hold_days: 10
exit:
  max_drawdown_pct: 0.10
  evidence_reverse: true
ban_list: ["ST", "停牌", "涨跌停"]
```

---

## 14. 安全与合规

* **鉴权**：默认本地；如对外，启用 **API Key**（`X-API-Key`）与 CORS 白名单
* **凭据**：仅 `.env`；日志掩码；定期轮换
* **合规**：仅个人研究用途；遵守数据源 TOS 与频控；禁止对外再分发源数据

---

## 15. 性能与容量（单机）

* **量级**：全市场 \~5000 × 250 交易日/年 × 多表；ZSTD 后数十 GB 量级
* **优化**：列裁剪、谓词下推、`year/month/day` 分区、字典编码、月度 compact
* **内存**：典型查询（近 250 日 × 200 只）常驻 < 1–2 GB；回测按年份/分片并行

---

## 16. 测试与回归

* **金标集**：100 只 × 3 年期 → `/tests/golden/`（期望指标/信号）
* **单测**：Adapters 字段映射、复权计算、日历/时区；Signals 去极值/标准化一致性
* **集成**：`daily_job(dt=固定日)` 全链路；回测曲线与金标阈值（MSE/MaxAE）
* **自检**：`selfcheck_job` 比对近 7 天指标差（阈内 PASS）

---

## 17. 依赖安装（最小可跑）

```bash
pip install fastapi uvicorn[standard] pydantic-settings
pip install duckdb pyarrow>=12 pandas
pip install apscheduler tenacity
pip install tushare akshare
pip install vectorbt numpy numba ta
pip install quantstats empyrical
# 前端
# npx create-next-app@latest ... + tailwind + shadcn/ui
```

---

## 18. 实施阶段与 DoD

### 阶段 A（5–7 天）：数据通道 + 可视化底座

* **交付**：TuShare Adapter（全量首拉+增量）、`prices_daily/daily_basic` 落盘；Watchlist & Stock Detail；`/api/prices /metrics /watchlist`；`daily_job`
* **KR**：收盘后 ≤ **30 分钟** 更新；抽查 3 股指标与后端 SQL 一致

### 阶段 B（4–5 天）：Universe + 市场总览

* **交付**：`/api/universe /api/market/summary` + Dashboard
* **KR**：覆盖率 ≥ **95%**；缺失率 ≤ **1%**

### 阶段 C（3–4 天）：P-Score 榜（观察，不下交易结论）

* **交付**：`signals_daily`（`p_mom_63d/p_rev_5d/p_score/vol_ann`）；`/api/rankings/p_score` + 历史轨迹
* **KR**：评分与肉眼趋势一致；无未来数据错位

### 阶段 X（与 A 同周 +1 天）：观测与告警

* **交付**：SLO/质量采集；Server酱 Notifier；P1 即时、P2 汇总、Ack
* **KR**：日更失败/断档 < **60s** 即达；P2 日报合并；前端可 Ack

### 阶段 D（5–7 天）：T+1 推荐 + 回测 v0

* **交付**：三件套 + 回测页（VectorbtEngine：`open_next` + bfill 顺延）；`/api/daily /api/backtest`
* **KR**：连续 **5 个交易日** 19:30 前产出；3–5 年回测“高>低”单调；禁入零漏

### 阶段 E（可选 5–7 天）：质量因子与校准

* **交付**：`q_quality`、`pq_score`；Calibration（分档未来 20 日单调）
* **KR**：`pq_score` 回撤不劣于 `p_score`；单调性基本成立

**DoD（完成定义）**

* **A**：网页可见自选股核心指标；≤30 分钟更新；三股抽查一致
* **B**：宇宙覆盖 ≥95%，缺失 ≤1%
* **C**：P-Score 榜上线、无未来数据
* **X**：Server酱告警可用；P1 即时、P2 汇总、前端可 Ack
* **D**：三件套 + 回测页；分层“高>低”；禁入零漏
* **E**（可选）：`pq_score` 稳定不弱于 `p_score`；单调性基本成立

---

## 19. 已知限制与风险

* 停牌/涨跌停采用推断口径，存在偏差；后续可引入更精细交易状态字段
* 数据合规：仅个人研究用途，禁止对外再分发
* 单机容量：分钟级或更长历史建议引入对象存储与并行框架

---

## 20. 参考链接

* FastAPI — [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
* DuckDB — [https://duckdb.org/](https://duckdb.org/)
* APScheduler — [https://apscheduler.readthedocs.io/](https://apscheduler.readthedocs.io/)
* vectorbt — [https://vectorbt.dev/](https://vectorbt.dev/)
* QuantStats — [https://github.com/ranaroussi/quantstats](https://github.com/ranaroussi/quantstats)
* Server酱 — [https://sct.ftqq.com/](https://sct.ftqq.com/)
* TuShare Pro — [https://tushare.pro/](https://tushare.pro/)
* AkShare — [https://github.com/akfamily/akshare](https://github.com/akfamily/akshare)
* RQAlpha — [https://github.com/ricequant/rqalpha](https://github.com/ricequant/rqalpha)

---