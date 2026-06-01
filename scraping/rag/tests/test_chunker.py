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


def test_overlap_carries_the_previous_paragraph_into_the_next_chunk():
    text = "\n\n".join(["aaaa", "bbbb", "cccc"])  # three 4-char paragraphs
    chunks = chunker.chunk_article(text, max_chars=6, overlap_chars=4)

    # Each new chunk re-includes the trailing paragraph of the previous one.
    assert chunks == ["aaaa", "aaaa\n\nbbbb", "bbbb\n\ncccc"]
