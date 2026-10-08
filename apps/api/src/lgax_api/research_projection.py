"""Public summary counts checked against immutable inputs, without reclassifying reviews."""

from collections import Counter
from copy import deepcopy
from math import isfinite

from lgax_core.public_planning import is_customer_source, summary_reference_coverage


def project_source_statistics(brief: dict, bundle: dict | None) -> dict:
    if bundle is None:
        return {}
    facts = {row['source_id']: row['facts'] for row in brief['source_facts']}
    sources = [source for source in bundle['sources'] if source['source_id'] in facts]
    if (len(sources) != len(facts)
            or any(source['facts'] != facts[source['source_id']] for source in sources)):
        return {}
    result = {'source_type_counts': dict(Counter(source['source_type'] for source in sources))}
    customer_ids, groups = set(), set()
    for source in sources:
        group = source.get('duplicate_group') or source['source_id']
        if is_customer_source(source) and group not in groups:
            customer_ids.add(source['source_id'])
            groups.add(group)
    result['unique_customer_source_count'] = len(customer_ids)
    raw = brief['runtime'].get('summary_reference_coverage')
    if raw is None:
        result['summary_reference_coverage_state'] = 'unavailable'
        return result
    result['summary_reference_coverage_state'] = 'invalid'
    if not isinstance(raw, dict):
        return result
    denominator = raw.get('denominator_source_ids')
    if (not isinstance(denominator, list)
            or any(not isinstance(source_id, str) for source_id in denominator)
            or denominator != sorted(set(denominator))
            or not set(denominator) <= customer_ids):
        return result
    processed = brief['runtime'].get('processed_source_ids')
    if (not isinstance(processed, list)
            or any(not isinstance(source_id, str) for source_id in processed)
            or set(denominator) != set(processed) & customer_ids):
        return result
    expected = summary_reference_coverage(brief['summaries'], customer_ids, set(denominator))
    for key, value in expected.items():
        actual = raw.get(key)
        if key == 'coverage_ratio':
            if value is None:
                if actual is not None:
                    return result
            elif (type(actual) not in (int, float) or not isfinite(actual)
                  or not 0 <= actual <= 1 or abs(actual - value) > 1e-12):
                return result
        elif type(value) is int:
            if type(actual) is not int or actual != value:
                return result
        elif isinstance(value, dict):
            if not isinstance(actual, dict) or set(actual) != set(value):
                return result
            if any(type(actual[polarity]) is not type(count) or actual[polarity] != count
                   for polarity, count in value.items()):
                return result
        elif type(actual) is not type(value) or actual != value:
            return result
    result['summary_reference_coverage'] = deepcopy(expected)
    result['summary_reference_coverage_state'] = 'provided'
    return result
