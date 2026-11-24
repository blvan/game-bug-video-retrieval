"""Prepare deterministic, source-derived text conditions for the exploratory pilot."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTION_NAMES = {
    'problem': ('describe the bug', 'description of the bug', 'describe the issue',
                'bug description', 'description', 'summary'),
    'reproduction': ('steps to reproduce', 'steps to reproduce the behavior',
                     'to reproduce', 'reproduction steps', 'how to reproduce',
                     'steps to reproduce the problem', 'steps to reproduce actual behavior'),
    'expected': ('expected behavior', 'expected behaviour'),
    'actual': ('actual behavior', 'actual behaviour', 'current behavior', 'current behaviour'),
}
EXCLUDED = {
    'game and system information', 'operating system', 'openrct2 build', 'base game',
    'area(s) with this issue?', 'attach save file', 'attachments', 'screenshots',
    'screenshots and videos', 'logs', 'crash logs', 'system information',
    'hardware', 'environment', 'version', 'game version', 'supertux version',
    'client version', 'branch', 'commit hash', 'operating system version',
    'build', 'type', 'additional context', 'triage', 'ac version', 'ac hash/commit',
    'custom changes', 'server operating system', 'extra notes',
    'customizations', 'modules', 'server', 'ac rev. hash/commit',
    'additional debugging information',
}
PLACEHOLDERS = {'_no response_', 'no response', 'n/a', 'none', 'not applicable'}
HEADER = re.compile(r'^\s*#{1,6}\s+(.+?)\s*#*\s*$')
INLINE_HEADER = re.compile(
    r'^\s*(SuperTux version|Expected behavio[u]?r|Actual behavio[u]?r|'
    r'Steps to reproduce(?: actual behavior)?|Additional debugging information|Version|Operating system)\s*:\s*\|?\s*(.*)$', re.I)


def clean_text(text):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    # Remove visual/media HTML but retain surrounding report prose.
    text = re.sub(r'<(?:video|audio|picture)\b.*?</(?:video|audio|picture)>', '',
                  text, flags=re.I | re.S)
    text = re.sub(r'<(?:img|source)\b[^>]*>', '', text, flags=re.I)
    text = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', text)
    # Preserve semantic link labels while removing media labels and destinations.
    def link_label(match):
        label = match.group(1)
        if re.search(r'https?://|\.(?:mp4|webm|mov|mkv|gif|png|jpe?g|zip|gz)\b', label, re.I):
            return ''
        return label
    text = re.sub(r'\[([^\]]*)\]\([^\n]*?\)', link_label, text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\b[\w.-]+\.(?:mp4|webm|mov|mkv|gif|png|jpe?g)\b', '', text, flags=re.I)
    return text


def extract(body):
    chunks = []
    heading = ''
    content = []
    for line in clean_text(body.replace('\r\n', '\n')).splitlines():
        match = HEADER.match(line)
        legacy = INLINE_HEADER.match(line)
        if match or legacy:
            chunks.append((heading, content))
            heading = (match.group(1) if match else legacy.group(1)).strip().lower().rstrip(':')
            content = [] if match else [legacy.group(2)]
        else:
            content.append(line)
    chunks.append((heading, content))
    cleaned = []
    structured = defaultdict(list)
    for heading, lines in chunks:
        if heading in EXCLUDED:
            continue
        kept = []
        for line in lines:
            value = line.strip()
            if not value or value.lower() in PLACEHOLDERS:
                continue
            if re.fullmatch(r'[-=| ]+', value) or value.startswith('- ['):
                continue
            if re.match(r'(attached please find|steps to reproduce the behavior\s*:)', value, re.I):
                continue
            kept.append(value)
        text = '\n'.join(kept)
        if not text:
            continue
        cleaned.append(text)
        section = next((key for key, names in SECTION_NAMES.items() if heading in names), None)
        if section:
            structured[section].append(text)
    return '\n\n'.join(cleaned), {key: '\n\n'.join(values) for key, values in structured.items()}


def prepare(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['issue_url']].append(row)
    results = []
    for url, group in sorted(grouped.items()):
        first = group[0]
        if any((r['issue_title'], r['issue_body']) !=
               (first['issue_title'], first['issue_body']) for r in group):
            raise ValueError(f'Conflicting source snapshots for {url}')
        title = first['issue_title'].strip()
        cleaned, sections = extract(first['issue_body'])
        structured = '\n\n'.join(key.capitalize() + '\n' + sections[key]
                                   for key in SECTION_NAMES if key in sections)
        results.append({
            'issue_url': url, 'repository': first['repository'],
            'relevant_candidate_ids': sorted(r['candidate_id'] for r in group),
            'title_only': title,
            'title_cleaned_body': '\n\n'.join(x for x in (title, cleaned) if x),
            'title_structured': '\n\n'.join(x for x in (title, structured) if x),
            'missing_sections': [key for key in SECTION_NAMES if key not in sections],
        })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/validated/validated_pairs.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/review/rq2-clip-pilot.json')
    args = parser.parse_args()
    results = prepare(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'issues': len(results), 'relevant_pairs': sum(len(r['relevant_candidate_ids']) for r in results)}))


if __name__ == '__main__':
    main()
