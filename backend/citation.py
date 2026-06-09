import re


def build_references(chunks: list[dict]) -> list[dict]:
    refs = []
    for idx, chunk in enumerate(chunks, start=1):
        source = chunk["source"]
        refs.append(
            {
                "id": idx,
                "chunk_id": chunk["chunk_id"],
                "doc_id": source["doc_id"],
                "filename": source["filename"],
                "chunk_index": source["chunk_index"],
                "content": source["content"],
                "expanded_context": chunk.get("expanded_context", ""),
                "score": float(chunk.get("score", 0.0)),
                "text_score": float(chunk.get("text_score", 0.0)),
                "vector_score": float(chunk.get("vector_score", 0.0)),
            }
        )
    return refs


def fix_answer_citations(answer: str, references: list[dict]) -> str:
    if not answer or not references:
        return answer

    citation_pattern = re.compile(r"\[(\d+)\]")
    parts = re.split(r"([.!?;\n]|\u3002|\uff01|\uff1f|\uff1b)", answer)
    sentences = []
    for index in range(0, len(parts), 2):
        sentence = parts[index]
        punct = parts[index + 1] if index + 1 < len(parts) else ""
        sentences.append(sentence + punct)

    fixed = []
    for sentence in sentences:
        if not citation_pattern.search(sentence):
            fixed.append(sentence)
            continue

        best_id = _best_reference_id(citation_pattern.sub("", sentence), references)
        if best_id is None:
            fixed.append(sentence)
            continue

        fixed.append(citation_pattern.sub(f"[{best_id}]", sentence))

    return "".join(fixed)


def _best_reference_id(text: str, references: list[dict]) -> int | None:
    query_shingles = _shingles(text)
    if not query_shingles:
        return None

    best_id = None
    best_score = 0.0
    for ref in references:
        corpus = "\n".join([ref.get("content", ""), ref.get("expanded_context", "")])
        ref_shingles = _shingles(corpus)
        if not ref_shingles:
            continue

        score = len(query_shingles & ref_shingles) / max(len(query_shingles), 1)
        if score > best_score:
            best_score = score
            best_id = int(ref["id"])

    return best_id if best_score >= 0.15 else None


def _shingles(text: str) -> set[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", normalized)
    if len(normalized) < 2:
        return set()
    return {normalized[i : i + 2] for i in range(len(normalized) - 1)}
