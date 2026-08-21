"""Ways of turning a specialist's retrieval into the report a stage hands on.

The report node is the most expensive thing in a turn — 43-56% of wall time
across six measured runs, and roughly 90% of that is decode, because the model
is writing two thousand tokens of JSON at 38 tok/s. Most of those tokens are
not judgement. On the cheapest turn in the sample (`logs/map_wintrip2.jsonl`,
one `catalogue_map` call returning 2,395 chars) the report came back at 7,440
chars — three times the size of the data it describes — with the same five
families stated four times over: once in `families` verbatim from the tool,
again as prose in `findings`, a third time as `sources`, and a fourth in
`summary`. A further 15-23% of every report is the literal text `"field": null`.

So there are two separable questions, and this module exists to let a benchmark
answer them independently:

* **Who does the work** — a model writing prose, or code reading the tool
  payloads the pipeline already parsed once.
* **How much of it survives** — every fact retrieved, or the few the answer
  will actually use.

Selected with ``CS_REPORT_MODE``:

``llm``
    What the pipeline has always done. The baseline.
``lean``
    The same call, told to omit empty fields and to leave `sources` to be
    rebuilt in code. Tests how much of the report is pure schema overhead
    rather than content, and costs one paragraph of prompt to try.
``derived``
    No model call at all. The structural fields are read out of the tool
    payloads, and the findings out of the normalized evidence rows the
    specialist already produces. Free and exact, but it cannot write a summary
    that reads like judgement, and for `solution_advisory` there is nothing to
    read — a recommendation is not present in any payload — so that agent falls
    back to ``llm``.
``raw``
    ``derived``, plus the untouched tool payloads riding along for the composer
    to read. Loses nothing, and moves the cost from decode to prefill, which on
    this server runs 26x faster per token.
``auto``
    ``raw`` for an overview brief, ``llm`` for a detailed one.

Every mode returns something that validates against the agent's report schema,
because the gate, the digest, the composer and the session's focus tracking all
read those fields and none of them should have to know which mode ran.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

from langchain_core.messages import AnyMessage, ToolMessage

from cs_agent.backends.payload_shape import merge_scope
from cs_agent.contracts import brief_depth

MODES = ("llm", "derived", "raw", "auto")

# Fields a report's SourceRefs are never asked for, because the model would
# write `null` into them far more often than a value — measured across 503 refs
# at 0.6%, 3.4% and 3.4% populated — and because the payload that produced the
# value still has it. Hidden from the schema, then filled in by code, which also
# removes the chance of a page number being retyped wrong.
BACKFILLED = ("brochure_md", "pricelist_pdf", "pricelist_page", "product_page_url")

# `sources` is not asked for either. Half its entries already sit on a finding
# and the rest come straight from the payloads, so the whole list rebuilds
# exactly — 14.3% of everything the model writes at detailed depth, for nothing.
HIDDEN_REPORT_FIELDS = ("sources",)

# A hint in the schema rather than a pydantic constraint: a length violation
# there costs a whole retry generation, which is worse than an over-long list.
# Code trims afterwards, so the cap holds either way.
DEFAULT_FINDINGS_CAP = 12

# Ceiling on the rebuilt source index, for the same reason the findings have one.
MAX_SOURCES = 12


def slim_reports() -> bool:
    """Whether to ask for the trimmed report. Off restores the old prompt."""
    return (os.getenv("CS_REPORT_SLIM") or "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


def findings_cap() -> int:
    return _int_env("CS_REPORT_FINDINGS_CAP", DEFAULT_FINDINGS_CAP)

# How many findings a derived report keeps. The complaint this whole exercise
# started from is that a report carries evidence which pertains to the question
# without being needed to answer it; a cap is the bluntest possible answer to
# that, and the one a benchmark can actually attribute an effect to.
DEFAULT_MAX_FINDINGS = 24

# Ceiling on the raw payloads carried by `raw` mode. One `get_sku` call returns
# 25,935 chars, and a detailed spec_selection brief makes several: uncapped,
# this mode alone would fill the 80k-token window the endpoints are configured
# for. Truncation is recorded rather than hidden, so a benchmark can tell a
# genuine result from one that ran out of room.
DEFAULT_RAW_CHAR_BUDGET = 60_000

# An advisory report is a recommendation, and no tool returns one.
NOT_DERIVABLE = {"solution_advisory"}


def report_mode() -> str:
    mode = (os.getenv("CS_REPORT_MODE") or "auto").strip().lower()
    return mode if mode in MODES else "auto"


def resolve_mode(brief: dict[str, Any], agent: str) -> str:
    """The mode this particular brief runs under.

    ``auto`` is decided here rather than in the node so that the fallback for a
    non-derivable agent applies to every mode that would have skipped the model.
    """
    mode = report_mode()
    if mode == "auto":
        mode = "raw" if brief_depth(brief) == "overview" else "llm"
    if mode in {"derived", "raw"} and agent in NOT_DERIVABLE:
        return "llm"
    return mode


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ[name]))
    except (KeyError, ValueError):
        return default


def max_findings() -> int:
    return _int_env("CS_REPORT_MAX_FINDINGS", DEFAULT_MAX_FINDINGS)


def raw_char_budget() -> int:
    return _int_env("CS_REPORT_RAW_CHARS", DEFAULT_RAW_CHAR_BUDGET)


def _reference_index(items: list[tuple[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-SKU document references, read out of the payloads that carried them.

    Provenance sits on individual *facts*, not only on a price lookup: a
    `get_sku` fact carries `source_of_truth` alongside the `source_pdf` and
    `source_page` it was read from, and that is where a pricelist page actually
    comes from on a turn that never calls `get_price_detail`. Missing this shape
    cost the citation "LV-Pricelist-WEF-1st-June26.pdf, p. 42" on a run whose
    payloads plainly contained it.
    """
    index: dict[str, dict[str, Any]] = {}

    def note(sku: Any, **fields: Any) -> None:
        if not isinstance(sku, str) or not sku:
            return
        record = index.setdefault(sku, {})
        for key, value in fields.items():
            if value not in (None, "", []) and key not in record:
                record[key] = value

    def read_facts(rows: Any, default_sku: Any) -> None:
        for fact in rows or []:
            if not isinstance(fact, dict):
                continue
            sku = fact.get("sku_code") or default_sku
            if fact.get("source_of_truth") == "pricelist_table":
                note(
                    sku,
                    pricelist_pdf=fact.get("source_pdf"),
                    pricelist_page=fact.get("source_page"),
                )

    def read_one(payload: dict[str, Any]) -> None:
        sku = payload.get("sku_code")
        note(sku, product_page_url=payload.get("url"))
        # A hoisted `url` belongs to every hit in the payload, so it is the
        # product page for whichever of them is being read here.
        if not payload.get("url"):
            note(sku, product_page_url=(payload.get("scope") or {}).get("url"))
        read_facts(payload.get("facts"), sku)
        read_facts(payload.get("specs"), sku)
        price = payload.get("price")
        if isinstance(price, dict):
            read_facts([price], sku)
        for chunk in payload.get("chunks") or []:
            if isinstance(chunk, dict):
                note(chunk.get("sku_code") or sku, brochure_md=chunk.get("brochure_md"))

    for _tool, payload in items:
        if not isinstance(payload, dict):
            continue
        read_one(payload)
        for row in _search_hits(payload) + (payload.get("rows") or []):
            if isinstance(row, dict):
                read_one(row)
        for entry in payload.get("prices") or []:
            if not isinstance(entry, dict):
                continue
            for observation in entry.get("observations") or []:
                note(
                    entry.get("sku_code"),
                    pricelist_pdf=observation.get("source_pdf"),
                    pricelist_page=observation.get("source_page"),
                )
    return index


