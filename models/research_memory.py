import os
import time
from typing import List, Any
import chromadb
from dotenv import load_dotenv


class ResearchMemoryStore:
    def __init__(self, persist_directory: str = ".nexus_memory"):
        load_dotenv()
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.chroma_client.get_or_create_collection(name="research_dossiers")

        # Initialize a secondary collection specifically tailored for processed Insights
        self.insight_collection = self.chroma_client.get_or_create_collection(name="synthesis_insights")

    def cache_dossier_sources(self, query: str, sources: List[Any]):
        """Persists a bundle of extracted academic sources directly into local vector storage."""
        if not sources:
            return

        documents = []
        metadatas = []
        ids = []

        for index, src in enumerate(sources):
            src_id = getattr(src, 'id', f"src_{int(time.time())}_{index}")
            title = getattr(src, 'title', 'Unknown Title')
            abstract = getattr(src, 'abstract', '')
            year = getattr(src, 'year', 'N/A')
            url = getattr(src, 'url', 'N/A')

            text_content = abstract if abstract else title

            documents.append(text_content)
            ids.append(src_id)
            metadatas.append({
                "search_query": query,
                "title": title,
                "year": str(year),
                "url": url,
                "timestamp": str(time.time())
            })

        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"[Research Memory Cache]: Stored {len(sources)} text vectors to secure disk allocation.")
        except Exception as e:
            print(f"[Research Memory Warning]: Caching encountered an issue: {e}")

    def query_historical_memories(self, query: str, limit: int = 5) -> List[dict]:
        """Cross-references current requests against historical vectors to pinpoint cached items."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit
            )

            cached_sources = []
            if results and 'documents' in results and results['documents']:
                for i in range(len(results['documents'][0])):
                    meta = results['metadatas'][0][i]
                    doc = results['documents'][0][i]
                    src_id = results['ids'][0][i]

                    cached_sources.append({
                        "id": src_id,
                        "title": meta.get("title", "Unknown Title"),
                        "abstract": doc,
                        "year": meta.get("year", "N/A"),
                        "url": meta.get("url", "N/A"),
                        "source_type": "academic"
                    })
            return cached_sources
        except Exception as e:
            print(f"[Research Memory Error]: Memory query retrieval aborted: {e}")
            return []

    # =========================================================================
    # NEW INSIGHT CACHING ENGINE LAYER
    # =========================================================================
    def cache_final_insight(self, query: str, insight_payload: dict, multidimensional_data: dict):
        """Saves the final verified Gemini insights alongside Phase 5 structured sections."""
        try:
            import json

            # Extract the raw text summary from nested dictionary layers defensively
            if isinstance(insight_payload, dict):
                inner = insight_payload.get('insight', '')
                if isinstance(inner, dict):
                    insight_text = inner.get('insight', str(inner))
                else:
                    insight_text = str(inner)
            else:
                insight_text = str(insight_payload)

            self.insight_collection.add(
                documents=[insight_text],  # <-- Guaranteed to be a plain string now!
                metadatas=[{
                    "query": query,
                    "themes": json.dumps(multidimensional_data.get('themes', [])),
                    "contradictions": json.dumps(multidimensional_data.get('contradictions', [])),
                    "research_gaps": json.dumps(multidimensional_data.get('research_gaps', [])),
                    "opportunity_areas": json.dumps(multidimensional_data.get('opportunity_areas', [])),
                    "timestamp": str(time.time())
                }],
                ids=[f"insight_{int(time.time())}"]
            )
            print("[Research Memory Cache]: Successfully cached final synthesized insight vectors to local disk.")
        except Exception as e:
            print(f"[Research Memory Warning]: Failed to index insight parameters: {e}")

    def query_historical_insight(self, query: str) -> dict:
        """Looks up existing semantic insights strictly matching the target query name."""
        try:
            results = self.insight_collection.query(
                query_texts=[query],
                n_results=1,
                where={"query": query}
            )

            # Safe defensive nesting validation checks
            if results and 'documents' in results and results['documents'] and len(results['documents'][0]) > 0:
                import json

                # Unpack the first match out of the inner response lists safely
                meta = results['metadatas'][0][0]
                doc = results['documents'][0][0]

                return {
                    "insight": {"theme": query, "insight": doc},
                    "themes": json.loads(meta.get("themes", "[]")),
                    "contradictions": json.loads(meta.get("contradictions", "[]")),
                    "research_gaps": json.loads(meta.get("research_gaps", "[]")),
                    "opportunity_areas": json.loads(meta.get("opportunity_areas", "[]")),
                    "cached_hit": True
                }
        except Exception as e:
            print(f"[Research Memory Warning]: Historical insight look-up defaulted: {e}")
        return None