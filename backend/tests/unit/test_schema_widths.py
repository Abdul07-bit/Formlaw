"""
Every value a CHECK constraint allows must fit its column. SQLite ignores VARCHAR lengths, so a too-narrow column only
fails on PostgreSQL — in production (e.g. missing_information.basis = 'referenced_in_documents' in VARCHAR(20)).
"""
from __future__ import annotations

import re

from sqlalchemy import CheckConstraint, String

from app.db.base import Base
import app.models  # noqa: F401  (registers every table)

_IN = re.compile(r"^\s*(\w+)\s+IN\s*\((.*)\)\s*$", re.S)


def test_check_constraint_values_fit_their_columns():
    checked, problems = 0, []
    for table in Base.metadata.tables.values():
        for c in table.constraints:
            if not isinstance(c, CheckConstraint):
                continue
            m = _IN.match(str(c.sqltext))
            if not m or m.group(1) not in table.c:
                continue
            col = table.c[m.group(1)]
            if not isinstance(col.type, String) or not col.type.length:
                continue
            longest = max(re.findall(r"'([^']*)'", m.group(2)), key=len)
            checked += 1
            if len(longest) > col.type.length:
                problems.append(f"{table.name}.{col.name}: '{longest}' ({len(longest)}) > VARCHAR({col.type.length})")
    assert checked > 15, "the scan is not finding the schema's constraints"
    assert not problems, problems
