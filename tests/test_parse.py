import re

import pytest

from acts import parse
from acts.config import DATA_DIR
from acts.parse import Paragraph, parse_pdf, parse_text


def span(text: str, size: float = 10.0) -> dict:
    return {"text": text, "size": size}


def line(*spans: dict) -> dict:
    return {"spans": list(spans)}


def block(*lines: dict) -> dict:
    return {"lines": list(lines)}


class FakePage:
    def __init__(self, *blocks: dict):
        self.blocks = list(blocks)

    def get_text(self, kind: str) -> dict:
        assert kind == "dict"

        return {"blocks": self.blocks}


class FakeDoc(list):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def pdf(monkeypatch):
    """Make `parse_pdf` read the given fake pages instead of a real PDF."""

    def use(*pages: FakePage) -> list[Paragraph]:
        monkeypatch.setattr(parse.pymupdf, "open", lambda path: FakeDoc(pages))

        return parse_pdf("fake.pdf")

    return use


# --------------------------------------------------------------------------- lines and spans


def test_join_lines_rejoins_hyphenated_words():
    assert (
        parse._join_lines(["sztucznej inteli-", "gencji ogólnego"])
        == "sztucznej inteligencji ogólnego"
    )


def test_join_lines_keeps_hyphen_before_uppercase_or_digit():
    assert parse._join_lines(["Rzeczpospolita-", "Polska"]) == "Rzeczpospolita- Polska"
    assert parse._join_lines(["w latach 2022-", "2025"]) == "w latach 2022- 2025"


def test_span_text_converts_superscript_article_number():
    assert parse._span_text(span("[88a]", 6.5)) == "^88a"


def test_span_text_drops_footnote_markers_and_large_text():
    assert parse._span_text(span("1)", 6.5)) == ""
    assert parse._span_text(span("1), 2)", 6.5)) == ""
    assert parse._span_text(span("DZIENNIK USTAW", 46.9)) == ""


def test_span_text_keeps_units():
    assert parse._span_text(span("3", 6.5)) == "3"


def test_body_lines_skip_footnotes_and_running_header():
    lines = parse._body_lines(
        block(
            line(span("Dziennik Ustaw")),
            line(span("– 5 –")),
            line(span("Poz. 1003")),
            line(span("Art. 12. Komisja wydaje opinię.")),
            line(span("1)", 6.5), span(" Niniejszą ustawą zmienia się ustawy", 9.0)),
        )
    )

    assert lines == ["Art. 12. Komisja wydaje opinię."]


def test_body_lines_rebuild_superscript_article():
    lines = parse._body_lines(
        block(line(span("Art. 479"), span("[88a]", 6.5), span(". Sąd okręgowy")))
    )

    assert lines == ["Art. 479^88a. Sąd okręgowy"]


def test_body_lines_normalize_whitespace():
    assert parse._body_lines(block(line(span("  Art.  1.   Ustawa  ")))) == ["Art. 1. Ustawa"]


# --------------------------------------------------------------------------- parse_pdf


def test_each_block_is_one_paragraph(pdf):
    paragraphs = pdf(
        FakePage(
            block(line(span("Art. 1. Ustawa określa:"))),
            block(
                line(span("1) zasady nadzoru nad rynkiem sztucznej inteli-")), line(span("gencji;"))
            ),
        )
    )

    assert [p.text for p in paragraphs] == [
        "Art. 1. Ustawa określa:",
        "1) zasady nadzoru nad rynkiem sztucznej inteligencji;",
    ]


def test_paragraph_continued_on_next_page_is_merged(pdf):
    paragraphs = pdf(
        FakePage(block(line(span("2. Komisja może zasięgnąć opinii organiza-")))),
        FakePage(
            block(line(span("Dziennik Ustaw")), line(span("– 2 –")), line(span("Poz. 1003"))),
            block(line(span("cyjnych."))),
            block(line(span("Art. 13. Opinia jest wiążąca."))),
        ),
    )

    assert paragraphs == [
        Paragraph("2. Komisja może zasięgnąć opinii organizacyjnych.", page=1),
        Paragraph("Art. 13. Opinia jest wiążąca.", page=2),
    ]


def test_letter_point_is_not_merged(pdf):
    paragraphs = pdf(FakePage(block(line(span("1) organy:"))), block(line(span("a) Komisja,")))))

    assert [p.text for p in paragraphs] == ["1) organy:", "a) Komisja,"]


def test_title_lines_are_merged_into_one(pdf):
    paragraphs = pdf(
        FakePage(
            block(line(span("USTAWA"))),
            block(line(span("z dnia 3 lipca 2026 r."))),
            block(line(span("o systemach sztucznej inteligencji"))),
        )
    )

    assert paragraphs[0].text == "USTAWA z dnia 3 lipca 2026 r. o systemach sztucznej inteligencji"


@pytest.mark.parametrize(
    ("raw", "fixed"),
    [
        ("niepóźniej niż w terminie", "nie później niż w terminie"),
        ("niewcześniej niż po roku", "nie wcześniej niż po roku"),
        ("niewięcej niż 12 miesięcy", "nie więcej niż 12 miesięcy"),
        ("niemniej niż 6 miesięcy", "nie mniej niż 6 miesięcy"),
        ("niemniej jednak organ", "niemniej jednak organ"),
    ],
)
def test_glued_words_are_split(pdf, raw, fixed):
    assert pdf(FakePage(block(line(span(raw)))))[0].text == fixed


def test_signature_is_dropped(pdf):
    paragraphs = pdf(
        FakePage(
            block(line(span("Art. 3. Ustawa wchodzi w życie po upływie 14 dni."))),
            block(line(span("Prezydent Rzeczypospolitej Polskiej: K. Nawrocki"))),
        )
    )

    assert [p.text for p in paragraphs] == ["Art. 3. Ustawa wchodzi w życie po upływie 14 dni."]


# --------------------------------------------------------------------------- real acts

AI_ACT = DATA_DIR / "D20261003.pdf"
SHORT_ACT = DATA_DIR / "D20260179.pdf"
needs_pdfs = pytest.mark.skipif(
    not (AI_ACT.exists() and SHORT_ACT.exists()), reason="PDFs not downloaded (make fetch)"
)


@needs_pdfs
def test_real_act_parses_cleanly():
    paragraphs = parse_pdf(AI_ACT)
    text = parse_text(AI_ACT)

    assert paragraphs[0].text == "USTAWA z dnia 3 lipca 2026 r. o systemach sztucznej inteligencji"
    assert "Dziennik Ustaw" not in text
    assert "Prezydent Rzeczypospolitej" not in text
    assert "Niniejszą ustawą zmienia się" not in text  # footnote
    assert "niepóźniej" not in text

    art_12 = next(p for p in paragraphs if p.text.startswith("Art. 12."))
    assert art_12.page == 5
    assert "nie później niż w terminie 30 dni" in art_12.text


@needs_pdfs
def test_real_act_articles_are_numbered_in_order():
    numbers = [int(m[1]) for p in parse_pdf(AI_ACT) if (m := re.match(r"^Art\. (\d+)\.", p.text))]
    own = [n for n in numbers if n <= 127]  # the act has 127 articles; the rest are quoted

    assert own == list(range(1, 128))


@needs_pdfs
def test_short_act():
    assert [p.text[:7] for p in parse_pdf(SHORT_ACT)][-3:] == ["Art. 1.", "Art. 2.", "Art. 3."]
