#!/usr/bin/env python3
"""
Automatyczny harness ewaluacyjny dla Polish Acts Assistant.
Tryb 1 (domyślny): uruchamia agenta na golden.jsonl, liczy metryki automatyczne i generuje eval/report.md.
Tryb 2 (--grade): interaktywna ocena human-in-the-loop w terminalu i aktualizacja eval/report.md.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

GOLDEN_PATH = Path("eval/golden.jsonl")
RESULTS_PATH = Path("eval/results_latest.json")
REPORT_PATH = Path("eval/report.md")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:0.6b")


def get_embedding(text: str) -> list[float]:
    """Pobiera wektor embeddingu z lokalnej Ollamy bez dodatkowych zależności."""
    if not text.strip():
        return []
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings",
        data=json.dumps({"model": EMBED_MODEL, "prompt": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("embedding", [])
    except Exception:
        return []


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2) if norm1 and norm2 else 0.0


def rouge_l_f1(pred: str, ref: str) -> float:
    """Oblicza leksykalne F1 na bazie najdłuższego wspólnego podciągu (LCS)."""
    p_toks = re.findall(r"\w+", pred.lower())
    r_toks = re.findall(r"\w+", ref.lower())
    if not p_toks or not r_toks:
        return 0.0
    m, n = len(p_toks), len(r_toks)
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            if p_toks[i - 1] == r_toks[j - 1]:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = temp
    lcs = dp[n]
    prec = lcs / m
    rec = lcs / n
    return (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0


def extract_citations_from_text(text: str) -> set[tuple[str, str]]:
    """
    Wyciąga pary (poz, art) z odpowiedzi tekstowej agenta, np.:
    'Dz.U. 2026 poz. 1003, art. 12' lub 'DU/2026/1003 ... art. 12'.
    """
    found = set()
    # Szukamy wszystkich wystąpień numeru pozycji oraz artykułu w bliskim sąsiedztwie
    poz_matches = list(re.finditer(r"(?:poz\.|DU/2026/)\s*(\d+)", text, re.IGNORECASE))
    art_matches = list(re.finditer(r"art\.\s*(\d+[a-z]?)", text, re.IGNORECASE))

    if poz_matches and art_matches:
        for p in poz_matches:
            # Przypisz najbliższy artykuł po lub przed numerem pozycji
            for a in art_matches:
                if abs(a.start() - p.start()) < 120:
                    found.add((p.group(1), a.group(1)))
    return found


def compute_citation_recall(answer: str, expected_sources: list[dict], q_type: str) -> float:
    """Sprawdza odsetek oczekiwanych źródeł (poz + art) obecnych w odpowiedzi."""
    if q_type == "oos" or not expected_sources:
        refusal_patterns = [
            r"nie\s+znalazł",
            r"brak\s+informacji",
            r"nie\s+reguluj",
            r"nie\s+dotycz",
            r"spoza\s+zakresu",
            r"nie\s+ma\s+w\s+(?:dostępnych|wybranych)",
            r"odmowa",
        ]
        is_refusal = any(re.search(pat, answer, re.IGNORECASE) for pat in refusal_patterns)
        return 1.0 if is_refusal else 0.0

    expected_pairs = set()
    for src in expected_sources:
        poz = src["eli"].split("/")[-1]
        art = str(src["art"])
        expected_pairs.add((poz, art))

    found_pairs = extract_citations_from_text(answer)
    if not expected_pairs:
        return 1.0
    hits = len(expected_pairs.intersection(found_pairs))
    return hits / len(expected_pairs)


def query_agent_cli(question: str) -> str:
    """
    Wywołuje Twój istniejący pipeline CLI przez `make ask` lub `uv run`.
    Wymusza temperature=0 przez zmienną środowiskową LLM_TEMPERATURE=0.
    """
    env = os.environ.copy()
    env["LLM_TEMPERATURE"] = "0"
    env["TEMPERATURE"] = "0"

    # Dostosuj komendę poniżej, jeśli Twoje CLI przyjmuje pytanie inaczej
    cmd = ["make", "ask", f"Q={question}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
    output = proc.stdout.strip()
    if proc.returncode != 0 and not output:
        return f"[BŁĄD URUCHOMIENIA]: {proc.stderr.strip()}"
    # Odfiltrowanie ewentualnych logów make z początku
    lines = [l for l in output.splitlines() if not l.startswith("uv run ") and not l.startswith("make[")]
    return "\n".join(lines).strip()


def generate_markdown_report(records: list[dict], run_meta: dict) -> None:
    """Generuje czytelny raport eval/report.md z podsumowaniem i miejscem na ocenę ręczną."""
    n = len(records)
    avg_time = sum(r["latency_s"] for r in records) / n if n else 0
    avg_cit = sum(r["citation_recall"] for r in records) / n if n else 0
    avg_emb = sum(r["embedding_sim"] for r in records) / n if n else 0
    avg_rouge = sum(r["rouge_l"] for r in records) / n if n else 0

    graded = [r for r in records if r.get("human_score") is not None]
    human_acc = (sum(r["human_score"] for r in graded) / len(graded) * 100) if graded else None

    md = []
    md.append("# Raport Ewaluacji RAG — Polish Acts Assistant\n")
    md.append("## 1. Konfiguracja Eksperymentu")
    md.append(f"- **Data uruchomienia:** `{run_meta['timestamp']}`")
    md.append(f"- **Liczba pytań (`golden.jsonl`):** `{n}`")
    md.append(f"- **Parametry generacji:** `temperature = 0` (wymuszone dla powtarzalności)")
    md.append(f"- **Model embeddingów do metryki semantycznej:** `{EMBED_MODEL}`\n")

    md.append("## 2. Średnie wyniki zbiorcze")
    md.append("| Metryka | Wynik | Opis |")
    md.append("| :--- | :---: | :--- |")
    if human_acc is not None:
        md.append(f"| **Human Accuracy (Ocena ręczna)** | **{human_acc:.1f}%** ({sum(r['human_score'] for r in graded)}/{len(graded)}) | Ostateczna poprawność merytoryczna / poprawna odmowa |")
    else:
        md.append("| **Human Accuracy (Ocena ręczna)** | *Oczekuje na ocenę* | Uruchom `make eval-grade` lub wpisz `1` / `0` w tabeli poniżej |")
    md.append(f"| **Citation / Refusal Recall** | **{avg_cit * 100:.1f}%** | Trafność cytowanych ustaw i artykułów (lub poprawna odmowa dla `oos`) |")
    md.append(f"| **Embedding Cosine Similarity** | **{avg_emb:.3f}** | Podobieństwo semantyczne odpowiedzi do `expected_answer` |")
    md.append(f"| **ROUGE-L (F1)** | **{avg_rouge:.3f}** | Leksykalne pokrywanie się słów z odpowiedzią wzorcową |")
    md.append(f"| **Średni czas odpowiedzi** | **{avg_time:.2f} s** | Średni czas generacji odpowiedzi na pytanie |\n")

    # Podsumowanie per typ pytania
    md.append("## 3. Wyniki w podziale na trudność (`type`)")
    md.append("| Typ pytania | Liczba | Cit./Refusal Recall | Emb. Sim | ROUGE-L | Czas (s) | Human Accuracy |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    for qtype in ["easy", "multi", "oos"]:
        sub = [r for r in records if r["type"] == qtype]
        if not sub:
            continue
        sub_cit = sum(r["citation_recall"] for r in sub) / len(sub) * 100
        sub_emb = sum(r["embedding_sim"] for r in sub) / len(sub)
        sub_rouge = sum(r["rouge_l"] for r in sub) / len(sub)
        sub_time = sum(r["latency_s"] for r in sub) / len(sub)
        sub_graded = [r for r in sub if r.get("human_score") is not None]
        h_str = f"{sum(r['human_score'] for r in sub_graded)}/{len(sub_graded)}" if sub_graded else "—"
        md.append(f"| `{qtype}` | {len(sub)} | {sub_cit:.1f}% | {sub_emb:.3f} | {sub_rouge:.3f} | {sub_time:.2f}s | {h_str} |")
    md.append("")

    md.append("## 4. Tabela przeglądowa wyników i miejsce na ocenę ręczną")
    md.append("> **Instrukcja oceny ręcznej:** Uruchom `make eval-grade` w terminalu, aby ocenić każde pytanie interaktywnie (`1` = poprawna / poprawna odmowa, `0` = błędna / halucynacja), albo uzupełnij kolumnę **Ocena Human** ręcznie.\n")
    md.append("| ID | Typ | Cit. Recall | Emb. Sim | ROUGE-L | Czas | Ocena Human (0/1) | Notatka |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for r in records:
        h_val = f"**{r['human_score']}**" if r.get("human_score") is not None else "`[ ]`"
        note = r.get("human_note", "")
        md.append(f"| `{r['id']}` | `{r['type']}` | {r['citation_recall']:.2f} | {r['embedding_sim']:.3f} | {r['rouge_l']:.3f} | {r['latency_s']:.1f}s | {h_val} | {note} |")
    md.append("\n---\n")

    md.append("## 5. Szczegółowe porównanie odpowiedzi (Golden vs Agent)\n")
    for r in records:
        src_str = ", ".join(f"{s['eli']} art. {s['art']}" + (f" ust. {s['ust']}" if s.get("ust") else "") for s in r["sources"]) or "BRAK (OOS)"
        md.append(f"### `{r['id']}` (`{r['type']}`) — Cit. Recall: `{r['citation_recall']:.2f}` | Emb. Sim: `{r['embedding_sim']:.3f}` | Czas: `{r['latency_s']:.1f}s`")
        md.append(f"- **Pytanie:** {r['question']}")
        md.append(f"- **Oczekiwane źródła:** `{src_str}`")
        md.append(f"- **Oczekiwana odpowiedź (Golden):** {r['expected_answer']}")
        md.append(f"- **Odpowiedź agenta:**\n> {r['actual_answer'].replace(chr(10), chr(10) + '> ')}\n")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"\n[OK] Wygenerowano raport: {REPORT_PATH}")


def run_evaluation():
    if not GOLDEN_PATH.exists():
        print(f"Błąd: Brak pliku {GOLDEN_PATH}")
        sys.exit(1)

    items = [json.loads(line) for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Rozpoczynam ewaluację {len(items)} pytań z {GOLDEN_PATH}...\n")

    results = []
    for idx, item in enumerate(items, 1):
        qid = item["id"]
        print(f"[{idx}/{len(items)}] {qid} ({item['type']}): {item['question'][:65]}...")

        t0 = time.perf_counter()
        actual = query_agent_cli(item["question"])
        latency = time.perf_counter() - t0

        cit_recall = compute_citation_recall(actual, item.get("sources", []), item["type"])
        rouge = rouge_l_f1(actual, item["expected_answer"])

        emb_pred = get_embedding(actual)
        emb_ref = get_embedding(item["expected_answer"])
        emb_sim = cosine_similarity(emb_pred, emb_ref)

        print(f"       -> Czas: {latency:.1f}s | Cit.Recall: {cit_recall:.2f} | Emb.Sim: {emb_sim:.3f} | ROUGE-L: {rouge:.3f}")

        results.append({
            "id": qid,
            "type": item["type"],
            "question": item["question"],
            "expected_answer": item["expected_answer"],
            "sources": item.get("sources", []),
            "actual_answer": actual,
            "latency_s": round(latency, 2),
            "citation_recall": round(cit_recall, 4),
            "embedding_sim": round(emb_sim, 4),
            "rouge_l": round(rouge, 4),
            "human_score": None,
            "human_note": "",
        })

    payload = {
        "meta": {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "records": results,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_markdown_report(results, payload["meta"])


def run_human_grading():
    if not RESULTS_PATH.exists():
        print(f"Brak pliku {RESULTS_PATH}. Uruchom najpierw: make eval")
        sys.exit(1)

    payload = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    records = payload["records"]

    print("=== TRYB OCENY RĘCZNEJ (HUMAN-IN-THE-LOOP) ===")
    print("Wpisz: 1 (poprawna / poprawna odmowa), 0 (błędna / halucynacja), Enter (pomiń)\n")

    for idx, r in enumerate(records, 1):
        print("=" * 70)
        print(f"[{idx}/{len(records)}] ID: {r['id']} | Typ: {r['type']} | Auto Cit.Recall: {r['citation_recall']}")
        print(f"PYTANIE:   {r['question']}")
        print(f"ŹRÓDŁA:    {r['sources']}")
        print(f"WZORZEC:   {r['expected_answer']}")
        print("-" * 70)
        print(f"AGENT:\n{r['actual_answer']}")
        print("-" * 70)

        while True:
            val = input("Twoja ocena [1 / 0 / Enter=pomiń]: ").strip()
            if val in ("1", "0", ""):
                break
            print("Nieprawidłowy znak. Wpisz 1, 0 lub Enter.")

        if val in ("1", "0"):
            r["human_score"] = int(val)
            note = input("Opcjonalna krótka notatka (Enter=brak): ").strip()
            r["human_note"] = note

    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_markdown_report(records, payload["meta"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--grade", action="store_true", help="Uruchom interaktywną ocenę ręczną wyników")
    args = parser.parse_args()

    if args.grade:
        run_human_grading()
    else:
        run_evaluation()