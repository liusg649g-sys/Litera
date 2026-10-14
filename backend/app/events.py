"""Internal future extraction contract; P2-A does not dispatch or enqueue it."""
from typing import TypedDict

class DocumentUploadedV1(TypedDict):
    eventId: str
    documentId: str
    ownerId: str
    fileHash: str
    storageKey: str
    occurredAt: str
