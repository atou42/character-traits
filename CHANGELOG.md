# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-14

First stable release after extensive data cleanup, engine optimization, and adversarial testing.

### Added

- **张力得分量化** — 每次抽卡自动计算张力得分（0.0~1.0），Full/Summary 模式显示冲突对详情表，Compact 模式显示行内分数
- **`--seed N` 参数** — 固定随机种子，可复现抽卡结果
- **`--no-side-conflict` 参数** — 可关闭同侧冲突避免
- **同侧冲突避免** — 同一侧（正面/负面）不会抽出互为冲突特质的组合（如勇敢+胆怯不同时出现）
- **负面特质输出增强** — 负面卡增加 related_emotions、possible_causes、examples 维度
- **对抗性测试套件** — 27 个测试区块、2924 个断言，覆盖数据完整性、冲突一致性、模糊匹配、边界条件等
- **截断指示符** — 输出截断时显示 `…`，不再无声截断

### Changed

- **`--show summary` 改为真正的简洁视图** — 仅展示 name + definition + 3 behaviors + aspects + tension
- **模糊匹配增加长度比阈值** — 短串长度需 >= 长串的 40%，减少误匹配
- **预计算 `_norm_conflicts`** — load_data() 加载时一次性归一化冲突引用
- **内部重构** — 提取 `_fuzzy_substring()` 和 `_render_trait_card()` 辅助函数

### Fixed

- **清洗 281 条悬空 conflicting_traits 引用** — 全部修正为指向真实存在的特质 key
- **填补 6 张特质卡的空 definition/name_en 字段**
- **修复空候选池和张力计算的边界 bug**

## [0.1.0] - 2026-04-13

Initial release.

### Added

- 基础抽卡引擎 — 200 张性格特质方法卡（96 正面 + 104 负面）
- 四种模式：随机抽卡、主题匹配、查询单卡、推荐分析（--analyze）
- 角色层级预设 — major / supporting / minor
- 跨维度约束、相似去重、张力保证、模糊匹配
- README 和 SKILL.md

[1.0.0]: https://github.com/atou/character-traits/releases/tag/v1.0.0
[0.1.0]: https://github.com/atou/character-traits/releases/tag/v0.1.0
