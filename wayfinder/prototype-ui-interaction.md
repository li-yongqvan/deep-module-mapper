---
name: prototype-ui-interaction
wayfinder: prototype
status: closed
---

## Question

双界面工具（现实模块图 + 自定义依赖画布）的交互应该长什么样？用户如何选模块、拖拽、连依赖、触发 AI 评审、查看结果？

## Context

- 界面一：展示代码库真实模块、接口功能、深度分、变更趋势、坏模块标红。
- 界面二：空白画布，用户挑选模块、自主连接依赖、让 AI 评审合理性。
- 技术选型：React Flow（xyflow）做画布层。
- 节点形态：模块盒 + 端口把手。

## Resolution

- 节点形状：**圆角矩形**。
- 端口把手：**小圆点**，位于节点左右两侧。
- 现实视图颜色：**交通灯语义**（绿 = 深模块，黄 = 中，红 = 浅模块/坏模块）。
- 自定义画布颜色：**中性灰蓝色节点**，AI 评审后把有问题的边/节点标红。
- 原型文件：`deep-module-mapper/wayfinder/prototype-ui.html`（一次性 throwaway）。

## Blocking

- `research-market-survey` 已关闭。
- `grilling-interface-criteria` 已关闭。

## Notes

- HITL ticket，用一次性原型（HTML/React 草图）让用户可点击/拖拽感受，已确认。
- 不交付正式代码。
