"""Smoke test: compile + exec both demo .su files and print outputs.

Run from anywhere:
    python examples/_smoke_test.py

Exit code 0 on pass (outputs match hardcoded expected tables), 1 on fail.
"""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Shared compile helper reads `// @embedding: <model>` directives from
# the top of each .su file; absent a directive, the codegen defaults
# (nomic-embed-text, 768-dim) apply. See examples/_su_harness.py.
from _su_harness import compile_to_module  # noqa: E402


def run_hello_world() -> bool:
    path = os.path.join(HERE, "hello_world.su")
    mod = compile_to_module(path)
    print("=" * 72)
    print("Example 0: hello_world.su (embed + retrieve — the minimal program)")
    print("=" * 72)
    got = mod.say()
    exp = "hello world"
    mark = "OK" if got == exp else "FAIL"
    print(f"  say() expected={exp!r} got={got!r} {mark}")
    print()
    return got == exp


def run_fuzzy_branching() -> bool:
    path = os.path.join(HERE, "fuzzy_branching.su")
    mod = compile_to_module(path)
    inputs = [
        ("vinegar + hungry", mod.smell_present, mod.hunger_hungry),
        ("vinegar + fed",    mod.smell_present, mod.hunger_fed),
        ("clean_air + hungry", mod.smell_absent, mod.hunger_hungry),
        ("clean_air + fed",    mod.smell_absent, mod.hunger_fed),
    ]
    expected = {
        "A": ["approach", "ignore",   "search",   "idle"],
        "B": ["search",   "idle",     "approach", "ignore"],
        "C": ["ignore",   "approach", "idle",     "search"],
        "D": ["idle",     "search",   "ignore",   "approach"],
    }
    fns = {"A": mod.program_A, "B": mod.program_B,
           "C": mod.program_C, "D": mod.program_D}

    print("=" * 72)
    print("Example 1: fuzzy_branching.su (weighted superposition conditionals)")
    print("=" * 72)
    total = 0
    correct = 0
    for prog in "ABCD":
        print(f"Program {prog}:")
        for i, (label, s, h) in enumerate(inputs):
            got = fns[prog](s, h)
            exp = expected[prog][i]
            mark = "OK" if got == exp else "FAIL"
            print(f"  {label:<22} expected={exp:<10} got={got:<10} {mark}")
            total += 1
            correct += got == exp
        print()
    print(f"{correct}/{total} decisions match expected")
    return correct == total


def run_role_filler() -> bool:
    path = os.path.join(HERE, "role_filler_record.su")
    mod = compile_to_module(path)
    records = [
        ("alice",  "red",   "circle",
         mod.f_alice, mod.f_red,  mod.f_circle),
        ("bob",    "blue",  "square",
         mod.f_bob,   mod.f_blue, mod.f_square),
    ]
    print("=" * 72)
    print("Example 2: role_filler_record.su (bind/bundle/unbind records)")
    print("=" * 72)
    total = 0
    correct = 0
    for name_lbl, color_lbl, shape_lbl, name_v, color_v, shape_v in records:
        rec = mod.make_record(name_v, color_v, shape_v)
        queries = [
            ("r_name",  mod.r_name,  name_lbl),
            ("r_color", mod.r_color, color_lbl),
            ("r_shape", mod.r_shape, shape_lbl),
        ]
        print(f"record = make_record({name_lbl}, {color_lbl}, {shape_lbl})")
        for role_lbl, role_v, exp in queries:
            got = mod.decode_field(rec, role_v)
            mark = "OK" if got == exp else "FAIL"
            print(f"  decode_field(record, {role_lbl:<8}) expected={exp:<8} got={got:<8} {mark}")
            total += 1
            correct += got == exp
        print()
    print(f"{correct}/{total} decodes match expected")
    return correct == total


def run_classifier() -> bool:
    path = os.path.join(HERE, "classifier.su")
    mod = compile_to_module(path)
    tests = [
        ("fruit_apple", mod.fruit_apple, "fruit"),
        ("fruit_pear",  mod.fruit_pear,  "fruit"),
        ("fruit_mango", mod.fruit_mango, "fruit"),
        ("veh_car",     mod.veh_car,     "vehicle"),
        ("veh_truck",   mod.veh_truck,   "vehicle"),
        ("veh_bike",    mod.veh_bike,    "vehicle"),
        ("tool_hammer", mod.tool_hammer, "tool"),
        ("tool_saw",    mod.tool_saw,    "tool"),
        ("tool_drill",  mod.tool_drill,  "tool"),
    ]
    print("=" * 72)
    print("Example 3: classifier.su (bundled prototype classifier)")
    print("=" * 72)
    total = 0
    correct = 0
    for label, vec, exp in tests:
        got = mod.classify(vec)
        mark = "OK" if got == exp else "FAIL"
        print(f"  classify({label:<12}) expected={exp:<8} got={got:<8} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} classifications match expected")
    return correct == total


