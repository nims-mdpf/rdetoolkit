"""The v2 documentation set is complete, bilingual and reachable (#454).

EP table
========

====================  ==========================  ====================================  =====================
Item                  Partition                   Expected                              Test ID
====================  ==========================  ====================================  =====================
narrative pages       getting started / concepts  ja page and ``.en.md`` twin exist     TC-DOC-STR-EP-001
                      / guides / reference / ADR
navigation            ja and en ``nav``           every v2 page listed in both          TC-DOC-STR-EP-002
ADR index             every ``docs/adr/0*.md``    linked from both index pages          TC-DOC-STR-EP-003
API reference         every ``rdetoolkit/v2`` page  has at least one mkdocstrings block  TC-DOC-STR-EP-004
====================  ==========================  ====================================  =====================

BV table
========

====================  ==========================  ====================================  =====================
Item                  Boundary                    Expected                              Test ID
====================  ==========================  ====================================  =====================
ADR prose             ``@`` + letter token         none (GitHub mention hazard)          TC-DOC-STR-BV-001
page added later      present on disk, not in nav  EP-002 fails                          TC-DOC-STR-BV-002
====================  ==========================  ====================================  =====================
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.v2.docs.doc_examples import DOCS_DIR, mention_hazards

MKDOCS_YML = DOCS_DIR.parent / "mkdocs.yml"
NARRATIVE = (
    "getting-started",
    "concepts/node",
    "concepts/flow",
    "concepts/runner",
    "guides/testing",
    "guides/plugins",
    "reference/cli",
    "adr/index",
    *(path.relative_to(DOCS_DIR).with_suffix("").as_posix() for path in sorted((DOCS_DIR / "adr").glob("0*.md")) if not path.name.endswith(".en.md")),
)
API_PAGES = tuple(path.relative_to(DOCS_DIR).as_posix() for path in sorted((DOCS_DIR / "rdetoolkit" / "v2").glob("*.md")))


class _IgnoreTagsLoader(yaml.SafeLoader):
    """Safe loader that maps mkdocs' ``!!python/name:`` tags to ``None``."""


_IgnoreTagsLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda loader, suffix, node: None)


def _nav_files(locale: str) -> set[str]:
    config: dict[str, Any] = yaml.load(MKDOCS_YML.read_text(encoding="utf-8"), Loader=_IgnoreTagsLoader)  # noqa: S506
    i18n = next(plugin["i18n"] for plugin in config["plugins"] if isinstance(plugin, dict) and "i18n" in plugin)
    (language,) = (entry for entry in i18n["languages"] if entry["locale"] == locale)

    def walk(items: list[Any]) -> Iterator[str]:
        for item in items:
            for value in item.values():
                if isinstance(value, list):
                    yield from walk(value)
                else:
                    yield value

    return set(walk(language["nav"]))


@pytest.mark.parametrize("page", NARRATIVE)
def test_narrative_pages_have_both_languages__tc_doc_str_ep_001(page: str) -> None:
    """TC-DOC-STR-EP-001: every v2 narrative page exists in Japanese and English."""
    assert (DOCS_DIR / f"{page}.md").is_file()
    assert (DOCS_DIR / f"{page}.en.md").is_file()


@pytest.mark.parametrize("locale", ["ja", "en"])
def test_every_v2_page_is_in_the_nav__tc_doc_str_ep_002(locale: str) -> None:
    """TC-DOC-STR-EP-002 / BV-002: each language's nav reaches every v2 page."""
    nav = _nav_files(locale)
    expected = {f"{page}.md" for page in NARRATIVE} | set(API_PAGES)
    assert expected - nav == set()


@pytest.mark.parametrize("suffix", ["", ".en"], ids=["ja", "en"])
def test_adr_index_links_every_adr__tc_doc_str_ep_003(suffix: str) -> None:
    """TC-DOC-STR-EP-003: the ADR index links every published ADR."""
    index = (DOCS_DIR / "adr" / f"index{suffix}.md").read_text(encoding="utf-8")
    linked = set(re.findall(r"\]\((0\d{3}-[\w-]+\.md)\)", index))
    published = {path.name for path in (DOCS_DIR / "adr").glob("0*.md") if not path.name.endswith(".en.md")}
    assert linked == published


@pytest.mark.parametrize("page", [page for page in API_PAGES if not page.endswith("/index.md")])
def test_api_pages_render_docstrings__tc_doc_str_ep_004(page: str) -> None:
    """TC-DOC-STR-EP-004: each v2 API page pulls at least one object through mkdocstrings."""
    assert re.search(r"^::: src\.rdetoolkit\.", (DOCS_DIR / page).read_text(encoding="utf-8"), re.MULTILINE)


@pytest.mark.parametrize(
    "doc",
    sorted((DOCS_DIR / "adr").glob("*.md")),
    ids=lambda path: path.name,
)
def test_adr_prose_has_no_mention_tokens__tc_doc_str_bv_001(doc: Path) -> None:
    """TC-DOC-STR-BV-001: ADR prose renders no GitHub mention."""
    assert mention_hazards(doc) == []
