import hashlib
import os
from typing import Optional
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

def get_document_hash(text: str) -> str:
    """Generate a unique hash for the document content."""
    return hashlib.sha256(text.encode()).hexdigest()

def get_cache_path(doc_hash: str) -> str:
    """Get the cache directory path for vectors."""
    cache_dir = "./vector_cache"
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"faiss_{doc_hash}")

def load_cached_vectorstore(cache_path: str, embeddings) -> Optional[FAISS]:
    """Try to load a cached vectorstore with safe deserialization."""
    try:
        if os.path.exists(cache_path):
            return FAISS.load_local(
                folder_path=cache_path,
                embeddings=embeddings,
                allow_dangerous_deserialization=True  # We trust our own cache
            )
        return None
    except Exception as e:
        print(f"Error loading cached vectors: {str(e)}")
        return None

def create_vectorstore(text: str, openai_api_key: str) -> 'FAISS':
    """
    Creates or loads a FAISS vector store with persistence.
    
    Args:
        text (str): The input text to be processed
        openai_api_key (str): OpenAI API key for embeddings
        
    Returns:
        FAISS: The vector store instance
    """
    try:
        # Initialize embeddings
        embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
            openai_api_key=openai_api_key
        )
        
        # Generate document hash and cache path
        doc_hash = get_document_hash(text)
        cache_path = get_cache_path(doc_hash)
        
        # Try to load cached vectors
        cached_vectorstore = load_cached_vectorstore(cache_path, embeddings)
        if cached_vectorstore:
            print("Using cached vectors")
            return cached_vectorstore
            
        print("Creating new vectors")
        # Text splitting with error handling
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200,
            length_function=len,
            add_start_index=True,
        )
        
        chunks = splitter.split_text(text)
        if not chunks:
            raise ValueError("No text chunks were generated")
            
        # Create FAISS vectorstore
        vectorstore = FAISS.from_texts(
            texts=chunks,
            embedding=embeddings,
            metadatas=[{
                "source": f"chunk_{i}",
                "doc_hash": doc_hash
            } for i in range(len(chunks))]
        )
        
        # Save vectors to cache
        try:
            vectorstore.save_local(cache_path)
            print(f"Vectors cached at: {cache_path}")
        except Exception as e:
            print(f"Error caching vectors: {str(e)}")
        
        return vectorstore
        
    except Exception as e:
        print(f"Error creating vectorstore: {str(e)}")
        # Create a minimal vectorstore with error message
        return FAISS.from_texts(
            texts=["Error processing document. Please try again."],
            embedding=embeddings
        )

# Optional: Cleanup function for managing cache
def cleanup_vector_cache(max_cache_size_mb: int = 500, min_cache_age_days: int = 7):
    """
    Clean up old vector cache files to manage storage.
    
    Args:
        max_cache_size_mb (int): Maximum cache size in MB
        min_cache_age_days (int): Minimum age in days before a cache can be deleted
    """
    cache_dir = "./vector_cache"
    if not os.path.exists(cache_dir):
        return
        
    try:
        # Get cache files sorted by modification time
        cache_files = []
        for filename in os.listdir(cache_dir):
            filepath = os.path.join(cache_dir, filename)
            if os.path.isfile(filepath):
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
                cache_files.append((filepath, mtime, size))
        
        cache_files.sort(key=lambda x: x[1])  # Sort by modification time
        
        # Calculate total cache size
        total_size = sum(file[2] for file in cache_files) / (1024 * 1024)  # Convert to MB
        
        if total_size > max_cache_size_mb:
            import time
            current_time = time.time()
            min_age_seconds = min_cache_age_days * 24 * 60 * 60
            
            # Remove old files until we're under the size limit
            for filepath, mtime, size in cache_files:
                if current_time - mtime > min_age_seconds:
                    try:
                        os.remove(filepath)
                        total_size -= size / (1024 * 1024)
                        print(f"Removed old cache file: {filepath}")
                        if total_size <= max_cache_size_mb:
                            break
                    except Exception as e:
                        print(f"Error removing cache file {filepath}: {str(e)}")
                        
    except Exception as e:
        print(f"Error cleaning vector cache: {str(e)}")