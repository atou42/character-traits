#!/usr/bin/env python3
"""角色特质抽卡脚本 — 从正面/负面特质卡中随机抽取组合"""

import json
import random
import sys
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")

VALID_CATS = {'身份', '互动', '成就', '道德', '道理'}

TIER_PRESETS = {
    "major":      {"positive": 4, "negative": 2},
    "supporting": {"positive": 3, "negative": 1},
    "minor":      {"positive": 1, "negative": 0},
}


def load_data():
    with open(os.path.join(DATA_DIR, "positive.json"), encoding="utf-8") as f:
        pos = json.load(f)
    with open(os.path.join(DATA_DIR, "negative.json"), encoding="utf-8") as f:
        neg = json.load(f)
    # Pre-compute normalized conflicts for every trait (cached)
    for d in (pos, neg):
        for k in d:
            d[k]["_norm_conflicts"] = _normalize_conflicts(d[k].get("conflicting_traits", []))
    return pos, neg


def parse_args(argv):
    """Parse CLI arguments into config dict."""
    config = {
        "positive_count": None,
        "negative_count": None,
        "character_tier": "major",
        "ensure_tension": True,
        "cross_category": True,
        "avoid_similar": True,
        "avoid_same_side_conflict": True,
        "show_depth": "full",
        "query": None,
        "analyze": False,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--positive" and i + 1 < len(argv):
            config["positive_count"] = int(argv[i + 1])
            i += 2
        elif arg == "--negative" and i + 1 < len(argv):
            config["negative_count"] = int(argv[i + 1])
            i += 2
        elif arg == "--tier" and i + 1 < len(argv):
            config["character_tier"] = argv[i + 1]
            i += 2
        elif arg == "--show" and i + 1 < len(argv):
            config["show_depth"] = argv[i + 1]
            i += 2
        elif arg == "--no-tension":
            config["ensure_tension"] = False
            i += 1
        elif arg == "--no-category":
            config["cross_category"] = False
            i += 1
        elif arg == "--no-similar":
            config["avoid_similar"] = False
            i += 1
        elif arg == "--no-side-conflict":
            config["avoid_same_side_conflict"] = False
            i += 1
        elif arg == "--analyze":
            config["analyze"] = True
            i += 1
        elif not arg.startswith("--"):
            config["query"] = arg if config["query"] is None else config["query"] + " " + arg
            i += 1
        else:
            i += 1

    # Apply tier presets (explicit count overrides)
    tier = config["character_tier"]
    if tier in TIER_PRESETS:
        if config["positive_count"] is None:
            config["positive_count"] = TIER_PRESETS[tier]["positive"]
        if config["negative_count"] is None:
            config["negative_count"] = TIER_PRESETS[tier]["negative"]

    return config


def fuzzy_match(name, target_dict):
    """Match a trait name to actual keys, allowing minor differences."""
    if name in target_dict:
        return name
    for key in target_dict:
        if name in key or key in name:
            return key
    return None


def _normalize_conflicts(conflicts):
    """Clean up conflicting_traits: join split entries, skip junk."""
    result = []
    skip_next = False
    for i, c in enumerate(conflicts):
        if skip_next:
            skip_next = False
            continue
        # Skip single-char noise like '的'
        if len(c) <= 1:
            # Check if this is a split: previous + this = real trait name
            if result and result[-1] + c in ('有道德的', '胆怯的', '负责的'):
                result[-1] = result[-1] + c
                continue
            continue
        # Check if next entry is a continuation split (e.g. '胆怯' + '的')
        if i + 1 < len(conflicts) and len(conflicts[i + 1]) == 1:
            combined = c + conflicts[i + 1]
            if len(combined) >= 3:
                result.append(combined)
                skip_next = True
                continue
        result.append(c)
    return result


def _cross_conflicts(pos_keys, neg_keys, pos, neg):
    """Find all cross-side conflict pairs between positive and negative traits.

    Returns a list of dicts: {"pos": str, "neg": str, "direction": "pos→neg"|"neg→pos"|"bidirectional"}
    """
    pairs = []
    for pk in pos_keys:
        p_conflicts = pos[pk].get("_norm_conflicts", [])
        for nk in neg_keys:
            fwd = False
            rev = False
            # Forward: positive's conflicts mention this negative
            if nk in p_conflicts:
                fwd = True
            else:
                for c in p_conflicts:
                    if len(c) >= 2 and (c in nk or nk in c):
                        fwd = True
                        break
            # Reverse: negative's conflicts mention this positive
            n_conflicts = neg[nk].get("_norm_conflicts", [])
            if pk in n_conflicts:
                rev = True
            else:
                for c in n_conflicts:
                    if len(c) >= 2 and (c in pk or pk in c):
                        rev = True
                        break
            if fwd or rev:
                direction = "bidirectional" if (fwd and rev) else ("pos→neg" if fwd else "neg→pos")
                pairs.append({"pos": pk, "neg": nk, "direction": direction})
    return pairs


def calc_tension(pos_keys, neg_keys, pos, neg):
    """Calculate tension score and conflict details for a draw result.

    Returns {"score": float, "pairs": list, "max_possible": int}
    score = actual_conflict_pairs / max_possible_pairs (0.0 ~ 1.0)
    """
    max_possible = len(pos_keys) * len(neg_keys)
    if max_possible == 0:
        return {"score": 0.0, "pairs": [], "max_possible": 0}
    pairs = _cross_conflicts(pos_keys, neg_keys, pos, neg)
    score = len(pairs) / max_possible
    return {"score": round(score, 2), "pairs": pairs, "max_possible": max_possible}


def has_conflict(key, existing_keys, trait_dict):
    """Check if key conflicts with any key in existing_keys via conflicting_traits."""
    conflicts = trait_dict[key].get("_norm_conflicts", [])
    for ek in existing_keys:
        # Direct match
        if ek in conflicts:
            return True
        # Fuzzy: only if conflict substring is >= 2 chars and is substantial part of ek
        for c in conflicts:
            if len(c) >= 2 and (c in ek or ek in c):
                return True
        # Reverse: existing key's conflicts mention this key
        ek_conflicts = trait_dict[ek].get("_norm_conflicts", [])
        if key in ek_conflicts:
            return True
        for ec in ek_conflicts:
            if len(ec) >= 2 and (ec in key or key in ec):
                return True
    return False


def find_trait(query, pos, neg):
    """Find a specific trait by name (exact or fuzzy)."""
    # Exact match
    if query in pos:
        return pos[query], "positive"
    if query in neg:
        return neg[query], "negative"
    # English match
    q_lower = query.lower()
    for k, v in pos.items():
        if v.get("name_en", "").lower() == q_lower:
            return v, "positive"
    for k, v in neg.items():
        if v.get("name_en", "").lower() == q_lower:
            return v, "negative"
    # Fuzzy
    for k in pos:
        if query in k or k in query:
            return pos[k], "positive"
    for k in neg:
        if query in k or k in query:
            return neg[k], "negative"
    return None, None


def theme_match(query, pos, neg):
    """Score traits against a theme description, return sorted lists."""
    def score(card):
        text = " ".join([
            card.get("definition", ""),
            card.get("positive_aspects", ""),
            card.get("negative_aspects", ""),
            " ".join(card.get("related_behaviors", [])[:10]),
        ])
        query_chars = set(query)
        hits = sum(1 for c in query_chars if c in text)
        # Also check bigram overlap
        query_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', query))
        text_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', text))
        word_hits = len(query_words & text_words)
        return hits + word_hits * 5

    pos_scored = sorted(pos.items(), key=lambda x: score(x[1]), reverse=True)
    neg_scored = sorted(neg.items(), key=lambda x: score(x[1]), reverse=True)
    return pos_scored, neg_scored


def draw_from_pool(keys, trait_dict, count, config, initial_chosen=None):
    """Draw N traits from a pool, applying same-side conflict and similar avoidance."""
    if count <= 0 or not keys:
        return []

    initial = list(initial_chosen) if initial_chosen else []
    chosen = list(initial)  # track for conflict checks, but we'll slice them off at the end
    candidates = list(keys)
    random.shuffle(candidates)

    for k in candidates:
        if len(chosen) >= count:
            break
        # Same-side conflict check
        if config["avoid_same_side_conflict"] and has_conflict(k, chosen, trait_dict):
            continue
        # Similar avoidance check
        if config["avoid_similar"]:
            skip = False
            sims = trait_dict[k].get("similar_traits", [])
            for ck in chosen:
                for s in sims:
                    if len(s) >= 2 and (s in ck or ck in s):
                        skip = True
                        break
                if skip:
                    break
                ck_sims = trait_dict[ck].get("similar_traits", [])
                for s in ck_sims:
                    if len(s) >= 2 and (s in k or k in s):
                        skip = True
                        break
                if skip:
                    break
            if skip:
                continue
        chosen.append(k)

    # Fallback: if we couldn't fill, just take remaining
    if len(chosen) < count:
        remaining = [k for k in keys if k not in chosen]
        chosen.extend(remaining[:count - len(chosen)])

    # Only return newly chosen items (exclude initial_chosen that were pre-seeded)
    new_picks = [k for k in chosen if k not in initial]
    # Fallback for unfilled: try remaining keys with conflict check
    if len(new_picks) < count:
        remaining = [k for k in keys if k not in chosen]
        for k in remaining:
            if len(new_picks) >= count:
                break
            if config.get("avoid_same_side_conflict") and has_conflict(k, chosen, trait_dict):
                continue
            new_picks.append(k)
            chosen.append(k)
    return new_picks[:count]


def draw_random(pos, neg, config):
    """Draw a random trait combination."""
    pos_count = config["positive_count"]
    neg_count = config["negative_count"]

    # Draw positives with retry for cross-category
    pos_keys = []
    all_pos = list(pos.keys())
    for _ in range(100):
        sampled = draw_from_pool(all_pos, pos, pos_count, config)
        if config["cross_category"] and pos_count >= 2:
            cats = set()
            for k in sampled:
                for c in pos[k].get("category", []):
                    if c in VALID_CATS:
                        cats.add(c)
            if len(cats) < 2:
                random.shuffle(all_pos)
                continue
        pos_keys = sampled
        break

    if not pos_keys:
        pos_keys = draw_from_pool(all_pos, pos, pos_count, config)

    # Draw negatives
    neg_keys = []

    # Tension: pick one negative from positive's conflicting_traits
    # Try each positive until we find one that has a matching negative conflict
    if config["ensure_tension"] and neg_count > 0 and pos_keys:
        for pk in pos_keys:
            conflicts = list(pos[pk].get("_norm_conflicts", []))
            random.shuffle(conflicts)
            for ct in conflicts:
                match = fuzzy_match(ct, neg)
                if match:
                    neg_keys.append(match)
                    break
            if neg_keys:
                break

    # Fill remaining negatives with same-side conflict avoidance
    remaining = [k for k in neg if k not in neg_keys]
    need = neg_count - len(neg_keys)
    if need > 0:
        extra = draw_from_pool(remaining, neg, need, config, initial_chosen=neg_keys)
        neg_keys.extend(extra)

    return pos_keys, neg_keys


def draw_themed(query, pos, neg, config):
    """Draw traits matching a theme description."""
    pos_count = config["positive_count"]
    neg_count = config["negative_count"]

    pos_scored, neg_scored = theme_match(query, pos, neg)

    # Pick from top candidates with some randomness
    top_n = min(max(pos_count * 3, 10), len(pos_scored))
    candidates = [k for k, _ in pos_scored[:top_n]]
    pos_keys = draw_from_pool(candidates, pos, pos_count, config)

    top_n_neg = min(max(neg_count * 3, 10), len(neg_scored))
    neg_candidates = [k for k, _ in neg_scored[:top_n_neg]]

    neg_keys = []
    # Try tension first — check each positive until one has a matching negative
    if config["ensure_tension"] and neg_count > 0 and pos_keys:
        for pk in pos_keys:
            conflicts = pos[pk].get("_norm_conflicts", [])
            for ct in conflicts:
                match = fuzzy_match(ct, neg)
                if match and match in neg_candidates:
                    neg_keys.append(match)
                    break
            if neg_keys:
                break

    remaining = [k for k in neg_candidates if k not in neg_keys]
    need = neg_count - len(neg_keys)
    if need > 0:
        extra = draw_from_pool(remaining, neg, need, config, initial_chosen=neg_keys)
        neg_keys.extend(extra)

    return pos_keys, neg_keys


def format_output(pos, neg, pos_keys, neg_keys, show_depth):
    """Format the draw result as markdown."""
    lines = ["## 角色特质组合\n"]

    # Compact mode: show inline tension score in header
    if show_depth == "compact" and pos_keys and neg_keys:
        tension = calc_tension(pos_keys, neg_keys, pos, neg)
        lines.append(f"**张力**：{tension['score']}\n")

    lines.append("### 正面特质\n")
    for i, k in enumerate(pos_keys, 1):
        t = pos[k]
        if show_depth == "compact":
            lines.append(f"**{t['name_cn']}** ({t['name_en']}) — {t['definition']}")
            continue

        lines.append(f"**{i}. {t['name_cn']}** ({t['name_en']})")
        lines.append(f"> {t['definition']}\n")

        behaviors = t.get("related_behaviors", [])[:3]
        if behaviors:
            lines.append(f"- **行为示例**：{'；'.join(behaviors)}")

        pa = t.get("positive_aspects", "")
        na = t.get("negative_aspects", "")
        if show_depth == "full":
            lines.append(f"- **正面**：{pa}")
            lines.append(f"- **负面**：{na}")
            thoughts = t.get("related_thoughts", [])[:3]
            if thoughts:
                lines.append(f"- **内心独白**：{'；'.join(thoughts)}")
            emotions = t.get("related_emotions", [])
            if emotions:
                lines.append(f"- **关联情绪**：{'、'.join(emotions)}")
            causes = t.get("possible_causes", [])[:3]
            if causes:
                lines.append(f"- **可能成因**：{'；'.join(causes)}")
            ex = t.get("examples", "")
            if ex:
                lines.append(f"- **影视案例**：{ex[:200]}")
            scenarios = t.get("challenging_scenarios", [])
            if scenarios:
                lines.append(f"- **考验情境**：{'；'.join(scenarios[:3])}")
        else:
            lines.append(f"- **正面**：{pa[:100]}")
            lines.append(f"- **负面**：{na[:100]}")

        cats = [c for c in t.get("category", []) if c in VALID_CATS]
        if cats:
            lines.append(f"- **维度**：{'、'.join(cats)}")
        lines.append("")

    if neg_keys:
        lines.append("### 负面特质\n")
        for i, k in enumerate(neg_keys, 1):
            t = neg[k]
            if show_depth == "compact":
                lines.append(f"**{t['name_cn']}** ({t['name_en']}) — {t['definition']}")
                continue

            lines.append(f"**{i}. {t['name_cn']}** ({t['name_en']})")
            lines.append(f"> {t['definition']}\n")

            behaviors = t.get("related_behaviors", [])[:3]
            if behaviors:
                lines.append(f"- **行为示例**：{'；'.join(behaviors)}")

            pa = t.get("positive_aspects", "")
            na = t.get("negative_aspects", "")
            if show_depth == "full":
                lines.append(f"- **正面**：{pa}")
                lines.append(f"- **负面**：{na}")
                thoughts = t.get("related_thoughts", [])[:3]
                if thoughts:
                    lines.append(f"- **内心独白**：{'；'.join(thoughts)}")
                emotions = t.get("related_emotions", [])
                if emotions:
                    lines.append(f"- **关联情绪**：{'、'.join(emotions)}")
                causes = t.get("possible_causes", [])[:3]
                if causes:
                    lines.append(f"- **可能成因**：{'；'.join(causes)}")
                ex = t.get("examples", "")
                if ex:
                    lines.append(f"- **影视案例**：{ex[:200]}")
                ho = t.get("how_to_overcome", "")
                if ho:
                    lines.append(f"- **克服路径**：{ho}")
            else:
                lines.append(f"- **正面**：{pa[:100]}")
                lines.append(f"- **负面**：{na[:100]}")
                ho = t.get("how_to_overcome", "")
                if ho:
                    lines.append(f"- **克服路径**：{ho[:100]}")

            # Check tension with positive traits (fuzzy-aware)
            conflicts_with_pos = []
            n_conflicts = t.get("_norm_conflicts", [])
            for pk in pos_keys:
                found = False
                if pk in n_conflicts:
                    found = True
                else:
                    for c in n_conflicts:
                        if len(c) >= 2 and (c in pk or pk in c):
                            found = True
                            break
                if not found:
                    p_conflicts = pos[pk].get("_norm_conflicts", [])
                    if k in p_conflicts:
                        found = True
                    else:
                        for c in p_conflicts:
                            if len(c) >= 2 and (c in k or k in c):
                                found = True
                                break
                if found:
                    conflicts_with_pos.append(pk)
            if conflicts_with_pos:
                lines.append(f"- **张力**：⚡ 与「{'、'.join(conflicts_with_pos)}」形成张力")
            lines.append("")

    # Arc hints
    if show_depth != "compact" and neg_keys:
        lines.append("### 角色弧线提示\n")
        for k in neg_keys:
            t = neg[k]
            ho = t.get("how_to_overcome", "")
            if ho:
                name = t['name_cn'].rstrip('的')
                lines.append(f"- **{name}的克服方向**：{ho[:150]}")
        # Challenging scenarios from first positive trait
        if pos_keys:
            scenarios = pos[pos_keys[0]].get("challenging_scenarios", [])[:2]
            if scenarios:
                name = pos[pos_keys[0]]['name_cn'].rstrip('的')
                lines.append(f"- **{name}的考验情境**：{'；'.join(scenarios)}")

    # Tension summary
    if pos_keys and neg_keys and show_depth != "compact":
        tension = calc_tension(pos_keys, neg_keys, pos, neg)
        lines.append("### 张力指标\n")
        n_conflicts = len(tension["pairs"])
        max_p = tension["max_possible"]
        lines.append(f"**张力得分**：{tension['score']}（{n_conflicts}/{max_p} 对冲突）\n")
        if tension["pairs"]:
            lines.append("| 正面 | 负面 | 方向 |")
            lines.append("|------|------|------|")
            for p in tension["pairs"]:
                dir_label = "⚡↔" if p["direction"] == "bidirectional" else "⚡→" if p["direction"] == "pos→neg" else "←⚡"
                lines.append(f"| {p['pos']} | {p['neg']} | {dir_label} |")
            lines.append("")
        lines.append("_0.0 = 无张力，1.0 = 全面对立。推荐区间 0.25–0.5_")

    return "\n".join(lines)


def format_single_card(card, card_type):
    """Format a single trait card for display."""
    lines = [f"## {card['name_cn']} ({card.get('name_en', '')})\n"]
    lines.append(f"> {card.get('definition', '')}\n")

    lines.append(f"### 基本信息")
    if card_type == "positive":
        cats = [c for c in card.get("category", []) if c in VALID_CATS]
        if cats:
            lines.append(f"- **维度**：{'、'.join(cats)}")
    sims = card.get("similar_traits", [])
    if sims:
        lines.append(f"- **相似特质**：{'、'.join(sims[:5])}")
    causes = card.get("possible_causes", [])
    if causes:
        lines.append(f"- **可能成因**：")
        for c in causes[:5]:
            lines.append(f"  - {c}")

    lines.append(f"\n### 行为表现")
    for b in card.get("related_behaviors", [])[:8]:
        lines.append(f"- {b}")

    lines.append(f"\n### 内心世界")
    for t in card.get("related_thoughts", [])[:5]:
        lines.append(f"- {t}")
    emotions = card.get("related_emotions", [])
    if emotions:
        lines.append(f"\n**关联情绪**：{'、'.join(emotions)}")

    lines.append(f"\n### 正反面分析")
    lines.append(f"**正面**：{card.get('positive_aspects', '')}")
    lines.append(f"\n**负面**：{card.get('negative_aspects', '')}")

    if card_type == "negative":
        ho = card.get("how_to_overcome", "")
        if ho:
            lines.append(f"\n**克服路径**：{ho}")

    ex = card.get("examples", "")
    if ex:
        lines.append(f"\n### 影视案例\n{ex}")

    conflicts = card.get("conflicting_traits", [])
    if conflicts:
        lines.append(f"\n### 冲突特质\n{'、'.join(conflicts[:10])}")

    if card_type == "positive":
        scenarios = card.get("challenging_scenarios", [])
        if scenarios:
            lines.append(f"\n### 考验情境")
            for s in scenarios:
                lines.append(f"- {s}")

    return "\n".join(lines)


def format_candidates_json(pos, neg, pos_keys, neg_keys):
    """Output candidate pool as structured JSON for analyze mode."""
    result = {"positive": [], "negative": []}
    for k in pos_keys:
        t = pos[k]
        result["positive"].append({
            "key": k,
            "name_cn": t["name_cn"],
            "name_en": t.get("name_en", ""),
            "definition": t.get("definition", ""),
            "category": [c for c in t.get("category", []) if c in VALID_CATS],
            "positive_aspects": t.get("positive_aspects", ""),
            "negative_aspects": t.get("negative_aspects", ""),
            "possible_causes": t.get("possible_causes", [])[:5],
            "related_behaviors": t.get("related_behaviors", [])[:8],
            "related_thoughts": t.get("related_thoughts", [])[:3],
            "related_emotions": t.get("related_emotions", []),
            "examples": t.get("examples", "")[:300],
            "challenging_scenarios": t.get("challenging_scenarios", []),
            "conflicting_traits": t.get("conflicting_traits", []),
            "similar_traits": t.get("similar_traits", []),
        })
    for k in neg_keys:
        t = neg[k]
        result["negative"].append({
            "key": k,
            "name_cn": t["name_cn"],
            "name_en": t.get("name_en", ""),
            "definition": t.get("definition", ""),
            "positive_aspects": t.get("positive_aspects", ""),
            "negative_aspects": t.get("negative_aspects", ""),
            "possible_causes": t.get("possible_causes", [])[:5],
            "related_behaviors": t.get("related_behaviors", [])[:8],
            "related_thoughts": t.get("related_thoughts", [])[:3],
            "related_emotions": t.get("related_emotions", []),
            "examples": t.get("examples", "")[:300],
            "how_to_overcome": t.get("how_to_overcome", ""),
            "conflicting_traits": t.get("conflicting_traits", []),
            "similar_traits": t.get("similar_traits", []),
        })
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    config = parse_args(sys.argv[1:])
    pos, neg = load_data()

    query = config.get("query")

    # Mode 4: Analyze — output top candidates as JSON for Claude to reason over
    if config["analyze"] and query:
        pos_scored, neg_scored = theme_match(query, pos, neg)
        # Expand candidate pool for analyze mode
        pool_pos = max(config["positive_count"] * 4, 12)
        pool_neg = max(config["negative_count"] * 4, 8)
        pos_keys = [k for k, _ in pos_scored[:pool_pos]]
        neg_keys = [k for k, _ in neg_scored[:pool_neg]]
        format_candidates_json(pos, neg, pos_keys, neg_keys)
        return

    # Mode 3: Single card lookup
    if query and config["positive_count"] == 0 and config["negative_count"] == 0:
        card, card_type = find_trait(query, pos, neg)
        if card:
            print(format_single_card(card, card_type))
            return

    # Mode 3 also: if query looks like a single trait name
    if query and len(query) <= 6:
        card, card_type = find_trait(query, pos, neg)
        if card:
            print(format_single_card(card, card_type))
            return

    # Mode 2: Themed draw
    if query:
        pos_keys, neg_keys = draw_themed(query, pos, neg, config)
    else:
        # Mode 1: Random draw
        pos_keys, neg_keys = draw_random(pos, neg, config)

    print(format_output(pos, neg, pos_keys, neg_keys, config["show_depth"]))


if __name__ == "__main__":
    main()
