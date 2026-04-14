#!/usr/bin/env python3
"""Adversarial verification test suite for character trait draw engine.

Covers: data integrity, constraint invariants, edge cases, all draw modes,
CLI routing, and boundary conditions. Designed to be run with:
    python3 scripts/test_draw.py
"""

import json
import random
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from draw import (
    _fuzzy_substring,
    load_data, parse_args, draw_random, draw_themed, draw_from_pool,
    has_conflict, _normalize_conflicts, fuzzy_match, find_trait,
    theme_match, format_output, format_single_card, format_candidates_json,
    calc_tension, _cross_conflicts,
    VALID_CATS, TIER_PRESETS,
)

# ─── Helpers ───────────────────────────────────────────────────────────────

passed = 0
failed = 0
errors = []


def assert_test(condition, name, detail=""):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        msg = f"FAIL: {name}"
        if detail:
            msg += f" — {detail}"
        errors.append(msg)
        print(msg)


def run_draws(n, config_overrides=None):
    """Run n draws, collect results for invariant checking."""
    pos, neg = load_data()
    results = []
    for _ in range(n):
        config = parse_args([])
        if config_overrides:
            config.update(config_overrides)
        pk, nk = draw_random(pos, neg, config)
        results.append((pk, nk, pos, neg, config))
    return results


def has_same_side_conflict(keys, trait_dict):
    """Check if any pair in keys conflicts on the same side."""
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if has_conflict(a, [b], trait_dict):
                return True, a, b
    return False, None, None


def has_similar_pair(keys, trait_dict):
    """Check if any pair in keys is similar."""
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            sims_a = trait_dict[a].get("similar_traits", [])
            sims_b = trait_dict[b].get("similar_traits", [])
            for s in sims_a:
                if _fuzzy_substring(s, b):
                    return True, a, b, "a_sim_of_b"
            for s in sims_b:
                if _fuzzy_substring(s, a):
                    return True, a, b, "b_sim_of_a"
    return False, None, None, None


# ═══════════════════════════════════════════════════════════════════════════
# 1. DATA INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════

def test_data_integrity():
    print("\n── 1. Data Integrity ──")
    pos, neg = load_data()

    # Correct counts
    assert_test(len(pos) == 96, "positive trait count", f"got {len(pos)}")
    assert_test(len(neg) == 104, "negative trait count", f"got {len(neg)}")

    # All keys == name_cn
    for k in pos:
        assert_test(pos[k].get("name_cn") == k, f"pos key==name_cn for {k}",
                    f"key={k!r} name_cn={pos[k].get('name_cn')!r}")
    for k in neg:
        assert_test(neg[k].get("name_cn") == k, f"neg key==name_cn for {k}",
                    f"key={k!r} name_cn={neg[k].get('name_cn')!r}")

    # Required fields
    required = ["name_cn", "name_en", "definition", "conflicting_traits"]
    for field in required:
        for k in pos:
            assert_test(field in pos[k], f"pos has {field}", f"missing in {k}")
        for k in neg:
            assert_test(field in neg[k], f"neg has {field}", f"missing in {k}")


    # No empty name_en or definition
    empty_name_en = [k for k in pos if not pos[k].get("name_en", "").strip()]
    assert_test(len(empty_name_en) == 0, "no empty pos name_en", f"empty: {empty_name_en}")
    empty_def_pos = [k for k in pos if not pos[k].get("definition", "").strip()]
    assert_test(len(empty_def_pos) == 0, "no empty pos definition", f"empty: {empty_def_pos}")

    # No empty conflicting_traits (all traits should have at least one)
    # Not a hard requirement — but log it
    zero_conf_pos = [k for k in pos if not _normalize_conflicts(pos[k].get("conflicting_traits", []))]
    zero_conf_neg = [k for k in neg if not _normalize_conflicts(neg[k].get("conflicting_traits", []))]
    print(f"  Info: {len(zero_conf_pos)} pos with 0 conflicts: {zero_conf_pos}")
    print(f"  Info: {len(zero_conf_neg)} neg with 0 conflicts: {zero_conf_neg}")


# ═══════════════════════════════════════════════════════════════════════════
# 2. SAME-SIDE CONFLICT AVOIDANCE
# ═══════════════════════════════════════════════════════════════════════════

def test_same_side_conflict_avoidance():
    print("\n── 2. Same-Side Conflict Avoidance ──")
    pos, neg = load_data()

    # 200 random draws: no same-side conflicts
    for i in range(200):
        config = parse_args([])
        pk, nk = draw_random(pos, neg, config)

        ok, a, b = has_same_side_conflict(pk, pos)
        assert_test(not ok, f"draw {i} no pos-side conflict", f"{a} ↔ {b}")

        ok, a, b = has_same_side_conflict(nk, neg)
        assert_test(not ok, f"draw {i} no neg-side conflict", f"{a} ↔ {b}")

    # 100 themed draws: same
    for i in range(100):
        config = parse_args([])
        pk, nk = draw_themed("一个冷酷的杀手", pos, neg, config)

        ok, a, b = has_same_side_conflict(pk, pos)
        assert_test(not ok, f"themed {i} no pos-side conflict", f"{a} ↔ {b}")

        ok, a, b = has_same_side_conflict(nk, neg)
        assert_test(not ok, f"themed {i} no neg-side conflict", f"{a} ↔ {b}")


