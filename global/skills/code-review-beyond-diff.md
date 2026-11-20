---
type: skill
name: code-review-beyond-diff
description: 代码审查视角：看改动波及的未改文件，按 must/should/nice 排序，shortcut 注释收成账本
metadata:
  domain: engineering
  tools: ["read_file", "search_files", "terminal"]
  success_count: 1
  tags: ["code", "review", "audit", "ponytail"]
  author: xskill
  created: 2026-10-18
  updated: 2026-10-18
---

## 情境

只读 diff 的审查会漏掉最关键的一类问题：改动重命名了字段 / 改了函数签名，而某个没被改的文件还在用旧约定，线上崩。

## 审查动作

1. 先读改动**波及到**的文件，不只 diff。字段改名就搜全仓旧名；签名改动就找所有调用点。
2. 按"会被叫起来修的人"的视角问四件事，每条发现都要写全：
   - 这段代码在做什么
   - 哪里会坏（有没有真实触发路径）
   - 怎么修
   - 不修会怎样
3. 分级排序：must fix / should fix / nice to have。只给清单不给顺序等于没审。
4. 全仓审计另外做：先建图（入口点、数据怎么流、预期负载），再排序"先修哪个"。

## 检查面

bug、安全、真实负载下的行为、缺测试的风险路径、慢路径、能删的东西。

## 债务账本

代码里刻意走的捷径用固定注释词标出（如 `shortcut:`）+ 何时该回来。定期把这些注释收成账本，否则"以后再说"等于"永远不说"。

## 来源

ponytail 的 /ponytail-review、/ponytail-audit、/ponytail-debt（MIT）。其"100% 命中植入问题"的对比数字来自作者自测基准，不作证据。
