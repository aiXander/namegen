"""Profile end-to-end generation matching the GUI's current config.yaml path.

Splits time between (a) Markov sampling proper and (b) the per-name
filtering (dedup / training-set exclusion / min_edit_distance), so we know
what to optimize. Run: uv run scripts/profile_generation.py
"""
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from markov_namegen import MarkovNameGenerator, too_close_to_training


def main():
    gen = MarkovNameGenerator()
    words = gen._load_training_data()
    print(f"training words: {len(words)}")

    from markov.name_generator import NameGenerator
    t0 = time.perf_counter()
    ng = NameGenerator(data=words,
                       order=gen.config['model']['order'],
                       temperature=gen.config['model']['temperature'],
                       backoff=gen.config['model']['backoff'])
    print(f"train time: {time.perf_counter() - t0:.2f}s")

    gen_cfg = gen.config['generation']
    training_set = set(words)
    min_distance = gen.config['filtering'].get('min_edit_distance', 0)

    names = set()
    target = 100
    sample_time = 0.0
    filter_time = 0.0
    attempts = 0
    none_returns = 0
    dup_or_training = 0
    edit_dist_rejects = 0

    t_start = time.perf_counter()
    while len(names) < target and time.perf_counter() - t_start < 120:
        t0 = time.perf_counter()
        name = ng.generate_name(
            min_length=gen_cfg['min_length'], max_length=gen_cfg['max_length'],
            starts_with=gen_cfg.get('starts_with', ''), ends_with=gen_cfg.get('ends_with', ''),
            includes=gen_cfg.get('includes', ''), excludes=gen_cfg.get('excludes', ''))
        sample_time += time.perf_counter() - t0
        attempts += 1
        if name is None:
            none_returns += 1
            continue

        t0 = time.perf_counter()
        keep = True
        if name in names or name in training_set:
            keep = False
            dup_or_training += 1
        elif too_close_to_training(name, training_set, min_distance):
            keep = False
            edit_dist_rejects += 1
        filter_time += time.perf_counter() - t0
        if keep:
            names.add(name)

    total = time.perf_counter() - t_start
    print(f"\ngot {len(names)}/{target} names in {total:.2f}s over {attempts} attempts")
    print(f"  sampling time:  {sample_time:.2f}s ({sample_time/total*100:.0f}%)")
    print(f"  filtering time: {filter_time:.2f}s ({filter_time/total*100:.0f}%)")
    print(f"  sampler None-returns: {none_returns} ({none_returns/attempts*100:.0f}% of attempts)")
    print(f"  dup/training rejects: {dup_or_training}")
    print(f"  edit-distance rejects: {edit_dist_rejects}")
    print(f"  per-attempt sample cost: {sample_time/attempts*1000:.2f}ms")

    # cProfile a slice of pure sampling to see hot functions
    print("\n--- cProfile: 300 generate_name calls ---")
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(300):
        ng.generate_name(
            min_length=gen_cfg['min_length'], max_length=gen_cfg['max_length'],
            starts_with=gen_cfg.get('starts_with', ''), ends_with=gen_cfg.get('ends_with', ''),
            includes=gen_cfg.get('includes', ''), excludes=gen_cfg.get('excludes', ''))
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats('cumulative').print_stats(15)
    print(s.getvalue())


if __name__ == '__main__':
    main()