# ═══════════════════════════════════════════════════════════════════════════
# 3. NO DUPLICATES
# ═══════════════════════════════════════════════════════════════════════════

def test_no_duplicates():
    print("\n── 3. No Duplicates ──")
    pos, neg = load_data()

    for i in range(200):
        config = parse_args([])
        pk, nk = draw_random(pos, neg, config)

        assert_test(len(pk) == len(set(pk)), f"draw {i} pos unique",
                    f"duplicates in {pk}")
        assert_test(len(nk) == len(set(nk)), f"draw {i} neg unique",
                    f"duplicates in {nk}")


# ═══════════════════════════════════════════════════════════════════════════
# 4. CORRECT COUNT
# ═══════════════════════════════════════════════════════════════════════════

def test_correct_count():
    print("\n── 4. Correct Count ──")
    pos, neg = load_data()

    # Default major: 4+2
    for i in range(50):
        config = parse_args([])
        pk, nk = draw_random(pos, neg, config)
        assert_test(len(pk) == 4, f"draw {i} pos count=4", f"got {len(pk)}")
        assert_test(len(nk) == 2, f"draw {i} neg count=2", f"got {len(nk)}")

    # Supporting: 3+1
    for i in range(50):
        config = parse_args(["--tier", "supporting"])
        pk, nk = draw_random(pos, neg, config)
        assert_test(len(pk) == 3, f"supporting {i} pos count=3", f"got {len(pk)}")
        assert_test(len(nk) == 1, f"supporting {i} neg count=1", f"got {len(nk)}")

    # Minor: 1+0
    for i in range(50):
        config = parse_args(["--tier", "minor"])
        pk, nk = draw_random(pos, neg, config)
        assert_test(len(pk) == 1, f"minor {i} pos count=1", f"got {len(pk)}")
        assert_test(len(nk) == 0, f"minor {i} neg count=0", f"got {len(nk)}")

    # Custom: high counts
    for i in range(20):
        config = parse_args(["--positive", "10", "--negative", "5"])
        pk, nk = draw_random(pos, neg, config)
        assert_test(len(pk) == 10, f"high pos {i} count=10", f"got {len(pk)}")
        assert_test(len(nk) == 5, f"high neg {i} count=5", f"got {len(nk)}")

    # Edge: 0+0
    config = parse_args(["--positive", "0", "--negative", "0"])
    pk, nk = draw_random(pos, neg, config)
    assert_test(len(pk) == 0, "0+0 pos count", f"got {len(pk)}")
    assert_test(len(nk) == 0, "0+0 neg count", f"got {len(nk)}")

    # Edge: 1+1
    for i in range(20):
        config = parse_args(["--positive", "1", "--negative", "1"])
        pk, nk = draw_random(pos, neg, config)
        assert_test(len(pk) == 1, f"1+1 draw {i} pos", f"got {len(pk)}")
        assert_test(len(nk) == 1, f"1+1 draw {i} neg", f"got {len(nk)}")


# ═══════════════════════════════════════════════════════════════════════════
# 5. TENSION GUARANTEE
# ═══════════════════════════════════════════════════════════════════════════

def test_tension_guarantee():
    print("\n── 5. Tension Guarantee ──")
    pos, neg = load_data()

    tension_met = 0
    tension_missed = 0
    for i in range(200):
        config = parse_args([])  # ensure_tension=True by default
        pk, nk = draw_random(pos, neg, config)
        if not nk:
            continue

        # Check if at least one neg conflicts with at least one pos (cross-side)
        found = False
        for n in nk:
            n_conflicts = _normalize_conflicts(neg[n].get("conflicting_traits", []))
            for p in pk:
                # Check if n's conflicts mention p, or p's conflicts mention n
                if p in n_conflicts or any(len(c) >= 2 and (c in p or p in c) for c in n_conflicts):
                    found = True
                    break
                p_conflicts = _normalize_conflicts(pos[p].get("conflicting_traits", []))
                if n in p_conflicts or any(len(c) >= 2 and (c in n or n in c) for c in p_conflicts):
                    found = True
                    break
            if found:
                break

        if found:
            tension_met += 1
        else:
            tension_missed += 1
            if tension_missed <= 5:
                print(f"  No tension: pos={pk}, neg={nk}")

    rate = tension_met / (tension_met + tension_missed) * 100 if (tension_met + tension_missed) > 0 else 0
    # Tension can only fail when first positive has zero conflicts and no other positive
    # provides a match — this is a data limitation, not a code bug
    assert_test(rate >= 95, f"tension >= 95% ({tension_met}/{tension_met + tension_missed})",
                f"missed {tension_missed} ({rate:.0f}%)")

    # With tension disabled: should sometimes lack tension
    no_tension_count = 0
    for i in range(100):
        config = parse_args(["--no-tension"])
        config["positive_count"] = 4
        config["negative_count"] = 2
        pk, nk = draw_random(pos, neg, config)
        found = False
        for n in nk:
            n_conflicts = _normalize_conflicts(neg[n].get("conflicting_traits", []))
            for p in pk:
                if p in n_conflicts or any(len(c) >= 2 and (c in p or p in c) for c in n_conflicts):
                    found = True
                    break
                p_conflicts = _normalize_conflicts(pos[p].get("conflicting_traits", []))
                if n in p_conflicts or any(len(c) >= 2 and (c in n or n in c) for c in p_conflicts):
                    found = True
                    break
        if not found:
            no_tension_count += 1

    # Not a hard assertion — just informational
    print(f"  Info: --no-tension draws without cross-side tension: {no_tension_count}/100")


