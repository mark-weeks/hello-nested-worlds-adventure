"""Summarize separately consented pilot observations; never reads/writes the world DB.

Input: a JSON list, one pseudonymous participant per row. Missing observations
remain unknown. Return measurements distinguish an unprompted second visit from
an answer to a reminder. The operator chooses the evidence window before recruiting.
"""
import argparse
import json
from pathlib import Path

METRICS = ('curiosity', 'understood_choice', 'unprompted_return', 'useful_return')


def report(rows):
    if not isinstance(rows, list):
        raise ValueError('Expected one list of participant observations.')
    seen = set()
    result = {metric: {'yes': 0, 'observed': 0, 'unknown': 0} for metric in METRICS}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('participant'), str) or not row['participant'].strip():
            raise ValueError('Each observation needs a pseudonymous participant.')
        if row['participant'] in seen:
            raise ValueError('Use one row per participant, not one per session.')
        seen.add(row['participant'])
        for metric in METRICS:
            value = row.get(metric)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f'{metric} must be true, false, or null.')
            if metric == 'unprompted_return' and value and row.get('reminded') is not False:
                raise ValueError('An unprompted return requires reminded=false evidence.')
            bucket = result[metric]
            bucket['unknown' if value is None else 'observed'] += 1
            if value is True:
                bucket['yes'] += 1
    return {'participants': len(seen), 'metrics': result,
            'interpretation': 'Observation counts; no causal attribution or retention claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observations', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(report(json.loads(args.observations.read_text())), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
