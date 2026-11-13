from src.tools.kb_indexer import load_kb, parse_markdown


def test_parse_markdown_splits_on_h2_and_keeps_topic():
    chunks = parse_markdown("demo", "# Demo Topic\n\n## A\nfirst  text\n\n## B\nsecond text\n")

    assert [(c.topic, c.section, c.text) for c in chunks] == [
        ("Demo Topic", "A", "first text"),
        ("Demo Topic", "B", "second text"),
    ]


def test_point_ids_are_deterministic_and_content_sensitive():
    a = parse_markdown("d", "# T\n## S\nsame")[0]
    b = parse_markdown("d", "# T\n## S\nsame")[0]
    c = parse_markdown("d", "# T\n## S\nchanged")[0]

    assert a.point_id == b.point_id
    assert a.point_id != c.point_id


def test_shipped_kb_loads():
    chunks = load_kb("kb")
    docs = {c.doc for c in chunks}

    assert len(docs) >= 15
    assert len({c.point_id for c in chunks}) == len(chunks)  # no duplicate chunks
    assert all(c.text for c in chunks)
