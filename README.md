# 角色特质抽卡 (Character Trait Draw)

基于 **200 张性格特质方法卡**（96 正面 + 104 负面）的 Claude Code Skill，为角色创作提供灵感和立体化参考。

## 使用场景

- **写小说/剧本** — 需要给角色注入立体性格，但不想从空白开始想
- **TRPG 跑团** — 快速生成 NPC 的性格组合，让每个路人都有记忆点
- **游戏开发** — 角色设计阶段用抽卡激发灵感，避免千篇一律
- **同人创作** — 给原作角色补充"如果他有这个缺点会怎样"的延伸思考
- **写作练习** — 抽一组特质，即兴写一个角色小传

## 数据来源

特质卡片源自编剧/创意写作领域的人物性格特质方法卡，每张卡包含：

| 维度 | 说明 |
|------|------|
| 定义 | 特质的核心含义 |
| 可能成因 | 什么经历会塑造出这个特质 |
| 行为表现 | 约 30 条具体行为描述 |
| 内心独白 | 角色脑海中的声音 |
| 关联情绪 | 该特质常伴随的情绪 |
| 正面价值 | 这个特质的积极面 |
| 负面影响 | 这个特质的消极面 |
| 影视案例 | 经典角色实例 |
| 冲突特质 | 与之矛盾的特质（戏剧张力来源） |
| 克服路径 | （负面特质）如何成长 |
| 考验情境 | （正面特质）什么情况会挑战这个特质 |

## 安装

```bash
git clone https://git.talesofai.com/atou/character-traits.git ~/.claude/skills/character-traits
```

## 四种用法

### 1. 随机抽卡

不给任何描述，随机抽取一组特质组合。

```
/character-traits                    # 默认：4 正 + 2 负
/character-traits --tier supporting  # 配角：3 正 + 1 负
/character-traits --tier minor       # 路人：1 正 + 0 负
```

### 2. 主题匹配

传入简短描述，脚本做关键词匹配后随机选取。

```
/character-traits "一个冷酷的杀手"
```

### 3. 查询单卡

查看某个特质的完整档案。

```
/character-traits "勇敢的"
```

### 4. 推荐分析（--analyze）

给出丰富的角色背景，Claude 会进行语义分析并推荐最匹配的特质组合，附角色弧线建议。

```
/character-traits --analyze "一个从小在孤儿院长大的女孩，被收养后却发现养父另有所图..."
```

## 参数说明

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--positive N` | int | 4 | 正面特质数量 |
| `--negative N` | int | 2 | 负面特质数量 |
| `--tier TIER` | string | major | 角色层级：major / supporting / minor |
| `--no-tension` | flag | - | 关闭冲突张力保证 |
| `--no-category` | flag | - | 关闭跨维度约束 |
| `--no-similar` | flag | - | 关闭相似去重 |
| `--show DEPTH` | string | full | 输出深度：summary / full / compact |
| `--analyze` | flag | - | 输出候选池 JSON，由 Claude 做推荐分析 |

### 角色层级预设

| 层级 | 正面 | 负面 | 适合 |
|------|------|------|------|
| major | 4 | 2 | 主角、反派、重要角色 |
| supporting | 3 | 1 | 配角、导师、盟友 |
| minor | 1 | 0 | 路人、背景板 |

显式传 `--positive` / `--negative` 时会覆盖 tier 预设。

## 抽卡逻辑

- **张力保证**（默认开启）：至少一对正面 + 负面特质互为冲突特质，确保角色有内在矛盾
- **跨维度**（默认开启）：正面特质覆盖至少 2 个性格维度（身份 / 互动 / 成就 / 道德）
- **去重**（默认开启）：跳过 `similar_traits` 高度重叠的特质
- **模糊匹配**：`conflicting_traits` 引用名与实际 key 有微小差异时自动匹配

## 项目结构

```
character-traits/
├── SKILL.md           # Claude Code Skill 定义
├── README.md          # 本文件
├── data/
│   ├── positive.json  # 96 个正面特质
│   └── negative.json  # 104 个负面特质
└── scripts/
    └── draw.py        # 抽卡引擎
```

## License

MIT
