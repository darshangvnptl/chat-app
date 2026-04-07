from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
import chromadb
import os

# Load documents from the "docs" directory
docs_path = "docs"
documents = []

for filename in os.listdir(docs_path):
    if filename.endswith(".txt"):
        filepath = os.path.join(docs_path, filename)
        loader = TextLoader(filepath)
        documents.extend(loader.load())

print(f"Loaded {len(documents)} documents")

# Split documents into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=20
)

chunks = text_splitter.split_documents(documents)
print(f"Split into {len(chunks)} chunks")

# Initialize Ollama embeddings
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://192.168.1.94:11434"
)

# Create ChromaDB collection
client = chromadb.PersistentClient(path="./vectordb")
collection = client.get_or_create_collection(name="technova_docs")

for i, chunk in enumerate(chunks):
    embedding = embeddings.embed_query(chunk.page_content)
    collection.add(
        ids=[str(i)],
        embeddings=[embedding],
        documents=[chunk.page_content],
        metadatas=[{"source": chunk.metadata["source"]}]
    )

print(f"Stored {len(chunks)} chunks in ChromaDB")

# Example query
results = collection.query(
    query_embeddings=[embeddings.embed_query("how do I reset my password")],
    n_results=2
)

print(results["documents"])