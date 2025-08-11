# PandaAlpha · 阶段 A 执行清单（ToDo）

> 范围：A-0 ～ A-4（数据通道 + 可视化底座）。每条包含可操作子任务、产出、验收（KR/DoD）与示例命令。

---

## 总体 KR（阶段 A）

- [ ] ≤ 收盘后 30 分钟完成更新并在页面可见
- [ ] 抽查 3 股：前/后端指标一致（MA、vol_ann、换手）
- [ ] `/api/status` 能展示“日更成功/失败”与水位线

---

## 日程建议（可微调）

- Day 1：A-0 项目骨架与环境
- Day 2-3：A-1 数据适配器（首拉 + 增量）
- Day 4：A-2 指标计算（服务端即时）
- Day 5：A-3 API 三端点
- Day 6-7：A-4 前端 Watchlist & Stock Detail + 联调与验收

---

## A-0 项目骨架与环境（0.5 天）

- [ ] 目录与依赖
  - [ ] 创建后端骨架：`app/main.py`、`app/scheduler.py`、`app/settings.py`、`app/api/__init__.py`
  - [ ] 数据与配置目录：`data/`（`parquet/`、`meta.sqlite` 占位）、`config/`、`doc/`
  - [ ] `.env.sample`（`TUSHARE_TOKEN`、`SERVERCHAN_SENDKEY`、`TZ=Asia/Shanghai`）
  - [ ] 最小依赖（见 §17）：`requirements.txt` / `uv.lock`
- [ ] 基础端点
  - [ ] `GET /health` → 200
  - [ ] `GET /api/status` → 返回空的 `watermarks` 与 `jobs` 列表
- [ ] 本地起服
  - [ ] `uvicorn app.main:app --reload` 可启动

验收（DoD）
- 起服无报错；`/health` 与 `/api/status` 200 且契约字段齐全。

命令示例
```bash
uvicorn app.main:app --reload
curl -s http://127.0.0.1:8000/health | jq .
curl -s http://127.0.0.1:8000/api/status | jq .
```

---

## A-1 数据适配器（TuShare 主源；AkShare 备源）（1.5–2 天）

- [ ] TuShare 适配器（模块：`app/adapters/tushare_adapter.py`）
  - [ ] 拉取：`trade_cal`、`daily`、`adj_factor`、`daily_basic`、`stock_basic`
  - [ ] 频控/重试：限速表 + `tenacity` 指数退避（最多 5 次）
  - [ ] 增量：`trade_cal` + `watermark.last_dt` 游标；首拉全量，其后仅补新增
  - [ ] 失败补偿：`meta.sqlite.fail_queue`（endpoint/params/retries/last_error）
- [ ] 落盘（分区 Parquet，`pyarrow>=12`）
  - [ ] 路径：`data/parquet/<table>/year=YYYY/month=MM/day=DD/part-*.parquet`
  - [ ] 压缩/编码：`ZSTD`、字典编码、行组 128–256MB，BloomFilter(`ts_code`)
  - [ ] 幂等写入：`*.parquet.tmp` → 覆盖率/行数校验 → 原子 rename
  - [ ] 更新 `data/watermark.parquet`（`table,last_dt,rowcount,hash`）
  - [ ] 月度 compact（合并小文件）
- [ ] 备源兜底（AkShare）：行业/缺口数据兜底（可延后至 B 阶段细化）
- [ ] 调度接入：`APScheduler` 单任务 `daily_job()`（19:00）

验收（KR/DoD）
- 任选四标的近 1 年数据完整；DuckDB 分区裁剪有效；`watermark.parquet` 正确更新。

命令示例
```bash
python -m app.scheduler daily_job --date 2025-08-01
duckdb -c "SELECT COUNT(*) FROM parquet_scan('data/parquet/prices_daily/year=2025/**') WHERE month=8;" | cat
```

---

## A-2 指标计算（服务端即时）（1 天）

- [ ] 指标模块：`app/metrics/*`
  - [ ] MA5/10/20（后复权 `close`）
  - [ ] `vol_ann = std(daily_ret) * sqrt(252)`（命名统一为 `vol_ann`）
  - [ ] 换手：左连 `daily_basic.turnover_rate`（不持久化）
  - [ ] 去极值/标准化留待 C 阶段（信号持久化）
- [ ] 一致性校验
  - [ ] 随机 3 股：DuckDB SQL vs Pandas 计算一致（容差内）

验收（DoD）
- 模块函数可被 `/api/metrics` 调用；抽查 3 股一致。

---

## A-3 API：`/api/prices` `/api/metrics` `/api/watchlist`（0.5–1 天）

- [ ] 契约与缓存
  - [ ] 统一分页 `page,limit`；错误包 `{error:{code,message,details?}}`
  - [ ] `Cache-Control: max-age=300` 与 `ETag = sha1(data_snapshot_id + normalized_query)`
  - [ ] 多标的 `ts_code`：拆分→去重→排序后纳入 `normalized_query`
- [ ] `/api/prices`
  - [ ] 支持 `adj=none|forward|backward`（默认 backward）：仅 `open/high/low/close` 做复权；`volume/amount` 原样
  - [ ] `include_basic=true` 时左连 `daily_basic`（追加 `turnover_rate`）
- [ ] `/api/metrics`
  - [ ] `window`（默认 20）、`metrics`（如 `ma,vol_ann,turnover`）、`start/end`
- [ ] `/api/watchlist`（GET/POST）
  - [ ] `watchlist` 表落 `meta.sqlite`；支持分页与覆盖写入

验收（KR/DoD）
- 本地小样 P95 < 150ms；契约返回字段与 `requirement.md §9` 对齐。

---

## A-4 前端：Watchlist & Stock Detail（1.5–2 天）

- [ ] 工程化
  - [ ] 创建 Next.js + Tailwind + shadcn/ui
  - [ ] ECharts 组件 `dynamic(...,{ ssr:false })`，避免水合错误
- [ ] Watchlist 页
  - [ ] 表格列：价/涨跌幅/量/换手/MA/`vol_ann`；虚拟滚动
  - [ ] 分页 + `ETag` 缓存
- [ ] Stock Detail 页
  - [ ] K 线 + MA + 量柱 + 十字线 + dataZoom
  - [ ] 预拉取近 `T-250` 数据

验收（KR/DoD）
- 与后端联调通过；≤30 分钟内可见日更；三股抽查与后端一致。

---

## 运行与调度

- [ ] `APScheduler` 配置：`SQLAlchemyJobStore(url="sqlite:///data/meta.sqlite")`、`TZ=Asia/Shanghai`、`coalesce=true`、`misfire_grace_time=3600`
- [ ] 计划任务：
  - [ ] 19:00 `daily_job()`：拉数→落盘→指标/信号→三件套（A 阶段输出前两步 + 指标供查询）
- [ ] `/api/status` 展示 `watermarks` 与 `jobs`（下一次/上一次运行时间与状态）

---

## 所需信息/凭据

- [ ] TuShare Token（必需）：`.env` 中 `TUSHARE_TOKEN`
- [ ] Server酱 SendKey（可等到 X 阶段）：`.env` 中 `SERVERCHAN_SENDKEY`

---

## 风险与回退

- 主源限流/断档：加入指数退避与失败补偿；必要时切 AkShare 兜底
- 小文件过多：月度 compact；控制行组大小；列裁剪 + 谓词下推

---

## 验收清单（最终打勾）

- [ ] 页面可见更新 ≤30 分钟
- [ ] 三股抽查一致
- [ ] `/api/status` 能展示“日更成功/失败”


