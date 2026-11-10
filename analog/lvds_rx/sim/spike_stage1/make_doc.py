#!/usr/bin/env python3
"""make_doc.py -- assemble docs/SPIKE_STAGE1.md from doc_template.md and the generated tables (sim/spike_stage1/results/tables.md)."""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
tpl = open(os.path.join(ROOT, 'sim', 'spike_stage1', 'doc_template.md')).read()
tab = open(os.path.join(ROOT, 'sim', 'spike_stage1', 'results', 'tables.md')).read()
open(os.path.join(ROOT, 'docs', 'SPIKE_STAGE1.md'), 'w').write(tpl.replace('{{TABLES}}', tab))
print('wrote docs/SPIKE_STAGE1.md')
