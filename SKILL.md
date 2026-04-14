---
name: character-traits
description: 角色特质抽卡与生成。从 96 正面 + 104 负面性格特质方法卡中随机抽取或查询，为角色设计提供灵感和立体化参考。当用户提到 抽卡、角色特质、性格设计、character traits、trait draw、角色人设 时触发。v1.0.0
user-invocable: true
argument-hint: "[特质名称 | 角色描述 | --positive N --negative N --tier major|supporting|minor --show summary|full|compact --analyze --seed N --no-side-conflict]"
allowed-tools: [Bash, Read]
---

# 角色特质抽卡 (Character Trait Draw)

基于 200 张性格特质方法卡（96 正面 + 104 负面），为角色创作提供灵感。

## 执行方式

**始终通过脚本执行，不要自己处理 JSON：**

```bash
python3 ~/.claude/skills/character-traits/scripts/draw.py [参数]
```

将 `$ARGUMENTS` 直接传递给脚本。

## 四种模式

### 模式 1：抽卡（默认）
随机抽取一组特质组合。
```bash
python3 ~/.claude/skills/character-traits/scripts/draw.py
python3 ~/.claude/skills/character-traits/scripts/draw.py --tier supporting
```

### 模式 2：主题匹配
传入简短描述，脚本做关键词匹配后随机选取。
```bash
python3 ~/.claude/skills/character-traits/scripts/draw.py "一个冷酷的杀手"
```

### 模式 3：查询单卡
查看某个特质的完整档案。
```bash
python3 ~/.claude/skills/character-traits/scripts/draw.py "勇敢的"
```

### 模式 4：推荐分析（`--analyze`）
用户给出丰富的角色背景，由 Claude 进行语义分析和推荐。**这是两步流程：**

**Step 1** — 获取候选池（脚本输出 JSON）：
```bash
python3 ~/.claude/skills/character-traits/scripts/draw.py --analyze "角色背景描述..."
```
脚本会输出 ~16 个正面 + ~8 个负面候选特质的完整 JSON，包含所有维度数据。

**Step 2** — Claude 基于用户提供的角色背景，逐个分析候选特质：
- 哪些特质与角色的经历、动机、矛盾高度契合？为什么？
- 哪些特质组合能产生最有戏剧张力的矛盾？
- 推荐最终的特质组合（遵循 tier 默认数量），每个附带推荐理由
- 基于推荐的负面特质，给出角色弧线方向建议

**输出格式：**
```
## 角色特质推荐分析

### 角色解读
[基于用户背景的 2-3 句核心解读]

### 推荐正面特质
**1. {name_cn}** ({name_en})
> {definition}
- **推荐理由**：[基于角色背景的具体分析，不是泛泛而谈]
- **角色体现**：[这个特质在角色身上会如何表现]

**2. ...**

### 推荐负面特质
**1. {name_cn}** ({name_en})
> {definition}
- **推荐理由**：...
- **张力**：⚡ 与「{正面特质}」形成 [具体矛盾描述]
- **克服路径**：{how_to_overcome 提取 + 结合角色定制}

### 角色弧线建议
[基于特质组合的 2-3 条成长方向建议]
```

**判断何时使用 `--analyze`：**
- 用户提供了角色的背景故事、性格描述、成长经历等丰富信息 → 用 `--analyze`
- 用户只给了简短关键词（如"冷酷的杀手"） → 用模式 2
- 用户没给描述 → 用模式 1

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--positive N` | int | 4 | 正面特质数量 |
| `--negative N` | int | 2 | 负面特质数量 |
| `--tier TIER` | string | major | 角色层级：major / supporting / minor |
| `--no-tension` | flag | off | 关闭冲突张力保证 |
| `--no-category` | flag | off | 关闭跨维度约束 |
| `--no-similar` | flag | off | 关闭相似去重 |
| `--show DEPTH` | string | full | 输出深度：summary / full / compact |
| `--no-side-conflict` | flag | off | 关闭同侧冲突避免 |
| `--seed N` | int | None | 固定随机种子，可复现结果 |
| `--analyze` | flag | off | 输出候选池 JSON（模式 4） |

### character_tier 预设

tier 设置默认 count，显式传 `--positive`/`--negative` 时覆盖：

- **major**（主角）：4 正 + 2 负
- **supporting**（配角）：3 正 + 1 负
- **minor**（小角色）：1 正 + 0 负

## 注意事项

- 模式 1/2/3 的脚本输出直接展示给用户，不要二次加工
- 模式 4 需要调用脚本后，Claude 自己做语义分析和推荐，输出格式化的推荐报告
- 默认每次调用结果不同；可用 `--seed N` 固定种子复现结果
- 不要编造特质数据
