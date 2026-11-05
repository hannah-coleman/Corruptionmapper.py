import network_report as nr


def test_canonical_names_fold_ocr_variants():
    canon = nr._canon_factory(["Branch"] * 6 + ["Bxanch"])
    assert canon("Bxanch") == "Branch"
    assert canon("B ranch") == "Branch"


def test_titles_are_stripped_from_names():
    assert nr._clean("Ms. Hailey Petit") == "Hailey Petit"


def test_motion_pattern_finds_mover_and_seconder():
    text = "Motion to table made by Council Member Adams; seconded by Council Member Branch. All in favor."
    match = nr._MOTION.search(text)
    assert (match.group(1), match.group(2)) == ("Adams", "Branch")


def test_report_states_it_is_not_an_accusation():
    report = nr.render_report([], [])
    assert "evidence of wrongdoing" in report
    assert "What is missing" in report


def test_report_suggests_questions_only_from_open_discrepancies():
    questions = nr._suggested_questions([
        {
            "status": "open",
            "message": "Agenda item is not mentioned in the minutes.",
            "innocent_explanations": ["The item may have been tabled."],
            "next_action": "Ask the clerk what action was taken.",
        },
        {"status": "resolved", "message": "Resolved discrepancy."},
    ])

    assert questions == [{
        "statement": "What explains this record discrepancy: Agenda item is not mentioned in the minutes?",
        "alternatives": ["The item may have been tabled."],
        "next_test": "Ask the clerk what action was taken.",
        "verification": "UNVERIFIED (not yet compared with the original)",
    }]


def test_report_includes_auto_suggested_discrepancy_questions():
    report = nr.render_report([], [{
        "status": "open",
        "kind": "agenda-only",
        "message": "An agenda item is missing from the minutes.",
        "innocent_explanations": ["The item may have been tabled."],
        "next_action": "Ask the clerk what action was taken.",
    }])

    assert "Suggested questions from open discrepancies" in report
    assert "What explains this record discrepancy: An agenda item is missing from the minutes?" in report
    assert "Questions and narratives in the research ledger" in report


def test_pattern_questions_come_from_records_and_never_assume_wrongdoing():
    flags = [
        {"status": "open", "kind": "agenda-only", "message": f"The agenda lists a property at 703 East Lake Street that the minutes never mention", "link": {"detail": d}}
        for d in ("2026-06-08 (#185)", "2026-07-13 (#187)")
    ] + [{"status": "open", "kind": "vote-tally", "message": "tally mismatch"}]
    net = {
        "edges": [{"source": "Hailey Petit", "target": "Penny Mac", "relation": "stated they represent", "evidence": [{"meeting": "2026-02-23 (#178)"}]},
                  {"source": "Baine", "target": "Council vote", "relation": "voted 'no'", "evidence": [{"meeting": "2026-02-23 (#178)"}]}],
        "awards": [{"award": "A1", "recipient": "Acme", "amount": "1,000", "agency": "HUD"}],
    }
    text = " ".join(q["statement"] for q in nr._pattern_questions(net, flags))

    assert "703 East Lake Street" in text and "2026-06-08" in text
    assert "Hailey Petit" in text and "Baine" in text and "A1" in text
    assert "laundering" not in text and "tunnel" not in text.lower()
    assert nr._pattern_questions({"edges": [], "awards": []}, []) == []


def test_state_agencies_are_excluded_and_business_owners_generate_questions():
    net = {"edges": [], "awards": [
        {"award": "S1", "recipient": "ARKANSAS DEPARTMENT OF TRANSPORTATION", "amount": "9,000", "agency": "DOT"},
        {"award": "L1", "recipient": "CITY OF PARAGOULD", "amount": "5,000", "agency": "DRA"}],
        "owners": {"J & M Foster Properties LLC": {"703 east lake street": {"2026-06-08"}}}}
    text = " ".join(q["statement"] for q in nr._pattern_questions(net, []))
    assert "S1" not in text and "L1" in text
    assert "J & M Foster Properties LLC" in text and "703 East Lake Street" in text
    match = nr._OWNER.search("The property is located at 600 West Park Street and is owned by Illuminated Enterprises LLC. 4. A Resolution")
    assert match.group(2) == "Illuminated Enterprises LLC"
