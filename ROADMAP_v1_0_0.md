# Nexus Research AI v1.0.0 Strategic Roadmap

## 1. Vision Statement
Nexus Research AI aims to become an industry-standard autonomous research platform, providing a seamless bridge between raw data discovery and high-fidelity, human-verified synthesis.

## 2. Feature Analysis: Long-Term Memory (Vector Stores)
### ChromaDB (Local/Open Source)
- **Pros**: Zero cost, local data privacy, easier to bundle with the core OS.
- **Cons**: Requires local compute resources, harder to scale for enterprise-level multi-user environments.

### Pinecone (Cloud Native)
- **Pros**: Massive scalability, managed infrastructure, high performance for billion-scale vector searches.
- **Cons**: Cost-intensive, introduces cloud dependency and potential latency.

**Strategic Choice**: v1.0.0 will default to ChromaDB for privacy-first local research, with an optional plugin architecture for Pinecone integration.

## 3. Synthesis Evolution: Full-Text Analysis
Currently, Nexus Research AI synthesizes insights from abstracts. v1.0.0 will implement **Full-Text Retrieval** using PDF parsing libraries (e.g., PyMuPDF) to ingest entire research papers, ensuring deeper context and more robust factual grounding.

## 4. Development Pillars
- **Trust**: Every claim must be traceable to a specific page or paragraph in the source text.
- **Scalability**: Asynchronous agent execution to handle hundreds of sources simultaneously.
- **Human-Centric**: Natural language logs and interactive audit trails (Squire Agent enhancements).
