import pytest

from acts.chunking import Chunk, act_title, chunk_act, chunk_all
from acts.config import DATA_DIR
from acts.parse import Paragraph

META = {
    "ELI": "DU/2026/1003",
    "title": "Ustawa z dnia 3 lipca 2026 r. o systemach sztucznej inteligencji",
    "displayAddress": "Dz.U. 2026 poz. 1003",
}


def paragraphs(*texts: str, page: int = 1) -> list[Paragraph]:
    return [Paragraph(text, page) for text in texts]


def chunk(*texts: str, max_chars: int = 1500) -> list[Chunk]:
    return chunk_act(paragraphs(*texts), META, max_chars=max_chars)


# --------------------------------------------------------------------------- articles


def test_one_chunk_per_article_with_its_paragraphs_and_points():
    chunks = chunk(
        "USTAWA z dnia 3 lipca 2026 r. o systemach sztucznej inteligencji",
        "Art. 1. Ustawa określa:",
        "1) organizację nadzoru;",
        "2) postępowanie w sprawie naruszenia.",
        "Art. 2. 1. Ustawy nie stosuje się do:",
        "1) obrony narodowej;",
        "2. Ustawę stosuje się odpowiednio do jednostek samorządu.",
    )

    assert [(c.art, c.ust) for c in chunks] == [("1", []), ("2", ["1", "2"])]
    assert (
        chunks[0].text
        == "Art. 1. Ustawa określa:\n1) organizację nadzoru;\n2) postępowanie w sprawie naruszenia."
    )
    assert all(c.parts == 1 for c in chunks)


def test_article_numbers_with_letters_and_superscripts():
    chunks = chunk("Art. 10a. Przepis.", "Art. 479^88a. Sąd okręgowy.", "Art. 12. Komisja.")

    assert [c.art for c in chunks] == ["10a", "479^88a", "12"]


def test_metadata_and_id():
    c = chunk("Art. 12. 1. Komisja wydaje opinię.")[0]

    assert c.id == "DU/2026/1003#art12"
    assert c.eli == "DU/2026/1003"
    assert c.act_title == "o systemach sztucznej inteligencji"
    assert c.address == "Dz.U. 2026 poz. 1003"
    assert c.metadata() == {
        "eli": "DU/2026/1003",
        "art": "12",
        "ust": ["1"],
        "part": 1,
        "parts": 1,
        "chapter": "",
        "page": 1,
        "act_title": "o systemach sztucznej inteligencji",
        "address": "Dz.U. 2026 poz. 1003",
        "id": "DU/2026/1003#art12",
    }


def test_page_is_where_the_article_starts():
    chunks = chunk_act(
        paragraphs("Art. 1. Ustawa określa:", page=3) + paragraphs("1) zasady.", page=4), META
    )

    assert chunks[0].page == 3


def test_act_title():
    assert act_title(META["title"]) == "o systemach sztucznej inteligencji"


# --------------------------------------------------------------------------- quotes


def test_quoted_articles_of_amended_act_stay_in_amending_article():
    chunks = chunk(
        "Art. 115. W ustawie – Kodeks postępowania cywilnego dodaje się dział IVfa w brzmieniu:",
        "„Dział IVfa",
        "Postępowanie w sprawach z zakresu sztucznej inteligencji",
        "Art. 479^88a. Sąd Okręgowy w Warszawie jest właściwy.",
        "2. Sąd rozpoznaje sprawę niezwłocznie.",
        "Art. 479^88b. Skarga kasacyjna przysługuje zawsze.”.",
        "Art. 116. Ustawa wchodzi w życie po 14 dniach.",
    )

    assert [c.art for c in chunks] == ["115", "116"]
    assert "Art. 479^88a." in chunks[0].text
    assert chunks[0].ust == []  # "2." inside the quote is not a paragraph of art. 115
    assert chunks[0].chapter == ""  # "Dział IVfa" inside the quote is not a heading


def test_quote_opening_paragraph_is_not_an_article():
    chunks = chunk(
        "Art. 5. W ustawie o pomocy społecznej art. 15 otrzymuje brzmienie:",
        "„Art. 15. Centrum może realizować usługi społeczne.”;",
        "Art. 6. Przepis końcowy.",
    )

    assert [c.art for c in chunks] == ["5", "6"]


def test_inline_quotes_are_balanced_within_a_paragraph():
    chunks = chunk(
        "Art. 1. Ilekroć jest mowa o „Komisji”, rozumie się przez to Komisję Rozwoju.",
        "Art. 2. Komisja jest organem nadzoru.",
    )

    assert [c.art for c in chunks] == ["1", "2"]


# --------------------------------------------------------------------------- headings


def test_chapter_heading_with_name_in_next_paragraph():
    chunks = chunk("Rozdział 1", "Przepisy ogólne", "Art. 1. Ustawa określa zasady.")

    assert chunks[0].chapter == "Rozdział 1 Przepisy ogólne"
    assert "Rozdział" not in chunks[0].text


def test_chapter_heading_with_name_in_same_paragraph():
    chunks = chunk(
        "Art. 4. Definicje.",
        "Rozdział 2 Organizacja nadzoru nad rynkiem",
        "Art. 5. Komisja jest organem nadzoru.",
    )

    assert [c.chapter for c in chunks] == ["", "Rozdział 2 Organizacja nadzoru nad rynkiem"]
    assert "Rozdział" not in chunks[0].text


