import chunker


def test_make_chunk_id_is_stable_and_position_sensitive():
    first = chunker.make_chunk_id("The Legend of Zelda", 0)
    again = chunker.make_chunk_id("The Legend of Zelda", 0)
    next_index = chunker.make_chunk_id("The Legend of Zelda", 1)

    assert first == again  # deterministic for the same input
    assert first != next_index  # position changes the id
    assert len(first) == 32  # md5 hex digest


def test_split_long_paragraph_never_exceeds_max_chars():
    paragraph = "This is a sentence. " * 100  # ~2000 chars
    pieces = chunker.split_long_paragraph(paragraph, max_chars=100)

    assert pieces
    assert all(len(piece) <= 100 for piece in pieces)


def test_split_long_paragraph_hard_splits_a_single_giant_sentence():
    giant = "x" * 250  # no sentence boundaries
    pieces = chunker.split_long_paragraph(giant, max_chars=100)

    assert all(len(piece) <= 100 for piece in pieces)
    assert "".join(pieces) == giant


def test_short_article_becomes_a_single_chunk():
    text = "\n\n".join(["First paragraph.", "Second paragraph.", "Third."])
    chunks = chunker.chunk_article(text, max_chars=1000, overlap_chars=0)

    assert len(chunks) == 1
    assert "First paragraph." in chunks[0]
    assert "Third." in chunks[0]


def test_article_is_split_into_multiple_chunks_when_long():
    paragraph = "y" * 400
    text = "\n\n".join([paragraph, paragraph, paragraph])
    chunks = chunker.chunk_article(text, max_chars=500, overlap_chars=50)

    assert len(chunks) >= 2


def test_overlap_carries_trailing_text_into_the_next_chunk():
    # Distinct per-paragraph vocab so overlap is detectable: the first word of a
    # later chunk reappearing in the earlier chunk means the tail was carried over.
    # Sizes chosen so the overlap actually fits under the cap (two paragraphs do not).
    p1 = ("alpha " * 7).strip()  # ~41 chars
    p2 = ("bravo " * 7).strip()
    p3 = ("charlie " * 5).strip()
    chunks = chunker.chunk_article("\n\n".join([p1, p2, p3]), max_chars=70, overlap_chars=20)

    assert len(chunks) >= 2
    assert all(len(c) <= 70 for c in chunks)  # cap honored despite overlap
    for earlier, later in zip(chunks, chunks[1:], strict=False):
        assert later.split()[0] in earlier


def test_chunks_never_exceed_max_chars_even_with_overlap():
    # A paragraph near the cap, repeated, stresses the overlap+append path that
    # the old algorithm overshot (it produced ~2x-oversize chunks).
    para = ("word " * 50).strip()  # ~249 chars
    text = "\n\n".join([para] * 6)
    for max_chars, overlap in [(300, 80), (256, 60), (500, 150)]:
        chunks = chunker.chunk_article(text, max_chars=max_chars, overlap_chars=overlap)
        assert chunks
        assert all(len(c) <= max_chars for c in chunks)
