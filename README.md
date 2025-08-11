# PandaAlpha

![PandaAlpha Logo](png/logo.png)

## 项目简介

PandaAlpha 是一个个人量化投资分析与决策支持系统，专注于 A 股市场分析。本系统提供实时数据获取、指标计算与可视化、量化策略回测以及 AI 辅助分析等功能。

## 核心功能

- 📊 实时数据获取（股价、成交量、换手率、基本面指标等）
- 📈 指标计算与可视化（价量指标、核心因子）
- 🔄 量化策略回测（验证指标有效性）
- 🤖 AI 辅助分析（结合传统量化与大模型给出综合评价）
- 🔔 告警通知（触发条件时推送消息）

## 技术栈

- 后端：Python + FastAPI
- 数据存储：Parquet + DuckDB
- 前端：Next.js + Tailwind + shadcn/ui
- 图表：ECharts + Recharts
- 回测引擎：vectorbt