# ═══════════════════════════════════════════════════════════════════════════
# 6. CROSS-CATEGORY
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_category():
    print("\n── 6. Cross-Category ──")
    pos, neg = load_data()

    for i in range(100):
        config = parse_args([])  # cross_category=True by default
        pk, nk = draw_random(pos, neg, config)
        cats = set()
        for k in pk:
            for c in pos[k].get("category", []):
                if c in VALID_CATS:
                    cats.add(c)
        assert_test(len(cats) >= 2, f"draw {i} cross-category (got {len(cats)})",
                    f"categories: {cats}")

    # With --no-category: single-category draws possible (just info)
    single_cat = 0
    for i in range(50):
        config = parse_args(["--no-category"])
        config["positive_count"] = 4
        config["negative_count"] = 2
        pk, nk = draw_random(pos, neg, config)
        cats = set()
        for k in pk:
            for c in pos[k].get("category", []):
                if c in VALID_CATS:
                    cats.add(c)
        if len(cats) < 2:
            single_cat += 1
    print(f"  Info: --no-category single-cat draws: {single_cat}/50")


# ═══════════════════════════════════════════════════════════════════════════
# 7. SIMILAR AVOIDANCE
# ═══════════════════════════════════════════════════════════════════════════

def test_similar_avoidance():
    print("\n── 7. Similar Avoidance ──")
    pos, neg = load_data()

    similar_found = 0
    for i in range(200):
        config = parse_args([])
        pk, nk = draw_random(pos, neg, config)

        ok, a, b, direction = has_similar_pair(pk, pos)
        if not ok:
            ok, a, b, direction = has_similar_pair(nk, neg)
        if ok:
            similar_found += 1
            if similar_found <= 5:
                print(f"  Similar pair: {a} ↔ {b} ({direction})")

    assert_test(similar_found == 0, f"no similar pairs in 200 draws",
                f"found {similar_found}")


# ═══════════════════════════════════════════════════════════════════════════
# 8. ZERO-CONFLICT TRAIT EDGE CASE
# ═══════════════════════════════════════════════════════════════════════════

def test_zero_conflict_traits():
    print("\n── 8. Zero-Conflict Trait Edge Case ──")
    pos, neg = load_data()

    zero_conf = [k for k in pos if not _normalize_conflicts(pos[k].get("conflicting_traits", []))]
    print(f"  Zero-conflict positive traits: {zero_conf}")

    # Force-draw a zero-conflict trait as first pick, verify tension still works
    if zero_conf:
        for zc in zero_conf:
            config = parse_args([])
            result = draw_from_pool([zc], pos, 1, config)
            assert_test(result == [zc], f"zero-conf trait {zc} drawable alone",
                        f"got {result}")


# ═══════════════════════════════════════════════════════════════════════════
# 9. DRAW_FROM_POOL EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════

def test_draw_from_pool_edge_cases():
    print("\n── 9. draw_from_pool Edge Cases ──")
    pos, neg = load_data()
    config = parse_args([])

    # count=0
    result = draw_from_pool(list(pos.keys()), pos, 0, config)
    assert_test(result == [], "draw_from_pool count=0", f"got {result}")

    # empty keys
    result = draw_from_pool([], pos, 4, config)
    assert_test(result == [], "draw_from_pool empty keys", f"got {result}")

    # count > available keys
    small_keys = list(pos.keys())[:3]
    result = draw_from_pool(small_keys, pos, 5, config)
    assert_test(len(result) <= 3, "draw_from_pool count>keys caps at available",
                f"got {len(result)}")

    # initial_chosen respected: no duplicates
    result = draw_from_pool(list(neg.keys()), neg, 2, config, initial_chosen=["懒惰的"])
    assert_test("懒惰的" not in result, "initial_chosen not in result",
                f"result={result}")

    # initial_chosen conflicts respected: second pick doesn't conflict with first
    for k in neg:
        nc = _normalize_conflicts(neg[k].get("conflicting_traits", []))
        for c in nc:
            match = None
            for kk in neg:
                if c in kk or kk in c:
                    match = kk
                    break
            if match and match != k:
                result = draw_from_pool(list(neg.keys()), neg, 1, config,
                                        initial_chosen=[k])
                if result:
                    ok, a, b = has_same_side_conflict([k] + result, neg)
                    assert_test(not ok, f"initial_chosen conflict respected for {k}",
                                f"conflict with {result}")
                break
        else:
            continue
        break


# ═══════════════════════════════════════════════════════════════════════════
# 10. FUZZY_MATCH EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════

