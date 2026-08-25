"""Confirm a mutated Robot run failed on the assertion the mutation broke.

A mutation check re-runs a suite with one value deliberately broken and expects
a failure. A non-zero robot exit alone does not prove anything: the run could
have died in SETUP (an agent-family suite's documented `project create` against
a project that already exists), or on a build, or on a missing key. Every one of
those is a failure the mutation did not cause, and treating it as proof is how a
vacuous assertion gets certified as verified.

So this reads the mutated run's output.xml and requires that a keyword with the
given name is present with status FAIL, that its ENCLOSING TEST also failed --
and, when a message substring is given, that the failure message names it (the
mutation sentinel). A keyword that never ran comes back NOT RUN, which fails
this check with that fact stated.

The enclosing-test requirement exists because a keyword can FAIL and still be
swallowed: `resources/tests/keywords.robot` has tests that deliberately break a
keyword inside `Run Keyword And Return Status` and then assert the returned
status is False, so the test itself PASSES with a FAILing `<kw>` inside it. A
checker that looks only at the keyword's own status calls that "caught" -- it
is not, because nothing about a swallowed failure shows the assertion can fail
a real run.

Usage:
    python ci/check_mutation.py <output.xml> <keyword-name> [message-substring]

Exit 0 when the named keyword failed as required, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree


def keyword_statuses(output_xml: Path, keyword: str) -> list[tuple[str, str, str]]:
    """(status, message, enclosing_status) for every `<kw>` in the run with this name.

    Robot writes one `<kw name="...">` element per invocation, at any nesting
    depth, each with a `<status status="PASS|FAIL|NOT RUN|SKIP">` child whose
    text is the failure message when there is one. Matching on the name is what
    ties the check to the mutated assertion rather than to "something failed".

    `enclosing_status` is the status of the nearest ancestor `<test>` (or, for a
    keyword outside any test -- suite setup/teardown -- the nearest `<suite>`).
    That is what tells a FAIL that made it out of the keyword apart from a FAIL
    that got caught by something like `Run Keyword And Return Status` and turned
    into a boolean: in the latter case the keyword is FAIL but the enclosing
    test still PASSes.
    """
    tree = ElementTree.parse(output_xml)
    root = tree.getroot()
    parent_of = {child: parent for parent in root.iter() for child in parent}

    def enclosing_status(element: ElementTree.Element) -> str:
        node = parent_of.get(element)
        while node is not None:
            if node.tag in ("test", "suite"):
                status = node.find("status")
                return status.get("status", "") if status is not None else ""
            node = parent_of.get(node)
        return ""

    found = []
    for element in root.iter("kw"):
        if element.get("name") != keyword:
            continue
        status = element.find("status")
        if status is None:
            continue
        found.append(
            (status.get("status", ""), (status.text or "").strip(), enclosing_status(element))
        )
    return found


def check(output_xml: Path, keyword: str, message_contains: str = "") -> list[str]:
    """Problems with the mutated run. Empty means the mutation was caught."""
    if not output_xml.is_file():
        return [
            f"{output_xml} does not exist. The mutated run produced no output.xml, "
            "which usually means robot itself failed to start (a bad suite path, or "
            "a variable file it could not read)."
        ]

    try:
        statuses = keyword_statuses(output_xml, keyword)
    except ElementTree.ParseError as error:
        return [f"{output_xml} is not parseable as Robot output: {error}"]

    if not statuses:
        return [
            f"no keyword named {keyword!r} appears in {output_xml}. Either the "
            "mutated run never reached it, or the name is spelled differently in "
            "the suite -- check the keyword name in the suite, then read log.html."
        ]

    genuine_failures = [
        (status, message)
        for status, message, enclosing in statuses
        if status == "FAIL" and enclosing == "FAIL"
    ]
    swallowed_failures = [
        (status, message)
        for status, message, enclosing in statuses
        if status == "FAIL" and enclosing != "FAIL"
    ]

    if not genuine_failures:
        if swallowed_failures:
            messages = " | ".join(m for _, m in swallowed_failures) or "(no message)"
            return [
                f"{keyword!r} FAILED {len(swallowed_failures)} time(s) in {output_xml}, "
                "but every one of those failures was inside a test that ultimately "
                "PASSED -- something upstream (a `Run Keyword And Return Status` or "
                "similar) caught the failure and swallowed it. A FAIL that never makes "
                "the test itself fail is not evidence the assertion can fail a real "
                "run; it proves the opposite, that whatever calls this keyword has a "
                "safety net around it.\n"
                f"  messages: {messages}"
            ]
        seen = ", ".join(sorted({status for status, _, _ in statuses}))
        return [
            f"{keyword!r} ran {len(statuses)} time(s) in {output_xml} but never "
            f"failed (statuses seen: {seen}). The mutated run failed for some other "
            "reason, so it proves nothing about this assertion."
        ]

    if message_contains and not any(message_contains in m for _, m in genuine_failures):
        messages = " | ".join(m for _, m in genuine_failures) or "(no message)"
        return [
            f"{keyword!r} failed, but no failure message mentions "
            f"{message_contains!r}, so this is probably not the mutation's doing.\n"
            f"  messages: {messages}"
        ]

    return []


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    output_xml = Path(sys.argv[1])
    keyword = sys.argv[2]
    # An empty third argument means "no message check"; the caller passes it
    # unconditionally so no shell array juggling is needed.
    message_contains = sys.argv[3] if len(sys.argv) > 3 else ""

    problems = check(output_xml, keyword, message_contains)
    for problem in problems:
        print(f"::error::{problem}", file=sys.stderr)
    if problems:
        return 1

    where = f" naming {message_contains!r}" if message_contains else ""
    print(f"Mutation caught: {keyword!r} FAILED{where} in {output_xml}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
