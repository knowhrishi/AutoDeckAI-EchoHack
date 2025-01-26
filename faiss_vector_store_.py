import os
import hashlib
import json
import time
from typing import Optional
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

class VectorStoreManager:
    def __init__(self, cache_dir: str = "./vector_cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _generate_doc_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
    
    def _get_cache_path(self, doc_hash: str) -> str:
        return os.path.join(self.cache_dir, f"{doc_hash}_faiss")
    
    def _save_metadata(self, doc_hash: str, metadata: dict):
        meta_path = os.path.join(self.cache_dir, f"{doc_hash}_meta.json")
        with open(meta_path, 'w') as f:
            json.dump(metadata, f)
    
    def create_vectorstore(self, text: str, openai_api_key: str) -> FAISS:
        """Create or load FAISS vector store with enhanced caching"""
        doc_hash = self._generate_doc_hash(text)
        cache_path = self._get_cache_path(doc_hash)
        
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=openai_api_key
        )
        
        # Try loading existing cache
        if os.path.exists(cache_path):
            try:
                return FAISS.load_local(
                    cache_path,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                print(f"Error loading cache: {str(e)}")
                
        # Create new vector store
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". "]
        )
        chunks = splitter.split_text(text)
        
        vectorstore = FAISS.from_texts(
            texts=chunks,
            embedding=embeddings,
            metadatas=[{"source": f"chunk_{i}"} for i in range(len(chunks))]
        )
        
        # Save to cache
        try:
            vectorstore.save_local(cache_path)
            self._save_metadata(doc_hash, {
                "created_at": time.time(),
                "chunk_count": len(chunks),
                "doc_length": len(text)
            })
        except Exception as e:
            print(f"Cache saving failed: {str(e)}")
            
        return vectorstore

    def cleanup_cache(self, max_size_gb: float = 2.0):
        """Automated cache cleanup with size management"""
        cache_files = []
        total_size = 0
        
        # Collect cache files
        for fname in os.listdir(self.cache_dir):
            if fname.endswith("_faiss"):
                path = os.path.join(self.cache_dir, fname)
                stat = os.stat(path)
                cache_files.append({
                    "path": path,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })
                total_size += stat.st_size
        
        # Convert to GB
        total_size_gb = total_size / (1024 ** 3)
        
        if total_size_gb > max_size_gb:
            # Sort by oldest first
            cache_files.sort(key=lambda x: x["mtime"])
            
            # Remove oldest until under limit
            for file_info in cache_files:
                try:
                    os.remove(file_info["path"])
                    meta_file = file_info["path"].replace("_faiss", "_meta.json")
                    if os.path.exists(meta_file):
                        os.remove(meta_file)
                    total_size_gb -= file_info["size"] / (1024 ** 3)
                    
                    if total_size_gb <= max_size_gb:
                        break
                except Exception as e:
                    print(f"Error removing cache file {file_info['path']}: {str(e)}")