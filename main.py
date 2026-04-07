from pyexpat.errors import messages

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, field_validator
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import chromadb
from langchain_ollama import OllamaEmbeddings

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

OLLAMA_HOST = "http://192.168.1.94:11434"
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://192.168.1.94:11434"
)

client = chromadb.PersistentClient(path="./vectordb")
collection = client.get_or_create_collection(name="technova_docs")
print("Connected to ChromaDB ✓")

class ChatRequest(BaseModel):
    messages: list
    @field_validator("messages")
    def validate_messages(messages):
        # Check 1 - messages list must not be empty
        if len(messages) == 0:
            raise ValueError("Messages cannot be empty")
        
        # Check 2 - last message must not exceed 1000 characters
        print("messages received:", messages)
        print("last message type:", type(messages[-1]))
        last_message = messages[-1]["content"]
        if len(last_message) > 1000:
            raise ValueError("Message too long, maximum 1000 characters")
        
        return messages

@app.get("/")
def home():
    with open("static/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, media_type="text/html")

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest):
    # Step 1 - search ChromaDB for relevant chunks
    user_message = body.messages[-1]["content"]
    query_embedding = embeddings.embed_query(user_message)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2
    )
    # Step 2 - build context from retrieved chunks
    context = "\n\n".join(results["documents"][0])

    # Step 3 - build the prompt and send to Ollama
    system_prompt = f"""You are a helpful customer support assistant for TechNova.
Answer the user's question using ONLY the context provided below.
If the answer is not in the context, say "I'm sorry, I don't have information about that. Please contact support@technova.com"

Context:
{context}"""
    
    response = httpx.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": "llama3.2",
            "messages": [
                {"role": "system", "content": system_prompt},
                *body.messages
            ],
            "stream": False
        },
        timeout=120
    )
    data = response.json()
    return {"reply": data["message"]["content"]}

