from backend.es_store import ESStore


class DocumentService:
    def __init__(self, store: ESStore | None = None) -> None:
        self.store = store or ESStore()

    def list_documents(self) -> list[dict]:
        return self.store.list_documents()

    def delete_document(self, doc_id: str) -> int:
        return self.store.delete_document(doc_id)

    def deduplicate_documents(self) -> dict:
        docs = self.store.list_documents()
        groups: dict[str, list[dict]] = {}
        for doc in docs:
            key = doc.get("file_hash") or doc.get("filename") or doc["doc_id"]
            groups.setdefault(key, []).append(doc)#key:doc   如果一个key后面有多个doc  说明有重复

        removed = []
        for group_docs in groups.values():
            if len(group_docs) <= 1:
                continue
            keep = sorted(group_docs, key=lambda item: item["doc_id"])[0]#留下第一条
            for doc in group_docs:
                if doc["doc_id"] == keep["doc_id"]:
                    continue
                deleted_chunks = self.store.delete_document(doc["doc_id"])
                removed.append(
                    {
                        "doc_id": doc["doc_id"],
                        "filename": doc.get("filename", ""),
                        "deleted_chunks": deleted_chunks,
                        "kept_doc_id": keep["doc_id"],
                    }
                )

        return {"removed": removed, "removed_count": len(removed)}
