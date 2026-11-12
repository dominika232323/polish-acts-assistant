from acts.fetch import ACTS, is_standalone


def act(title: str, type_: str = "Ustawa") -> dict:
    return {"title": title, "type": type_}


def test_is_standalone_accepts_new_act():
    assert is_standalone(act("Ustawa z dnia 3 lipca 2026 r. o systemach sztucznej inteligencji"))


def test_is_standalone_rejects_amendments_ratifications_and_budget():
    assert not is_standalone(act("Ustawa z dnia 8 października 2026 r. o zmianie ustawy o VAT"))
    assert not is_standalone(act("Ustawa z dnia 18 września 2026 r. o ratyfikacji Traktatu"))
    assert not is_standalone(act("Ustawa budżetowa na rok 2026"))
    assert not is_standalone(act("Rozporządzenie Ministra Zdrowia", type_="Rozporządzenie"))


def test_corpus_has_20_acts():
    assert len(ACTS) == 20
