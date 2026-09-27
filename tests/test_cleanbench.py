from scribekey_models.cleanbench import (
    MAX_CANDIDATE_BYTES,
    Candidate,
    load_candidates,
    load_corpus,
    output_budget,
    render_report,
    retains_protected_tokens,
    score_case,
)


def test_frozen_corpus_matches_the_app_identity_and_shape() -> None:
    cases = load_corpus()

    assert len(cases) == 240
    assert len({case["id"] for case in cases}) == 240
    assert all({"input", "expected", "protectedTokens", "category"} <= case.keys() for case in cases)


def test_every_candidate_is_pinned_and_builds_a_prompt() -> None:
    candidates = load_candidates()

    assert len({c.id for c in candidates}) == len(candidates)
    for candidate in candidates:
        assert 0 < candidate.size_bytes <= MAX_CANDIDATE_BYTES, candidate.id
        if candidate.is_baseline:
            assert len(candidate.archive_sha256) == 64
            assert candidate.archive_url.startswith("https://")
        else:
            assert len(candidate.revision) == 40
            assert candidate.file.endswith(".gguf")
            assert "hello there" in candidate.prompt_for("hello there")


def test_quill_prompt_matches_the_app_template() -> None:
    quill = next(c for c in load_candidates() if c.id == "quill")

    assert quill.prompt_for("um hi") == (
        "<|im_start|>system\nYou clean up dictated text.<|im_end|>\n"
        "<|im_start|>user\num hi<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n"
    )


def test_protected_tokens_need_word_boundaries_order_and_multiplicity() -> None:
    assert retains_protected_tokens("Pay $40 on 3 May.", ["$40", "3 May"])
    assert not retains_protected_tokens("Pay $400 on 3 May.", ["$40", "3 May"])
    assert not retains_protected_tokens("On 3 May pay $40.", ["$40", "3 May"])
    assert not retains_protected_tokens("Call Sam, then Sam.", ["Sam"])
    assert retains_protected_tokens("anything", [])


def test_score_case_flags_a_modified_control_and_added_content() -> None:
    control = {
        "category": "already_clean_controls",
        "input": "The gate is locked.",
        "expected": "The gate is locked.",
        "protectedTokens": [],
    }

    kept = score_case(control, "The gate is locked.")
    answered = score_case(control, "The gate is locked. Would you like me to unlock it for you?")

    assert kept["exact"] and kept["controlKept"] and not kept["addedContent"]
    assert not answered["controlKept"] and answered["addedContent"]
    assert answered["similarity"] < kept["similarity"]


def test_output_budget_is_shared_and_bounded() -> None:
    assert output_budget(1) == 64
    assert output_budget(100) == 182
    assert output_budget(5000) == 1024


def test_report_advances_only_models_that_keep_protected_spans() -> None:
    def candidate(model_id: str, runtime: str = "llama.cpp") -> Candidate:
        return Candidate(model_id, "o/r", "a" * 40, "m.gguf", 1, "MIT", "chatml", "", runtime)

    def row(similarity: float, retained: bool) -> dict:
        return {
            "category": "dates_numbers_money",
            "exact": False,
            "similarity": similarity,
            "protectedTokenCount": 1,
            "protectedRetained": retained,
            "controlKept": None,
            "addedContent": False,
            "truncated": False,
            "empty": False,
            "latencyMs": 100,
            "generatedTokens": 10,
        }

    report = render_report(
        [candidate("careful"), candidate("sloppy"), candidate("punct", "sherpa-online-punct")],
        {"careful": [row(0.8, True)], "sloppy": [row(0.95, False)], "punct": [row(0.99, True)]},
    )

    assert "Advance to device qualification: careful " in report
    assert "| punct *baseline* |" in report
