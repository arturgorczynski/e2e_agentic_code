# RAG: nine standalone lessons

These lessons use six shipped, versioned Acme documents: three finance reports and
three authored research notes under `live_example/data/documents/content/`. They are
fictional teaching sources. Each notebook starts from the files and runs independently;
no previous notebook state is required. The notebooks leave their outputs empty in Git.
The shared loader excludes sections that merely list evaluation questions or
retrieval exercises; those are test prompts, not answer evidence. Section IDs
retain their original numbers so source references do not silently shift.

| Lesson | Main question | Runtime |
| --- | --- | --- |
| [01 Chunking](01_chunking.ipynb) | What do length, overlap, semantic breaks and parent/child chunks change? | local text embeddings |
| [02 Advanced and multimodal](02_advanced_multimodal_chunking.ipynb) | How do tables, diagrams, image descriptions and provenance survive chunking? | local vision chat and multimodal embeddings |
| [03 Embeddings](03_embeddings_and_clusters.ipynb) | What do vectors represent, and what can 3D UMAP and clusters show? | local text and multimodal embeddings |
| [04 Exact neighbors](04_exact_nearest_neighbors.ipynb) | How does exhaustive cosine retrieval rank every fragment? | local text embeddings |
| [05 Approximate neighbors](05_approximate_neighbors.ipynb) | How do IVF and HNSW trade candidate count against recall? | local embeddings, in-memory Chroma |
| [06 Index lifecycle](06_build_and_maintain_index.ipynb) | How do versions, hashes, upsert, delete and verified retrieval fit together? | disposable local Chroma |
| [07 BM25 and hybrid](07_bm25_and_hybrid.ipynb) | How do term statistics and RRF complement dense retrieval? | local embeddings, BM25 |
| [08 Clef reranking](08_rerankers_with_clef.ipynb) | How does System One rescore a short candidate list? | Clef Flash and Clef |
| [09 Full RAG](09_end_to_end_rag.ipynb) | How does retrieval become a grounded, cited answer? | local Chroma, BM25, Clef Flash, selected chat model |

## Run

From the repository root:

```powershell
uv sync --locked --group rag
ollama pull qwen3-embedding:0.6b
uv run --group rag python scripts/verify_rag_notebooks.py
uv run --group rag python scripts/verify_rag_notebooks.py --execute 01_chunking.ipynb
```

Pull the additional local models when you reach their lessons:

```powershell
# Lessons 02 and 03: shared image/text embeddings; 02 also captions an image.
ollama pull embeddinggemma-2:latest
ollama pull gemma4:12b
# Lesson 08 compares both rerankers; 09 uses Clef Flash by default.
ollama pull clef-flash:latest
ollama pull clef:latest
```

Lesson 09 also needs the chat model selected by `[selection].main` in the root
`models.toml`. If that profile is local, pull its `OLLAMA_MODEL` from `.env`.

Select the root `.venv` kernel in VS Code or Jupyter. `--execute` starts a **fresh
kernel for each named lesson** and writes executed copies only to ignored
`.tmp/rag/executed/`; it never rewrites the teaching notebooks. The static check
validates notebook JSON and the repository convention: all imports are in the
first code cell. To execute all nine, omit the filename after `--execute`.

Model settings live only in the root `.env` (copy `.env.example` if needed):
`RAG_EMBED_MODEL` defaults to `qwen3-embedding:0.6b`, `RAG_VISION_MODEL` to
`gemma4:12b`, `RAG_MULTIMODAL_EMBED_MODEL` to `embeddinggemma-2:latest`,
`RAG_RERANK_MODELS` to `clef-flash:latest,clef:latest`, and
`RAG_RERANK_MODEL` to `clef-flash:latest` for lesson 09. `OLLAMA_BASE_URL` selects
the local Ollama server. The final answer model uses the shared `get_model()`
factory and `[selection].main` in root `models.toml`; it may be a cloud provider
if you choose one. Model downloads and inference stay local with the default
configuration.

Clef models use Ollama's **System One** API, not chat. An older local tag may be
rejected as an unsupported format; the two `ollama pull` commands above refresh
it. The image-caption lesson uses a vision **chat** model instead. It also
compares text and image vectors from EmbeddingGemma 2's shared multimodal
space. A caption fed to the text-only embedder is a different representation;
the two model spaces cannot be mixed in one index.

Chroma is deliberately local: lesson 05 and 09 use `EphemeralClient`, while 06
uses a disposable `PersistentClient` directory under `.tmp/rag`. These examples
do not change Acme's running portal or its separate mock retrieval. Source
hashes and IDs remain visible so a ranking can be checked against the actual
document. Acme access scopes are metadata for teaching, not user authentication.

Reference APIs: [Ollama embeddings and System One](https://github.com/ollama/ollama/blob/main/docs/api.md),
[Clef decision schema](https://ollama.com/library/clef),
[EmbeddingGemma 2 multimodal model](https://ollama.com/library/embeddinggemma-2),
[Chroma clients](https://docs.trychroma.com/reference/python),
[Chroma HNSW configuration](https://cookbook.chromadb.dev/core/configuration/),
[FAISS index families](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes),
and [UMAP clustering caveats](https://umap-learn.readthedocs.io/en/latest/clustering.html).