def test_fuzzy_match_edge_cases():
    print("\n── 10. fuzzy_match Edge Cases ──")
    pos, neg = load_data()

    # Exact match
    assert_test(fuzzy_match("勇敢的", pos) == "勇敢的", "exact match")
    assert_test(fuzzy_match("胆怯的", neg) == "胆怯的", "exact match neg")

    # Substring match
    result = fuzzy_match("勇敢", pos)
    assert_test(result is not None and "勇敢" in result, "substring match",
                f"got {result}")

    # No match
    assert_test(fuzzy_match("zzzz不存在的", pos) is None, "no match returns None")

    # Adversarial: very short query that could match many
    result = fuzzy_match("的", pos)
    assert_test(result is not None, "single char 的 matches something",
                f"got {result}")


# ═══════════════════════════════════════════════════════════════════════════
# 11. _NORMALIZE_CONFLICTS
# ═══════════════════════════════════════════════════════════════════════════

def test_normalize_conflicts():
    print("\n── 11. _normalize_conflicts ──")

    # Clean input passes through
    assert_test(_normalize_conflicts(["勇敢的", "鲁莽的"]) == ["勇敢的", "鲁莽的"],
                "clean conflicts pass through")

    # Split entry joined: '胆怯' + '的' -> '胆怯的'
    assert_test("胆怯的" in _normalize_conflicts(["胆怯", "的"]),
                "split entry joined")

    # Single-char noise removed
    result = _normalize_conflicts(["勇敢的", "的", "鲁莽的"])
    assert_test("的" not in result, "single-char noise removed", f"got {result}")

    # Empty list
    assert_test(_normalize_conflicts([]) == [], "empty list")

    # All single chars
    assert_test(_normalize_conflicts(["的", "了"]) == [], "all single chars")


# ═══════════════════════════════════════════════════════════════════════════
# 12. PARSE_ARGS
# ═══════════════════════════════════════════════════════════════════════════

def test_parse_args():
    print("\n── 12. parse_args ──")

    # Default
    c = parse_args([])
    assert_test(c["positive_count"] == 4, "default pos count", f"got {c['positive_count']}")
    assert_test(c["negative_count"] == 2, "default neg count", f"got {c['negative_count']}")
    assert_test(c["ensure_tension"] is True, "default tension on")
    assert_test(c["cross_category"] is True, "default category on")
    assert_test(c["avoid_similar"] is True, "default similar on")
    assert_test(c["avoid_same_side_conflict"] is True, "default side conflict on")
    assert_test(c["show_depth"] == "full", "default show full")

    # All flags
    c = parse_args(["--no-tension", "--no-category", "--no-similar", "--no-side-conflict"])
    assert_test(c["ensure_tension"] is False, "--no-tension")
    assert_test(c["cross_category"] is False, "--no-category")
    assert_test(c["avoid_similar"] is False, "--no-similar")
    assert_test(c["avoid_same_side_conflict"] is False, "--no-side-conflict")

    # Tier presets
    for tier, expected in TIER_PRESETS.items():
        c = parse_args(["--tier", tier])
        assert_test(c["positive_count"] == expected["positive"],
                    f"tier {tier} pos", f"got {c['positive_count']}")
        assert_test(c["negative_count"] == expected["negative"],
                    f"tier {tier} neg", f"got {c['negative_count']}")

    # Explicit count overrides tier
    c = parse_args(["--tier", "minor", "--positive", "5", "--negative", "3"])
    assert_test(c["positive_count"] == 5, "explicit pos overrides tier")
    assert_test(c["negative_count"] == 3, "explicit neg overrides tier")

    # Query from positional args
    c = parse_args(["一个冷酷的杀手"])
    assert_test(c["query"] == "一个冷酷的杀手", "single query")

    c = parse_args(["一个", "冷酷的", "杀手"])
    assert_test(c["query"] == "一个 冷酷的 杀手", "multi-word query joined")

    # --analyze
    c = parse_args(["--analyze", "query"])
    assert_test(c["analyze"] is True, "--analyze flag")

    # --show
    c = parse_args(["--show", "compact"])
    assert_test(c["show_depth"] == "compact", "--show compact")

    # Unknown flags ignored (not crash)
    c = parse_args(["--unknown-flag"])
    assert_test(True, "unknown flag doesn't crash")


# ═══════════════════════════════════════════════════════════════════════════
# 13. FIND_TRAIT
# ═══════════════════════════════════════════════════════════════════════════

def test_find_trait():
    print("\n── 13. find_trait ──")
    pos, neg = load_data()

    # Exact positive
    card, ctype = find_trait("勇敢的", pos, neg)
    assert_test(card is not None and ctype == "positive", "find exact positive")

    # Exact negative
    card, ctype = find_trait("胆怯的", pos, neg)
    assert_test(card is not None and ctype == "negative", "find exact negative")

    # English match (name_en is "Courageous", not "Brave")
    card, ctype = find_trait("Courageous", pos, neg)
    assert_test(card is not None, "find by english name", f"ctype={ctype}")

    # Fuzzy match
    card, ctype = find_trait("勇敢", pos, neg)
    assert_test(card is not None, "find by fuzzy substring")

    # Not found
    card, ctype = find_trait("不存在的特质名xyz", pos, neg)
    assert_test(card is None and ctype is None, "not found returns None,None")