def _walk_refs(node: Any) -> Iterator[dict[str, Any]]:
    """Every SourceRef-shaped mapping inside a report, wherever it is nested."""
    if isinstance(node, dict):
        if "sku_code" in node and "statement" not in node and "why_it_fits" not in node:
            yield node
        for value in node.values():
            yield from _walk_refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_refs(value)


def backfill_report(
    report: dict[str, Any],
    messages: list[AnyMessage],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Restore the fields the slim schema did not ask the model to write.

    Every reference the model gave a sku_code gains whatever documents the
    payloads recorded against that SKU, and `sources` is rebuilt from the
    findings *and* the payloads together. Findings alone would not do it: only
    half of a measured 170 source entries also appeared on a finding, so
    rebuilding from findings would quietly drop the other half.
    """
    items = payloads(messages)
    index = _reference_index(items)
    for ref in _walk_refs(report):
        for key, value in index.get(str(ref.get("sku_code") or ""), {}).items():
            if ref.get(key) in (None, "", []):
                ref[key] = value
    if not report.get("sources"):
        # An index of what this report references, plus provenance for the SKUs
        # it named — not a log of everything the specialist retrieved. Rebuilding
        # from the payloads wholesale produced 20 entries where the model had
        # chosen 4, which is prompt weight the composer has to read past.
        named = {
            str(ref.get("sku_code"))
            for ref in _walk_refs(report)
            if ref.get("sku_code")
        }
        seen: dict[str, dict[str, Any]] = {}
        for ref in _walk_refs(report):
            seen.setdefault(json.dumps(ref, sort_keys=True, default=str), dict(ref))
        for ref in _sources(items, evidence):
            if ref.get("sku_code") and str(ref["sku_code"]) not in named:
                continue
            seen.setdefault(json.dumps(ref, sort_keys=True, default=str), ref)
        report["sources"] = list(seen.values())[:MAX_SOURCES]
    if len(report.get("findings") or []) > findings_cap():
        # The schema asked for this cap and the model is free to ignore it.
        report["findings"] = report["findings"][: findings_cap()]
    return report


def payloads(messages: list[AnyMessage]) -> list[tuple[str, Any]]:
    """Every successful tool result in the transcript, decoded, in order.

    Errors are dropped: a derived report is built only from what came back, and
    an error payload carries a `next_step` written for the model, not a fact.
    """
    out: list[tuple[str, Any]] = []
    for message in messages or []:
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "status", None) == "error":
            continue
        content: Any = message.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        if isinstance(content, dict) and content.get("error"):
            continue
        out.append((message.name or "unknown", content))
    return out


def _families(items: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    """Families named by any catalogue-shaped payload, first mention winning.

    `catalogue_map` publishes the whole record — path, count, description, URL —
    so it is read first and anything a later payload adds only fills gaps. A
    `taxonomy_browse` child is only a family when the walk has reached a leaf;
    higher up it is a category, and reporting one as a family is the mistake the
    taxonomy section of the agent prompt exists to prevent.
    """
    found: dict[str, dict[str, Any]] = {}

    def add(name: Any, targeted: bool, **fields: Any) -> None:
        if not isinstance(name, str) or not name.strip():
            return
        record = found.setdefault(
            name,
            {
                "name": name,
                "path": [],
                "description": None,
                "sku_count": 0,
                "url": None,
                "targeted": False,
            },
        )
        record["targeted"] = record["targeted"] or targeted
        for key, value in fields.items():
            if value not in (None, "", [], 0) and not record.get(key):
                record[key] = value

    for tool, payload in items:
        if not isinstance(payload, dict):
            continue
        if tool == "catalogue_map":
            for group in payload.get("groups") or []:
                if isinstance(group, dict):
                    add(
                        # `catalogue_map` keys the group on the column it
                        # matched; `name` was the older spelling of the same
                        # thing and is still accepted so an old trace replays.
                        group.get("family") or group.get("name"),
                        True,
                        path=group.get("path") or [],
                        description=group.get("description"),
                        sku_count=group.get("sku_count") or 0,
                        url=group.get("url"),
                    )
        elif tool == "taxonomy_browse":
            parent = payload.get("path") or []
            for child in payload.get("children") or []:
                if isinstance(child, dict) and child.get("is_leaf"):
                    add(
                        child.get("name"),
                        False,
                        path=[*parent, child.get("name")],
                        description=child.get("description"),
                        sku_count=child.get("sku_count") or 0,
                        url=child.get("url"),
                    )
        elif tool in {"product_search", "get_sku", "resolve_product"}:
            rows = _search_hits(payload) or (
                [payload] if payload.get("sku_code") else []
            )
            for row in rows:
                if isinstance(row, dict):
                    add(
                        row.get("family"),
                        True,
                        path=row.get("path") or [],
                        url=row.get("url"),
                    )
    return list(found.values())


# Families a derived report will carry. The same ceiling the digest uses, for
# the same reason: a downstream stage has to fit several of these at once.
MAX_FAMILIES = 8

# Tools that answer a question, against tools that list a place. `catalogue_map`
# and `product_search` were called with terms and return only what matched them,
# so every family they name is one the specialist was looking for.
# `taxonomy_browse` returns every child of a node whether or not it bears on the
# question, so its output is used to fill a gap, never to widen a result.
TARGETED = ("catalogue_map", "product_search", "resolve_product", "get_sku")


def _relevant(families: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Narrow to the families a targeted search named, if any did.

    Judging relevance by matching the question's words against family names was
    tried and abandoned: this catalogue names things the way the trade does and
    the customer does not. "What air circuit breakers do you have?" shares no
    word with `ACB - WiNmaster 3` but shares one with `Motor Protection Circuit
    Breakers`, so overlap scoring dropped all three ACB ranges and kept the one
    that was wrong. "List the wintrip products" likewise scored `WiNtrip2 MCB &
    Isolator` at zero — different token — and threw away the largest family of
    the five. Which family answers the question is judgement about the domain,
    and the tool that was called is the only trace of it left in the payload.
    """
    targeted = [family for family in families if family.get("targeted")]
    chosen = targeted or families
    return [
        {key: value for key, value in family.items() if key != "targeted"}
        for family in chosen[:MAX_FAMILIES]
    ]


def _skus(items: list[tuple[str, Any]]) -> list[str]:
    """Ordering codes the retrieval actually reached, in the order it saw them."""
    codes: list[str] = []
    for tool, payload in items:
        if not isinstance(payload, dict):
            continue
        rows = _search_hits(payload) or payload.get("prices") or []
        if payload.get("sku_code"):
            rows = [payload, *rows]
        for row in rows:
            if isinstance(row, dict) and (code := row.get("sku_code")):
                codes.append(str(code))
        for code in payload.get("sku_codes") or []:
            codes.append(str(code))
    return list(dict.fromkeys(codes))


def _statement(row: dict[str, Any]) -> str:
    """One evidence row as a sentence, without inventing anything."""
    value = row.get("value_display")
    if value is None and row.get("value_num") is not None:
        value = row["value_num"]
    unit = f" {row['unit']}" if row.get("unit") and value is not None else ""
    if row.get("sku_code") and row.get("spec_id"):
        return f"{row['sku_code']} {row['spec_id']}: {value}{unit}"
    if row.get("spec_id"):
        return f"{row['spec_id']}: {value}{unit}"
    return str(row.get("text") or value or "").strip()


def _findings(
    evidence: list[dict[str, Any]], brief: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    """The evidence rows worth carrying, most relevant first, then capped.

    Relevance is judged against the brief rather than the question: a spec the
    brief asked for by name is the reason the specialist ran, and a row carrying
    a value against a named ordering code is the only kind a downstream stage can
    cite. Everything else is retrieval that happened to come back in the same
    payload — true, on topic, and not what the answer needs.
    """
    wanted = " ".join(
        str(part).lower()
        for part in (
            *(brief.get("must_return") or []),
            *(brief.get("parameters") or {}).keys(),
            brief.get("objective") or "",
        )
    )

    def rank(row: dict[str, Any]) -> tuple[int, int]:
        spec = str(row.get("spec_id") or "").lower()
        named = 0 if spec and spec in wanted else 1
        cited = 0 if row.get("sku_code") and row.get("spec_id") else 1
        return (named, cited)

    ordered = sorted(
        (row for row in evidence if _statement(row)),
        key=rank,
    )
    findings: list[dict[str, Any]] = []
    for row in ordered[:limit]:
        specification = bool(row.get("sku_code") and row.get("spec_id"))
        source: dict[str, Any] | None = None
        if row.get("sku_code") or row.get("source_of_truth"):
            source = {
                "sku_code": row.get("sku_code"),
                "source_of_truth": row.get("source_of_truth"),
            }
        findings.append(
            {
                "statement": _statement(row),
                # The gate wants a scope behind every specification claim — a
                # sku_code, or a family when the claim is about the range. An
                # evidence row carries neither unless it names a SKU, so
                # anything without one is a catalogue fact by construction here,
                # which is both true and the only classification code can defend.
                "kind": "specification" if specification and source else "catalogue",
                "source": source,
            }
        )
    return findings


def _sources(items: list[tuple[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Where the findings came from, deduplicated on the whole reference."""
    refs: list[dict[str, Any]] = []
    for _tool, payload in items:
        if not isinstance(payload, dict):
            continue
        for price in payload.get("prices") or []:
            for observation in (price.get("observations") or []) if isinstance(price, dict) else []:
                refs.append(
                    {
                        "sku_code": price.get("sku_code"),
                        "pricelist_pdf": observation.get("source_pdf"),
                        "pricelist_page": observation.get("source_page"),
                        "source_of_truth": "pricelist_table",
                    }
                )
        url = payload.get("url") or (payload.get("scope") or {}).get("url")
        if url:
            refs.append({"sku_code": payload.get("sku_code"), "product_page_url": url})
        for row in (payload.get("groups") or []) + (payload.get("children") or []):
            if isinstance(row, dict) and row.get("url"):
                refs.append({"product_page_url": row["url"]})
    for row in evidence:
        if row.get("sku_code") and row.get("source_of_truth"):
            refs.append(
                {"sku_code": row["sku_code"], "source_of_truth": row["source_of_truth"]}
            )
    unique: dict[str, dict[str, Any]] = {}
    for ref in refs:
        unique.setdefault(json.dumps(ref, sort_keys=True), ref)
    return list(unique.values())


def _counted(families: list[dict[str, Any]]) -> str:
    parts = [
        f"{family['name']} ({family['sku_count']})" if family.get("sku_count") else family["name"]
        for family in families[:8]
    ]
    return ", ".join(parts)


def _filters_applied(items: list[tuple[str, Any]]) -> list[str]:
    applied: list[str] = []
    searched: list[str] = []
    for tool, payload in items:
        if tool not in {"product_search", "resolve_product", "get_peer_group"}:
            continue
        if isinstance(payload, dict):
            applied.extend(str(item) for item in payload.get("filters_applied") or [])
            searched.append(tool)
    # The gate will not accept an empty shortlist without something in
    # filters_tried, and a search that applied no spec filter still tried
    # something. Naming the tool is the honest version of that.
    return list(dict.fromkeys(applied)) or [
        f"{tool} returned no ordering code" for tool in dict.fromkeys(searched)
    ]


def _search_hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The SKU rows in a `product_search` result, grouped or not.

    A grouped search answers "which of these families have X" and puts its rows
    under `groups[].sample_hits` instead of `hits`, so reading `hits` alone
    sees an empty result where the payload in fact carries every group.

    Each row is returned with the payload's `scope` merged back underneath it.
    `product_search` hoists `family`, `path` and `url` out of the hits when all
    of them agree, which scoped to one family is always — and a derived report
    indexes hits by exactly those three. The row's own value wins where it has
    one, so this reads correctly whether or not the hoist fired.
    """
    rows = list(payload.get("hits") or [])
    for group in payload.get("groups") or []:
        if isinstance(group, dict):
            rows.extend(
                row for row in group.get("sample_hits") or [] if isinstance(row, dict)
            )
    return [merge_scope(payload, row) for row in rows]


def _candidates(items: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    """Ordering codes paired with the filters that actually returned them.

    A specialist runs several searches on its way to an answer, and the filters
    of one say nothing about the hits of another. Collecting all the codes and
    all the filters separately and pairing them afterwards produced reports
    claiming `CSCOS2P25A` — a 25 A two-pole device — "matches rated_current_a eq
    400, poles eq 4", because a search that found nothing at 400 A contributed
    its filters to codes a later unfiltered search had returned. The gate cannot
    catch that: the shape is valid and only the meaning is wrong.

    So the pairing is kept where the payload already has it — each result's
    `filters_applied` belongs to that result's `hits` and to nothing else.
    """
    found: dict[str, str] = {}
    for tool, payload in items:
        if not isinstance(payload, dict):
            continue
        if tool == "product_search":
            applied = [str(item) for item in payload.get("filters_applied") or []]
            why = (
                "Matches " + ", ".join(applied)
                if applied
                else "Returned by a catalogue search with no specification filter"
            )
            rows = _search_hits(payload)
        elif tool in {"get_sku", "resolve_product"}:
            why = "Retrieved directly by ordering code"
            rows = [payload] if payload.get("sku_code") else []
        else:
            continue
        for row in rows:
            if isinstance(row, dict) and (code := row.get("sku_code")):
                # First claim wins: a code first seen under a real filter keeps
                # that provenance rather than being overwritten by a later
                # unfiltered sweep that happened to return it again.
                found.setdefault(str(code), why)
    return [{"sku_code": code, "why_it_fits": why, "key_specs": []} for code, why in found.items()]


def _table(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """The comparison table, taken from `compare_skus` rather than rewritten.

    This is the one report field a tool returns in exactly the shape the schema
    wants, which makes it the clearest case in the whole exercise: asking a
    model to retype it can only introduce error.
    """
    axes: list[str] = []
    rows: dict[str, dict[str, Any]] = {}
    match = False
    for tool, payload in items:
        if tool != "compare_skus" or not isinstance(payload, dict):
            continue
        axes.extend(str(axis) for axis in payload.get("axes") or [])
        for axis, values in (payload.get("rows") or {}).items():
            if isinstance(values, dict):
                rows.setdefault(str(axis), {}).update(values)
        match = match or bool(payload.get("peer_group_match"))
    return {"axes": list(dict.fromkeys(axes)), "rows": rows, "peer_group_match": match}


def _standards(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Facts that read as a standards or certification claim.

    Matched on the spec_id, because that is the catalogue's own vocabulary; a
    claim keyed on anything else could not be cited back to a SKU.
    """
    markers = ("standard", "certif", "ip_rating", "conform", "approval", "iec", "is_")
    claims = []
    for row in evidence:
        spec = str(row.get("spec_id") or "").lower()
        if not row.get("sku_code") or not spec or not any(m in spec for m in markers):
            continue
        value = row.get("value_display") or row.get("value_num")
        if value is None:
            continue
        claims.append(
            {
                "sku_code": row["sku_code"],
                "spec_id": row["spec_id"],
                "value_display": str(value),
                "source_of_truth": row.get("source_of_truth"),
                "source": {
                    "sku_code": row["sku_code"],
                    "source_of_truth": row.get("source_of_truth"),
                },
            }
        )
    return claims


def _follow_ups(families: list[dict[str, Any]]) -> list[str]:
    """Questions an overview closes on, built from what it found.

    Templated, and it shows: these are the one part of a report that is pure
    judgement, and the reason a derived overview reads flatter than a written
    one even when every fact in it is identical.
    """
    questions = ["Would you like ordering codes and ratings for any of these ranges?"]
    if families:
        questions.append(f"Shall I go deeper on {families[0]['name']}?")
    questions.append("Do you need prices, or a particular rating or pole count?")
    return questions


def derive_report(
    agent: str,
    brief: dict[str, Any],
    messages: list[AnyMessage],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a specialist report from the retrieval, with no model call.

    Every field here is copied or counted, never composed, so the report cannot
    contain a fact the tools did not return — which is the property the gate and
    rule 15 of the composer prompt are both trying to enforce by inspection.
    """
    items = payloads(messages)
    families = _relevant(_families(items))
    skus = _skus(items)
    findings = _findings(evidence, brief, max_findings())
    overview = brief_depth(brief) == "overview"

    report: dict[str, Any] = {
        "agent": agent,
        "status": "complete" if (families or skus or findings) else "no_result",
        "summary": "",
        "findings": findings,
        "sources": _sources(items, evidence),
        "gaps": [],
        "caveats": [],
    }

    if agent == "discovery":
        report["families"] = families
        report["representative_skus"] = [] if overview else skus[:8]
        report["follow_up_questions"] = _follow_ups(families) if overview else []
        total = sum(family.get("sku_count") or 0 for family in families)
        report["summary"] = (
            f"{len(families)} families"
            + (f" totalling {total} SKUs" if total else "")
            + (f": {_counted(families)}." if families else ".")
        ) if families else "No family matched this objective."
    elif agent == "spec_selection":
        applied = _filters_applied(items)
        matched = [item for item in applied if " returned no ordering code" not in item]
        candidates = _candidates(items)
        report["candidates"] = candidates[:MAX_FAMILIES]
        report["filters_tried"] = applied
        if not candidates:
            report["no_candidates_reason"] = (
                "No ordering code came back from the searches this brief ran."
            )
            # The gate reads an empty shortlist as acceptable only when the
            # report also says what was attempted, so this pairing is not
            # optional — a brief that reached the report node having called no
            # search at all still has to account for itself.
            report["filters_tried"] = applied or ["no product search was run"]
        shown = [
            entry["sku_code"] for entry in report["candidates"] if entry.get("sku_code")
        ]
        report["summary"] = (
            f"{len(candidates)} ordering codes came back"
            + (f" from searches filtered on {', '.join(matched)}" if matched else "")
            + (f": {', '.join(shown)}." if shown else ".")
        )
    elif agent == "comparison":
        table = _table(items)
        report["peer_group_match"] = table.pop("peer_group_match")
        report["table"] = table
        report["differentiators"] = []
        codes = sorted({code for values in table["rows"].values() for code in values})
        report["summary"] = (
            f"Compared {len(codes)} ordering codes on {len(table['axes'])} axes."
            if codes
            else "No comparison table was retrieved."
        )
        if len(codes) < 2:
            report["status"] = "no_result"
            report["gaps"] = ["Fewer than two ordering codes resolved for comparison."]
    elif agent == "compliance":
        standards = _standards(evidence)
        report["standards"] = standards
        report["certifications"] = []
        report["not_established"] = (
            [] if standards else ["No standards or certification fact was retrieved."]
        )
        report["summary"] = (
            f"{len(standards)} standards claims across "
            f"{len({claim['sku_code'] for claim in standards})} ordering codes."
            if standards
            else "No standards claim was retrieved."
        )
    return report


# What each agent's report has to carry for the rest of the pipeline to work.
# An empty one is not merely a thin answer: the gate accepts it as a valid
# `no_result`, and the composer's sufficiency check then spends revision rounds
# trying to fill a gap no retry can close. One measured comparison did that for
# 1,156 seconds — 2.3x the baseline — across three specialist rounds and 38 tool
# calls, and refused to answer at the end of it.
CORE_FIELD = {
    "discovery": "families",
    "spec_selection": "candidates",
    "comparison": "table",
    "compliance": "standards",
}


def derived_core_is_empty(agent: str, report: dict[str, Any]) -> bool:
    """Whether derivation found nothing the downstream stages can use.

    The comparison table is the one that actually goes wrong in practice: it can
    only be read from `compare_skus`, and a specialist is free to answer the
    same brief with `product_search` and `analytics_query` instead, which it did.
    """
    field = CORE_FIELD.get(agent)
    if field is None:
        return False
    value = report.get(field)
    if field == "table":
        return not (value or {}).get("rows")
    return not value


def needs_model_fallback(mode: str, agent: str, report: dict[str, Any]) -> bool:
    """Whether to write this report with the model after all.

    Only `derived` falls back. `raw` carries the tool payloads alongside the
    report, so a composer facing an empty structured core can still read what
    was retrieved — measured at 426s against the model's 500s on exactly the
    comparison that sent `derived` into a revision loop. Falling back there
    would trade a win for a loss.
    """
    return mode == "derived" and derived_core_is_empty(agent, report)


def raw_bundle(messages: list[AnyMessage], budget: int | None = None) -> list[dict[str, Any]]:
    """The tool results themselves, newest first, until the budget runs out.

    Newest first because a specialist narrows as it goes: the last call is the
    one that answered the objective, and the first is usually the orientation
    search whose result the later calls superseded. Truncation is announced in
    the bundle so a reader — model or benchmark — knows it is looking at part of
    the retrieval rather than all of it.
    """
    budget = budget if budget is not None else raw_char_budget()
    kept: list[dict[str, Any]] = []
    spent = 0
    dropped = 0
    for tool, payload in reversed(payloads(messages)):
        blob = json.dumps(payload, default=str)
        if spent + len(blob) > budget:
            dropped += 1
            continue
        spent += len(blob)
        kept.append({"tool": tool, "result": payload})
    kept.reverse()
    if dropped:
        kept.append(
            {
                "tool": "__truncated__",
                "result": f"{dropped} earlier tool results omitted to stay inside "
                f"{budget:,} characters.",
            }
        )
    return kept