def run_analogy() -> bool:
    path = os.path.join(HERE, "analogy.su")
    mod = compile_to_module(path)
    tests = [
        ("paris",  mod.paris,  "france"),
        ("tokyo",  mod.tokyo,  "japan"),
        ("london", mod.london, "uk"),
        ("rome",   mod.rome,   "italy"),
        ("cairo",  mod.cairo,  "egypt"),
    ]
    print("=" * 72)
    print("Example 4: analogy.su (associative pair memory: capital -> country)")
    print("=" * 72)
    total = 0
    correct = 0
    for lbl, v, exp in tests:
        got = mod.country_of(v)
        mark = "OK" if got == exp else "FAIL"
        print(f"  country_of({lbl:<6}) expected={exp:<8} got={got:<8} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} recalls match expected")
    return correct == total


def run_knowledge_graph() -> bool:
    path = os.path.join(HERE, "knowledge_graph.su")
    mod = compile_to_module(path)
    tests = [
        ("dog has",   mod.dog,   mod.has, "fur"),
        ("cat has",   mod.cat,   mod.has, "claws"),
        ("fish has",  mod.fish,  mod.has, "scales"),
        ("bird can",  mod.bird,  mod.can, "fly"),
        ("whale can", mod.whale, mod.can, "swim"),
    ]
    print("=" * 72)
    print("Example 5: knowledge_graph.su (bundled triples, compositional query)")
    print("=" * 72)
    total = 0
    correct = 0
    for lbl, s, p, exp in tests:
        got = mod.lookup_object(s, p)
        mark = "OK" if got == exp else "FAIL"
        print(f"  lookup_object({lbl:<10}) expected={exp:<8} got={got:<8} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} triple queries match expected")
    return correct == total


def run_predicate_lookup() -> bool:
    path = os.path.join(HERE, "predicate_lookup.su")
    mod = compile_to_module(path)
    objs = [
        ("cats",     mod.cats),
        ("dogs",     mod.dogs),
        ("fish",     mod.fish),
        ("birds",    mod.birds),
        ("hamsters", mod.hamsters),
    ]
    queries = [
        ("alice", mod.alice, {"cats", "dogs"}),
        ("bob",   mod.bob,   {"fish", "birds"}),
        ("carol", mod.carol, {"hamsters"}),
    ]
    print("=" * 72)
    print("Example 6: predicate_lookup.su (multi-object superposition)")
    print("=" * 72)
    total = 0
    correct = 0
    for subj_lbl, subj, members in queries:
        scores = {o_lbl: mod.fits(subj, mod.likes, o) for o_lbl, o in objs}
        min_member = min(scores[m] for m in members)
        max_nonmember = max(s for k, s in scores.items() if k not in members)
        ok = min_member > max_nonmember
        mark = "OK" if ok else "FAIL"
        member_str = "+".join(sorted(members))
        print(
            f"  {subj_lbl:<5} likes {member_str:<14} "
            f"min_member={min_member:+.3f} max_nonmember={max_nonmember:+.3f} {mark}"
        )
        total += 1
        correct += ok
    print()
    print(f"{correct}/{total} queries separate members from non-members")
    return correct == total


def run_fuzzy_dispatch() -> bool:
    path = os.path.join(HERE, "fuzzy_dispatch.su")
    mod = compile_to_module(path)
    tests = [
        ("weather", mod.q_weather, "lookup:weather"),
        ("music",   mod.q_music,   "start:music"),
        ("timer",   mod.q_timer,   "start:timer"),
        ("cancel",  mod.q_cancel,  "stop:alarm"),
    ]
    print("=" * 72)
    print("Example 7: fuzzy_dispatch.su (N-way dispatch, structured records)")
    print("=" * 72)
    total = 0
    correct = 0
    for lbl, q, exp in tests:
        got = mod.dispatch(q)
        mark = "OK" if got == exp else "FAIL"
        print(f"  dispatch({lbl:<7}) expected={exp:<16} got={got:<16} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} dispatches match expected")
    return correct == total


def run_nearest_phrase() -> bool:
    path = os.path.join(HERE, "nearest_phrase.su")
    mod = compile_to_module(path)
    phrase_pairs = [
        (f"p{i:02d}", getattr(mod, f"p{i:02d}"), mod.PHRASE_NAME)
        for i in range(1, 21)
    ]
    expected_clean = [
        "the quick brown fox", "hello world", "goodbye cruel world",
        "how are you today", "what is your name", "i am fine thanks",
        "please and thank you", "can you help me", "see you tomorrow",
        "have a nice day", "good morning friend", "good night sleep well",
        "lets get coffee", "whats for dinner", "turn on the lights",
        "play some music", "set an alarm", "tell me a joke",
        "remind me later", "whats the weather",
    ]
    noisy_tests = [
        (mod.p02, mod.p05, "hello world"),
        (mod.p16, mod.p01, "play some music"),
        (mod.p20, mod.p13, "whats the weather"),
        (mod.p17, mod.p09, "set an alarm"),
        (mod.p11, mod.p18, "good morning friend"),
    ]
    print("=" * 72)
    print("Example 8: nearest_phrase.su (20-phrase codebook, clean + noisy)")
    print("=" * 72)
    total = 0
    correct = 0
    for (lbl, v, _), exp in zip(phrase_pairs, expected_clean):
        got = mod.nearest(v)
        mark = "OK" if got == exp else "FAIL"
        print(f"  nearest({lbl}) expected={exp:<22} got={got:<22} {mark}")
        total += 1
        correct += got == exp
    for t, d, exp in noisy_tests:
        got = mod.nearest_noisy(t, d)
        mark = "OK" if got == exp else "FAIL"
        print(f"  nearest_noisy(...)       expected={exp:<22} got={got:<22} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} retrievals match expected")
    return correct == total


