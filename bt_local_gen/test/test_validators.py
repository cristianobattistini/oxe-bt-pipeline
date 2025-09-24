from bt_local_gen.validators import split_two_code_blocks


def test_split_two_blocks():
    txt = """```xml\n<root/>\n```\n```json\n{}\n```"""
    x, j = split_two_code_blocks(txt)
    assert x.strip().startswith("<root")
    assert j.strip().startswith("{")
