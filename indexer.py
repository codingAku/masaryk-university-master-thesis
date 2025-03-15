import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

def initialize_indexer(files):
    """
    Reads the domain files, splits them into chunks,
    computes embeddings, and builds a FAISS index.
    
    Args:
        files (list): List of file paths to your domain documents.
    
    Returns:
        documents (list): List of text chunks.
        index (faiss.Index): FAISS index built from the embeddings.
        embedding_model (SentenceTransformer): Model used for computing embeddings.
    """
    documents = []
    for file_path in files:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                # Split text into paragraphs; adjust chunking as needed.
                for para in text.split("\n\n"):
                    para = para.strip()
                    if para:
                        documents.append(para)
    
    # Load an embedding model (you can choose a different model if preferred)
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    doc_embeddings = embedding_model.encode(documents, convert_to_numpy=True)
    doc_embeddings = np.array(doc_embeddings).astype("float32")
    
    # Create a FAISS index using L2 distance
    embedding_dim = doc_embeddings.shape[1]
    index = faiss.IndexFlatL2(embedding_dim)
    index.add(doc_embeddings)
    
    return documents, index, embedding_model

def retrieve_context(query, documents, index, embedding_model, top_k=3):
    """
    Retrieves the top_k relevant text chunks for a given query.
    
    Args:
        query (str): The user query.
        documents (list): List of text chunks.
        index (faiss.Index): The FAISS index built from document embeddings.
        embedding_model (SentenceTransformer): Model to encode the query.
        top_k (int): Number of top matching chunks to retrieve.
    
    Returns:
        str: Concatenated text of the retrieved chunks.
    """
    query_embedding = embedding_model.encode([query], convert_to_numpy=True)
    query_embedding = np.array(query_embedding).astype("float32")
    distances, indices = index.search(query_embedding, top_k)
    relevant_chunks = [documents[i] for i in indices[0] if i < len(documents)]
    return "\n\n".join(relevant_chunks)