def run_sequence() -> bool:
    path = os.path.join(HERE, "sequence.su")
    mod = compile_to_module(path)
    positions = [mod.pos_0, mod.pos_1, mod.pos_2, mod.pos_3, mod.pos_4]
    fox_exp = ["the", "quick", "brown", "fox", "jumps"]
    dog_exp = ["a", "lazy", "brown", "dog", "sleeps"]
    print("=" * 72)
    print("Example 9: sequence.su (position-bound bundle, 2 x 5-token sequences)")
    print("=" * 72)
    total = 0
    correct = 0
    for name, seq, exp in [("seq_fox", mod.seq_fox, fox_exp), ("seq_dog", mod.seq_dog, dog_exp)]:
        for i, p in enumerate(positions):
            got = mod.decode_at(seq, p)
            mark = "OK" if got == exp[i] else "FAIL"
            print(f"  decode_at({name}, pos_{i}) expected={exp[i]:<8} got={got:<8} {mark}")
            total += 1
            correct += got == exp[i]
    sim_ff = mod.seq_similarity(mod.seq_fox, mod.seq_fox)
    sim_fd = mod.seq_similarity(mod.seq_fox, mod.seq_dog)
    sim_ok = sim_ff > 0.99 and 0.0 < sim_fd < 0.5
    mark = "OK" if sim_ok else "FAIL"
    print(f"  sim(fox,fox)={sim_ff:+.3f}  sim(fox,dog)={sim_fd:+.3f}  (expect self~=1.0, disjoint-with-shared-pos2 in (0, 0.5)) {mark}")
    total += 1
    correct += sim_ok
    print()
    print(f"{correct}/{total} sequence checks match expected")
    return correct == total


def run_loop_rotation() -> bool:
    path = os.path.join(HERE, "loop_rotation.su")
    mod = compile_to_module(path)
    # Haar-random rotation from a fixed seed; the trajectory is
    # deterministic but spec-agnostic about which codebook entry each
    # start ends up nearest to. Pin whatever the fixed seed produces —
    # the demo is about the loop(cond) + snap mechanics, not about
    # "loop converges to dog."
    expected = {
        "cat":    "bird",
        "dog":    "cat",
        "bird":   "bird",
        "fish":   "cat",
        "rabbit": "fish",
    }
    print("=" * 72)
    print("Example 10: loop_rotation.su (eigenrotation + snap terminal commit)")
    print("=" * 72)
    total = 0
    correct = 0
    for start_name, exp in expected.items():
        start_vec = getattr(mod, f"v_{start_name}")
        got = mod.wander_then_snap(start_vec)
        mark = "OK" if got == exp else "FAIL"
        print(f"  wander_then_snap(v_{start_name:<6}) expected={exp:<6} got={got:<6} {mark}")
        total += 1
        correct += got == exp
    print()
    print(f"{correct}/{total} loop+snap results match expected")
    return correct == total


def run_counter_loop() -> bool:
    path = os.path.join(HERE, "counter_loop.su")
    mod = compile_to_module(path)
    # Deterministic under seed=42. The step_* prototype that the
    # terminal state snaps to is the substrate's realization of the
    # iteration count — the demo is of the mechanism, not of a
    # particular count.
    exp = "step_five"
    print("=" * 72)
    print("Example 11: counter_loop.su (loop(cond) as helical counter, Turing)")
    print("=" * 72)
    got = mod.main()
    mark = "OK" if got == exp else "FAIL"
    print(f"  count_then_snap() expected={exp!r} got={got!r} {mark}")
    print()
    return got == exp


def main() -> int:
    ok0 = run_hello_world()
    ok1 = run_fuzzy_branching()
    print()
    ok2 = run_role_filler()
    print()
    ok3 = run_classifier()
    print()
    ok4 = run_analogy()
    print()
    ok5 = run_knowledge_graph()
    print()
    ok6 = run_predicate_lookup()
    print()
    ok7 = run_fuzzy_dispatch()
    print()
    ok8 = run_nearest_phrase()
    print()
    ok9 = run_sequence()
    print()
    ok10 = run_loop_rotation()
    print()
    ok11 = run_counter_loop()
    print()
    print("=" * 72)
    if all([ok0, ok1, ok2, ok3, ok4, ok5, ok6, ok7, ok8, ok9, ok10, ok11]):
        print("PASS")
        return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
