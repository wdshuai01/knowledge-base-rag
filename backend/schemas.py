from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class DeleteDocumentRequest(BaseModel):
    doc_id: str = Field(..., min_length=1)

