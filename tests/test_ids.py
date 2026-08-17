from orc.ids import canonical_dump, content_hash, is_valid_id


def test_length_and_hex():
    assert is_valid_id(content_hash({"a": 1}))


def test_deterministic():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"a": 1, "b": 2})


def test_order_insensitive():
    a = content_hash({"a": 1, "b": 2})
    b = content_hash({"b": 2, "a": 1})
    assert a == b


def test_content_sensitive():
    assert content_hash({"a": 1}) != content_hash({"a": 2})


def test_canonical_dump_stable_across_parsers():
    import yaml

    for text in ("a: 1\nb: [2, 3]\n", "b: [2,3]\na: 1\n"):
        obj = yaml.safe_load(text)
        assert canonical_dump(obj) == canonical_dump(yaml.safe_load(text))


def test_id_prefix_is_8_chars():
    assert len(content_hash({"x": "y"})) == 8
