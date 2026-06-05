from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL

app = FastAPI()

print("Loading embedding model...")
model = SentenceTransformer(EMBEDDING_MODEL).half()
embedding_dim = (
    model.get_sentence_embedding_dimension()
    )
model.encode("warmup")
print("Model loaded.")

class EmbeddingRequest(BaseModel):
    text: str

@app.post("/embed")
async def embed(req: EmbeddingRequest):
    embedding = model.encode(req.text).tolist()

    return {
        "embedding": embedding,
        "embedding_dim":embedding_dim
    }