def test_preamble_and_annex():
    chunks = chunk(
        "USTAWA z dnia 23 stycznia 2026 r. o ustanowieniu Dnia Inwalidy Wojennego",
        "W uznaniu zasług inwalidów wojennych stanowi się, co następuje:",
        "Art. 1. Ustanawia się dzień 12 kwietnia Dniem Inwalidy Wojennego.",
        "Załącznik do ustawy z dnia 29 maja 2026 r.",
        "WYKAZ NIERUCHOMOŚCI",
        "1) nieruchomość położona przy ul. Legionów 83 w Łodzi;",
    )

    assert [c.art for c in chunks] == ["preambuła", "1", "załącznik"]
    assert chunks[2].ust == []
    assert chunks[2].id == "DU/2026/1003#artzałącznik"


def test_numbered_annex():
    assert (
        chunk("Załącznik nr 2 do ustawy z dnia 1 lutego 2026 r.", "TABELA")[0].art == "załącznik 2"
    )


# --------------------------------------------------------------------------- splitting


def test_long_article_is_split_with_lead_repeated():
    points = [f"{i}) definicja numer {i} " + "x" * 80 + ";" for i in range(1, 21)]
    chunks = chunk("Art. 4. Użyte w ustawie określenia oznaczają:", *points, max_chars=600)

    assert len(chunks) > 1
    assert all(c.art == "4" and c.parts == len(chunks) for c in chunks)
    assert [c.part for c in chunks] == list(range(1, len(chunks) + 1))
    assert [c.id for c in chunks][:2] == ["DU/2026/1003#art4/1", "DU/2026/1003#art4/2"]
    assert all(len(c.text) <= 600 for c in chunks)
    assert all(
        c.text.startswith("Art. 4. Użyte w ustawie określenia oznaczają:\n[…]\n")
        for c in chunks[1:]
    )

    joined = "\n".join(c.text.split("[…]\n")[-1] for c in chunks[1:])
    assert all(point in chunks[0].text or point in joined for point in points)  # nothing lost


def test_split_parts_know_their_paragraphs():
    chunks = chunk(
        "Art. 8. 1. " + "a" * 300,
        "2. " + "b" * 300,
        "3. " + "c" * 300,
        max_chars=700,
    )

    assert [c.ust for c in chunks] == [["1", "2"], ["3"]]


def test_long_lead_is_shortened():
    chunks = chunk("Art. 9. " + "słowo " * 100, "1) punkt " + "y" * 600, max_chars=700)

    assert chunks[1].text.split("\n")[0].endswith(" …")
    assert len(chunks[1].text.split("\n")[0]) <= 302


def test_embedding_text_has_act_and_chapter():
    c = chunk("Rozdział 1", "Przepisy ogólne", "Art. 1. Ustawa określa zasady.")[0]

    assert c.embedding_text() == (
        "Ustawa o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003) – Rozdział 1 Przepisy ogólne\n"
        "Art. 1. Ustawa określa zasady."
    )


def test_embedding_text_without_chapter():
    c = chunk("Art. 1. Ustawa określa zasady.")[0]

    assert (
        c.embedding_text().split("\n")[0]
        == "Ustawa o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)"
    )


# --------------------------------------------------------------------------- real acts

needs_pdfs = pytest.mark.skipif(
    not (DATA_DIR / "D20261003.pdf").exists(), reason="PDFs not downloaded (make fetch)"
)


@pytest.fixture(scope="module")
def corpus() -> list[Chunk]:
    return chunk_all()


@needs_pdfs
def test_every_act_has_articles_numbered_without_gaps(corpus):
    by_act: dict[str, list[int]] = {}

    for c in corpus:
        if c.art.isdigit():
            by_act.setdefault(c.eli, []).append(int(c.art))

    assert len(by_act) == 20

    for eli, numbers in by_act.items():
        articles = list(dict.fromkeys(numbers))
        assert articles == list(range(1, max(articles) + 1)), eli


@needs_pdfs
def test_ai_act_has_127_articles_and_quoted_code_stays_inside(corpus):
    ai = [c for c in corpus if c.eli == "DU/2026/1003"]

    assert len({c.art for c in ai}) == 127
    assert any("Art. 479^88a." in c.text for c in ai if c.art == "115")


@needs_pdfs
def test_corpus_chunks_are_unique_and_bounded(corpus):
    ids = [c.id for c in corpus]

    assert len(ids) == len(set(ids))
    assert all(c.text.strip() for c in corpus)
    assert max(len(c.text) for c in corpus) < 2500  # only a single huge paragraph exceeds 1500


@needs_pdfs
def test_no_headings_inside_chunks(corpus):
    assert not any(
        line.startswith(("Rozdział ", "Oddział ")) for c in corpus for line in c.text.split("\n")
    )


@needs_pdfs
def test_golden_example_article_is_one_chunk(corpus):
    art_12 = [c for c in corpus if c.eli == "DU/2026/1003" and c.art == "12"]

    assert len(art_12) == 1
    assert art_12[0].ust == ["1", "2", "3", "4"]
    assert art_12[0].chapter.startswith("Rozdział 2 Organizacja nadzoru")
    assert "nie później niż w terminie 30 dni" in art_12[0].text