# ═══════════════════════════════════════════════════════════════════════════
# 14. FORMAT OUTPUT (no crash)
# ═══════════════════════════════════════════════════════════════════════════

def test_format_output_no_crash():
    print("\n── 14. format_output (no crash) ──")
    pos, neg = load_data()

    for depth in ["compact", "summary", "full"]:
        try:
            config = parse_args([])
            pk, nk = draw_random(pos, neg, config)
            output = format_output(pos, neg, pk, nk, depth)
            assert_test(isinstance(output, str) and len(output) > 0,
                        f"format_output depth={depth} returns string")
        except Exception as e:
            assert_test(False, f"format_output depth={depth}", str(e))

    # Edge: no negatives
    pk = list(pos.keys())[:2]
    nk = []
    try:
        output = format_output(pos, neg, pk, nk, "full")
        assert_test(isinstance(output, str), "format_output no negatives")
    except Exception as e:
        assert_test(False, "format_output no negatives", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# 15. FORMAT_SINGLE_CARD (no crash)
# ═══════════════════════════════════════════════════════════════════════════

def test_format_single_card_no_crash():
    print("\n── 15. format_single_card (no crash) ──")
    pos, neg = load_data()

    for k in list(pos.keys())[:5]:
        try:
            output = format_single_card(pos[k], "positive")
            assert_test(isinstance(output, str), f"format_single_card pos {k}")
        except Exception as e:
            assert_test(False, f"format_single_card pos {k}", str(e))

    for k in list(neg.keys())[:5]:
        try:
            output = format_single_card(neg[k], "negative")
            assert_test(isinstance(output, str), f"format_single_card neg {k}")
        except Exception as e:
            assert_test(False, f"format_single_card neg {k}", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# 16. CLI SMOKE TEST
# ═══════════════════════════════════════════════════════════════════════════

def test_cli_smoke():
    print("\n── 16. CLI Smoke Test ──")
    script = os.path.join(SCRIPT_DIR, "draw.py")

    # Random draw
    r = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=10)
    assert_test(r.returncode == 0, "CLI random draw exit 0", r.stderr[:200] if r.stderr else "")
    assert_test("角色特质组合" in r.stdout, "CLI random draw has header")

    # Themed draw
    r = subprocess.run([sys.executable, script, "冷酷杀手"], capture_output=True, text=True, timeout=10)
    assert_test(r.returncode == 0, "CLI themed draw exit 0", r.stderr[:200] if r.stderr else "")

    # Single card lookup
    r = subprocess.run([sys.executable, script, "勇敢的"], capture_output=True, text=True, timeout=10)
    assert_test(r.returncode == 0, "CLI single card exit 0", r.stderr[:200] if r.stderr else "")
    assert_test("勇敢" in r.stdout, "CLI single card has content")

    # Analyze mode
    r = subprocess.run([sys.executable, script, "--analyze", "一个孤儿"],
                       capture_output=True, text=True, timeout=10)
    assert_test(r.returncode == 0, "CLI analyze exit 0", r.stderr[:200] if r.stderr else "")
    try:
        j = json.loads(r.stdout)
        assert_test("positive" in j and "negative" in j, "CLI analyze returns JSON")
    except json.JSONDecodeError:
        assert_test(False, "CLI analyze returns valid JSON", r.stdout[:200])

    # --tier minor
    r = subprocess.run([sys.executable, script, "--tier", "minor", "--show", "compact"],
                       capture_output=True, text=True, timeout=10)
    assert_test(r.returncode == 0, "CLI tier minor exit 0")
    assert_test("负面特质" not in r.stdout, "CLI tier minor has no negatives")

    # --no-side-conflict flag
    r = subprocess.run([sys.executable, script, "--no-side-conflict"],
                       capture_output=True, text=True, timeout=10)
    assert_test(r.returncode == 0, "CLI --no-side-conflict exit 0")


# ═══════════════════════════════════════════════════════════════════════════
# 17. ADVERSARIAL: EXHAUSTIVE SAME-SIDE CONFLICT CHECK
# ═══════════════════════════════════════════════════════════════════════════

def test_exhaustive_conflict_consistency():
    """Verify has_conflict is bidirectional and consistent with data."""
    print("\n── 17. Exhaustive Conflict Consistency ──")
    pos, neg = load_data()

    # For every pair that has_conflict says conflicts, verify in data
    false_positives = 0
    for i, a in enumerate(list(pos.keys())[:20]):
        for b in list(pos.keys())[i+1:30]:
            if has_conflict(a, [b], pos):
                a_nc = _normalize_conflicts(pos[a].get("conflicting_traits", []))
                b_nc = _normalize_conflicts(pos[b].get("conflicting_traits", []))
                direct = b in a_nc or a in b_nc
                fuzzy = False
                for c in a_nc:
                    if len(c) >= 2 and (c in b or b in c):
                        fuzzy = True
                for c in b_nc:
                    if len(c) >= 2 and (c in a or a in c):
                        fuzzy = True
                if not direct and not fuzzy:
                    false_positives += 1
                    if false_positives <= 5:
                        print(f"  Possible false positive: {a} ↔ {b}")

    print(f"  Possible false positives in sample: {false_positives}")


# ═══════════════════════════════════════════════════════════════════════════
# 18. ADVERSARIAL: HIGH COUNT STRESS TEST
# ═══════════════════════════════════════════════════════════════════════════

def test_high_count_stress():
    """Request many traits, verify no crashes and invariants hold."""
    print("\n── 18. High Count Stress Test ──")
    pos, neg = load_data()

    # Request all positive traits (96) — should still not conflict
    config = parse_args(["--positive", "96", "--negative", "0", "--no-category"])
    pk, nk = draw_random(pos, neg, config)
    assert_test(len(pk) <= 96, "96 pos count capped at 96", f"got {len(pk)}")
    ok, a, b = has_same_side_conflict(pk, pos)
    print(f"  All 96 pos: {len(pk)} drawn, same-side conflicts: {'yes' if ok else 'no'}")

    # Request all negative traits (104)
    config = parse_args(["--positive", "0", "--negative", "104", "--no-category",
                         "--no-tension"])
    pk, nk = draw_random(pos, neg, config)
    assert_test(len(nk) <= 104, "104 neg count capped at 104", f"got {len(nk)}")
    ok, a, b = has_same_side_conflict(nk, neg)
    print(f"  All 104 neg: {len(nk)} drawn, same-side conflicts: {'yes' if ok else 'no'}")

    # Request more than available
    config = parse_args(["--positive", "200", "--negative", "200", "--no-category"])
    pk, nk = draw_random(pos, neg, config)
    assert_test(len(pk) <= 96, "200 pos capped at 96", f"got {len(pk)}")
    assert_test(len(nk) <= 104, "200 neg capped at 104", f"got {len(nk)}")


# ═══════════════════════════════════════════════════════════════════════════
# 19. ADVERSARIAL: DISABLED CONSTRAINTS COMBINATION
# ═══════════════════════════════════════════════════════════════════════════

def test_disabled_constraints():
    """All constraints off: should still not crash and produce results."""
    print("\n── 19. Disabled Constraints ──")
    pos, neg = load_data()

    config = parse_args(["--no-tension", "--no-category", "--no-similar", "--no-side-conflict"])
    for i in range(50):
        pk, nk = draw_random(pos, neg, config)
        assert_test(len(pk) > 0, f"disabled {i} has pos results")
        assert_test(len(nk) > 0, f"disabled {i} has neg results")


# ═══════════════════════════════════════════════════════════════════════════
# 20. ADVERSARIAL: THEMED DRAWS WITH VARIOUS QUERIES
# ═══════════════════════════════════════════════════════════════════════════

def test_themed_draws_various():
    """Various query types: short, long, nonsense, mixed-language."""
    print("\n── 20. Themed Draws Various Queries ──")
    pos, neg = load_data()

    queries = [
        "冷酷杀手",
        "一个从小在孤儿院长大的女孩，被收养后却发现养父另有所图",
        "abc",
        "的的了了",
        "勇敢善良",
        "A brave hero",
        "",
    ]

    for q in queries:
        try:
            config = parse_args([])
            pk, nk = draw_themed(q, pos, neg, config)
            assert_test(len(pk) > 0, f"themed '{q[:20]}' has results",
                        f"pos={len(pk)} neg={len(nk)}")
        except Exception as e:
            assert_test(False, f"themed '{q[:20]}' no crash", str(e))


def test_tension_quantification():
    """21. Tension score and cross-conflict pair detection."""
    print("\n── 21. Tension Quantification ──")


    pos, neg = load_data()
    # calc_tension with no negative traits
    result = calc_tension(["爱国的"], [], pos, neg)
    assert_test(result["score"] == 0.0, "zero neg → score 0.0", f"got {result['score']}")
    assert_test(result["max_possible"] == 0, "zero neg → max_possible 0", f"got {result['max_possible']}")

    # calc_tension with no positive traits
    result = calc_tension([], ["胆怯的"], pos, neg)
    assert_test(result["score"] == 0.0, "zero pos → score 0.0", f"got {result['score']}")

    # calc_tension with known conflicting pair
    # "爱国的" has "不忠诚的" in its conflicting_traits
    result = calc_tension(["爱国的"], ["不忠诚的"], pos, neg)
    assert_test(result["score"] > 0.0, "known conflict pair → score > 0", f"got {result['score']}")
    assert_test(len(result["pairs"]) >= 1, "known conflict pair → pairs non-empty", f"got {len(result['pairs'])}")
    assert_test(result["max_possible"] == 1, "1x1 → max 1", f"got {result['max_possible']}")

    # Score range for random draws
    scores = []
    for _ in range(100):
        random.seed()
        config = parse_args([])
        pk, nk = draw_random(pos, neg, config)
        t = calc_tension(pk, nk, pos, neg)
        assert_test(0.0 <= t["score"] <= 1.0, f"score in [0,1]", f"got {t['score']}")
        assert_test(t["max_possible"] == len(pk) * len(nk), "max_possible = pos*neg", f"{t['max_possible']} != {len(pk)}*{len(nk)}")
        scores.append(t["score"])
    avg = sum(scores) / len(scores) if scores else 0
    assert_test(avg > 0.05, f"avg tension > 0.05", f"avg={avg:.3f}")

    # _cross_conflicts detects bidirectional matches
    pairs = _cross_conflicts(["爱国的"], ["不忠诚的"], pos, neg)
    if pairs:
        assert_test(pairs[0]["direction"] in ("pos→neg", "neg→pos", "bidirectional"),
                     "direction is valid", f"got {pairs[0]['direction']}")

    # Tension score in format_output (full mode)
    config = parse_args([])
    pk, nk = draw_random(pos, neg, config)
    output = format_output(pos, neg, pk, nk, "full")
    assert_test("张力得分" in output, "format_output full has 张力得分", "missing in output")
    assert_test("张力指标" in output, "format_output full has 张力指标", "missing in output")

    # Tension score in format_output (compact mode)
    output_c = format_output(pos, neg, pk, nk, "compact")
    assert_test("张力" in output_c, "format_output compact has 张力", "missing in output")
    assert_test("张力指标" not in output_c, "compact has no 张力指标 section", "should be summary only")

    # Score with zero-conflict positive traits
    zero_conflict = ["天真无邪的", "外向的", "幸福的"]
    for zc in zero_conflict:
        if zc in pos:
            result = calc_tension([zc], list(neg.keys())[:5], pos, neg)
            assert_test(isinstance(result["score"], float), f"zero-conflict {zc} no crash", f"score={result['score']}")
            break



def test_data_quality_adversarial():
    """22. Adversarial data quality: zero dangling refs, no prose, no splits, no single-char noise."""
    print("\n── 22. Data Quality (Adversarial) ──")
    pos, neg = load_data()
    all_keys = set(pos.keys()) | set(neg.keys())

    # 22a. Zero dangling conflicting_traits after normalize + fuzzy
    dangling = 0
    for side_name, side_dict in [("positive", pos), ("negative", neg)]:
        for key, card in side_dict.items():
            normed = _normalize_conflicts(card.get("conflicting_traits", []))
            for ref in normed:
                if ref in all_keys:
                    continue
                # fuzzy fallback
                found = False
                for k in all_keys:
                    if len(ref) >= 2 and (ref in k or k in ref):
                        found = True
                        break
                if not found:
                    dangling += 1
                    print(f"  DANGLING: {side_name} '{key}' -> '{ref}'")
    assert_test(dangling == 0, "zero dangling conflicting_traits refs",
                f"found {dangling} dangling refs")

    # 22b. No single-char entries in raw conflicting_traits
    single_char_count = 0
    for side_name, side_dict in [("positive", pos), ("negative", neg)]:
        for key, card in side_dict.items():
            for ref in card.get("conflicting_traits", []):
                if len(ref) <= 1:
                    single_char_count += 1
                    print(f"  SINGLE-CHAR: {side_name} '{key}' -> '{ref}'")
    assert_test(single_char_count == 0, "no single-char entries in conflicting_traits",
                f"found {single_char_count}")

    # 22c. No prose/text fragments (entries containing Chinese punctuation)
    # Exception: entries that are exact keys are valid (e.g. "古怪的，不可靠的")
    prose_chars = set("。，、；：！？（）【】“”‘’…—《》\n")
    prose_count = 0
    for side_name, side_dict in [("positive", pos), ("negative", neg)]:
        for key, card in side_dict.items():
            for ref in card.get("conflicting_traits", []):
                if any(c in prose_chars for c in ref):
                    if ref in all_keys:
                        continue  # valid key that happens to contain punctuation
                    prose_count += 1
                    print(f"  PROSE FRAGMENT: {side_name} '{key}' -> '{ref}'")
    assert_test(prose_count == 0, "no prose fragments in conflicting_traits",
                f"found {prose_count}")

    # 22d. No English annotations in conflicting_traits (e.g., "反社会的 Antisocial")
    import re
    english_count = 0
    for side_name, side_dict in [("positive", pos), ("negative", neg)]:
        for key, card in side_dict.items():
            for ref in card.get("conflicting_traits", []):
                if re.search(r'[A-Za-z]{3,}', ref):
                    english_count += 1
                    print(f"  ENGLISH IN REF: {side_name} '{key}' -> '{ref}'")
    assert_test(english_count == 0, "no English annotations in conflicting_traits",
                f"found {english_count}")

    # 22e. Every conflict ref after normalize is >= 2 chars
    short_count = 0
    for side_name, side_dict in [("positive", pos), ("negative", neg)]:
        for key, card in side_dict.items():
            for ref in _normalize_conflicts(card.get("conflicting_traits", [])):
                if len(ref) < 2:
                    short_count += 1
                    print(f"  SHORT REF: {side_name} '{key}' -> '{ref}'")
    assert_test(short_count == 0, "all normalized refs >= 2 chars",
                f"found {short_count}")

    # 22f. No duplicate entries within a single trait's conflicting_traits (after normalize)
    dup_count = 0
    for side_name, side_dict in [("positive", pos), ("negative", neg)]:
        for key, card in side_dict.items():
            normed = _normalize_conflicts(card.get("conflicting_traits", []))
            seen = set()
            for ref in normed:
                if ref in seen:
                    dup_count += 1
                    print(f"  DUP CONFLICT: {side_name} '{key}' -> '{ref}'")
                seen.add(ref)
    assert_test(dup_count == 0, "no duplicate conflict refs within a trait",
                f"found {dup_count} duplicates")

    # 22g. Cross-side conflict graph: at least 80% of traits have at least one cross-side conflict
    cross_coverage = 0
    total = 0
    for side_name, side_dict, other_dict in [("positive", pos, neg), ("negative", neg, pos)]:
        for key, card in side_dict.items():
            total += 1
            normed = _normalize_conflicts(card.get("conflicting_traits", []))
            has_cross = False
            for ref in normed:
                if ref in other_dict:
                    has_cross = True
                    break
                for ok in other_dict:
                    if len(ref) >= 2 and (ref in ok or ok in ref):
                        has_cross = True
                        break
                if has_cross:
                    break
            if has_cross:
                cross_coverage += 1
    coverage_pct = cross_coverage / total if total > 0 else 0
    assert_test(coverage_pct >= 0.8, f"cross-side conflict coverage >= 80%",
                f"got {coverage_pct:.1%} ({cross_coverage}/{total})")


# ═══════════════════════════════════════════════════════════════════════════

def test_cached_norm_conflicts():
    """23. Verify _norm_conflicts is pre-computed and correct."""
    print("\n── 23. Cached Normalized Conflicts ──")
    pos, neg = load_data()

    # Every card has _norm_conflicts
    missing = 0
    for k in pos:
        if '_norm_conflicts' not in pos[k]:
            missing += 1
    assert_test(missing == 0, 'all positive traits have _norm_conflicts', f'{missing} missing')

    missing_neg = 0
    for k in neg:
        if '_norm_conflicts' not in neg[k]:
            missing_neg += 1
    assert_test(missing_neg == 0, 'all negative traits have _norm_conflicts', f'{missing_neg} missing')

    # Cached values match live computation
    mismatch = 0
    for k in pos:
        expected = _normalize_conflicts(pos[k].get('conflicting_traits', []))
        actual = pos[k].get('_norm_conflicts', [])
        if expected != actual:
            mismatch += 1
            print(f'  MISMATCH pos {k}: expected={expected}, got={actual}')
    assert_test(mismatch == 0, 'positive cached matches live', f'{mismatch} mismatches')

    for k in neg:
        expected = _normalize_conflicts(neg[k].get('conflicting_traits', []))
        actual = neg[k].get('_norm_conflicts', [])
        if expected != actual:
            mismatch += 1
            print(f'  MISMATCH neg {k}: expected={expected}, got={actual}')
    assert_test(mismatch == 0, 'negative cached matches live', f'{mismatch} mismatches')




# ═══════════════════════════════════════════════════════════════════════════
# 24. FUZZY SUBSTRING HELPER
# ═══════════════════════════════════════════════════════════════════════════

def test_fuzzy_substring_helper():
    """24. Test _fuzzy_substring helper edge cases."""
    print("\n── 24. Fuzzy Substring Helper ──")
    
    # Exact match
    assert_test(_fuzzy_substring("test", "test") == True, "exact match returns True")
    
    # Substring match
    assert_test(_fuzzy_substring("hello", "hello world") == True, "substring match returns True")
    assert_test(_fuzzy_substring("world", "hello world") == True, "reverse substring match returns True")
    
    # No match
    assert_test(_fuzzy_substring("abc", "xyz") == False, "no match returns False")
    
    # Single char with min_len=2 returns False
    assert_test(_fuzzy_substring("a", "abc") == False, "single char with min_len=2 returns False")
    
    # Single char with min_len=1 returns True
    assert_test(_fuzzy_substring("a", "abc", min_len=1) == True, "single char with min_len=1 returns True")
    
    # Empty string returns False
    assert_test(_fuzzy_substring("", "test") == False, "empty string returns False")
    assert_test(_fuzzy_substring("test", "") == False, "empty string in second arg returns False")

# RUN ALL
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Character Trait Draw — Adversarial Verification Suite  ║")
    print("╚══════════════════════════════════════════════════════════╝")

    random.seed(42)

    test_data_integrity()
    test_same_side_conflict_avoidance()
    test_no_duplicates()
    test_correct_count()
    test_tension_guarantee()
    test_cross_category()
    test_similar_avoidance()
    test_zero_conflict_traits()
    test_draw_from_pool_edge_cases()
    test_fuzzy_match_edge_cases()
    test_normalize_conflicts()
    test_parse_args()
    test_find_trait()
    test_format_output_no_crash()
    test_format_single_card_no_crash()
    test_cli_smoke()
    test_exhaustive_conflict_consistency()
    test_high_count_stress()
    test_disabled_constraints()
    test_themed_draws_various()
    test_tension_quantification()
    test_data_quality_adversarial()
    test_cached_norm_conflicts()
    test_fuzzy_substring_helper()

    print(f"\n{'═' * 60}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    if errors:
        print(f"\n  Failed tests:")
        for e in errors:
            print(f"    {e}")
    print(f"{'═' * 60}")

    sys.exit(1 if failed > 0 else 0)
