from legal.citation_normalizer import extract_citations

def test_extract_simple():
    text = "См. КоАП РФ, ст. 20.1 ч.1 п.2"
    cites = extract_citations(text)
    assert any(c["code"] == "КоАП РФ" and c["article"]=="20.1" for c in cites)
