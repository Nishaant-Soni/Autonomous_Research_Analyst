"""The `Evidence` contract shared by both retrievers and the agents (PRD §5.3).

Keeping evidence structured from the moment it's gathered is what makes deterministic
citation validation possible later. Web-derived evidence carries `source_url`;
corpus-derived evidence carries `source_chunk_id`. This dual path lets the citation
validator verify both source types uniformly (PRD §8).
"""

from typing import Literal

from pydantic import BaseModel, model_validator


class Evidence(BaseModel):
    content: str
    retriever: Literal["web", "rag"]
    claim: str = ""  # the asserted claim; filled by the Researcher, empty at retrieval
    source_url: str | None = None
    source_chunk_id: int | None = None

    @model_validator(mode="after")
    def _require_matching_source(self) -> "Evidence":
        if self.retriever == "web" and not self.source_url:
            raise ValueError("web evidence requires source_url")
        if self.retriever == "rag" and self.source_chunk_id is None:
            raise ValueError("rag evidence requires source_chunk_id")
        return self
