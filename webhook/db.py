from google.cloud import firestore

from webhook.config import settings


async def connect():
    return firestore.Client(project=settings.GCP_PROJECT_ID)


async def get_doc(collection, document="default"):
    db = await connect()
    return db.collection(collection).document(document)


async def update_doc(collection, document, data):
    db = await connect()
    doc_ref = db.collection(collection).document(document)
    doc_ref.set(data, merge=True)


async def get_doc_data(collection, document="default") -> dict | None:
    """Read a Firestore document and return its data dict, or None."""
    doc = (await get_doc(collection, document)).get()
    return doc.to_dict() if doc.exists else None
