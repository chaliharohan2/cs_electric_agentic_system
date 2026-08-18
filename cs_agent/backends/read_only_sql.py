"""One shared rule for what counts as a single read-only analytics query.

The SQLite backend opens its connection with ``mode=ro``, so a write cannot
reach the file whatever we let through; this check exists to turn an attempt
into a sentence the analyst can act on, and to protect the fixtures backend,
whose in-memory database is writable.
"""

from __future__ import annotations

import re

# Checks run against a copy with string literals blanked, so a semicolon or a
# keyword inside a LIKE pattern is not mistaken for syntax.
_LITERAL = re.compile(r"'(?:[^']|'')*'")
# The three statement forms SQLite will return rows for. WITH matters most: a
# common table expression is the natural way to stage a comparison, and it is
# what the analyst reaches for when asked to rank a named set of SKUs.
_READ_HEAD = re.compile(r"^\s*(?:select|with|values)\b", re.IGNORECASE)
# A write keyword only means a write in statement-head position — the start of
# the string, or the opening of a parenthesised CTE body. Searching for these
# anywhere would reject `coalesce(replace(...))` and any column whose name
# starts with one of them.
_WRITE_HEAD = re.compile(
    r"(?:^|\(|\bas\s*\()\s*"
    r"(?:insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum"
    r"|reindex|begin|commit|rollback|replace\s+into)\b",
    re.IGNORECASE,
)

_ONE_STATEMENT = "Send one statement per call: remove the ';' and anything after it."
_READ_ONLY = (
    "Only a read-only query is allowed. Start it with SELECT, WITH or VALUES "
    "and do not include a data-modifying statement. A leading "
    "WITH name AS (SELECT ...) common table expression is allowed."
)


def read_only_sql_error(statement: str) -> str | None:
    """Return why ``statement`` is not one read-only query, or None if it is.

    Each rejection names the specific thing to change. A single message for
    both faults tells the analyst nothing it did not already believe, and it
    spends a retry re-sending the same SQL.
    """
    probe = _LITERAL.sub("''", statement)
    if ";" in probe:
        return _ONE_STATEMENT
    if not _READ_HEAD.match(probe) or _WRITE_HEAD.search(probe):
        return _READ_ONLY
    return None
