"""
OpenNotebook.py — RAG Legal Itosturre
Motor de auditoría anti-alucinaciones para escritos jurídicos.

Comandos:
  python OpenNotebook.py ingest --directory /ruta/a/pdfs/
  python OpenNotebook.py audit --text "texto del borrador"
  python OpenNotebook.py audit --file /ruta/borrador.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

# ─────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────

CHROMA_PATH = "/home/licjo/chroma_db"
COLLECTION_NAME = "corpus_legal_itosturre"
EMBED_MODEL = "intfloat/multilingual-e5-small"

# PDFs legales — excluir documentos personales
EXCLUDE_PATTERNS = [
    "ActaNacimiento", "Chapter_1es", "CONSIGNA", "Bloc de notas",
    "Battlefield", "Marvel", "FrameView", "SOFÍA", "desktop"
]

# Patrones de referencias legales en texto
ARTICLE_PATTERNS = [
    r'[Aa]rt[íi]culo[s]?\s+(\d+[\w\-]*)(?:\s*,\s*(?:fracci[oó]n|frac\.|p[áa]rrafo|p[áa]rr\.)\s+[\w\.]+)?(?:\s+(?:del?|de la)\s+([A-Z][A-Za-záéíóúñÁÉÍÓÚÑ\s]+))?',
    r'[Aa]rt\.\s*(\d+[\w\-]*)(?:\s*,?\s*(?:frac\.|fracci[oó]n)\s+[\w\.]+)?(?:\s+(?:del?|de la)\s+([A-Z][A-Za-záéíóúñÁÉÍÓÚÑ\s]+))?',
    r'[Rr]egistro\s+(?:digital[:\s]+)?(\d{7})',
]

# Abreviaciones → nombre completo del ordenamiento
LAW_ALIASES = {
    "CPEUM": "Constitución Política de los Estados Unidos Mexicanos",
    "CFF": "Código Fiscal de la Federación",
    "LISR": "Ley del Impuesto sobre la Renta",
    "LFPCA": "Ley Federal de Procedimiento Contencioso Administrativo",
    "LFPA": "Ley Federal de Procedimiento Administrativo",
    "CADH": "Convención Americana sobre Derechos Humanos",
    "LFPDPPP": "Ley Federal de Protección de Datos Personales",
    "LFPC": "Ley Federal de Protección al Consumidor",
    "LIVA": "Ley del Impuesto al Valor Agregado",
    "TJAJ": "Ley de Justicia Administrativa del Estado de Jalisco",
    "LPAJM": "Ley del Procedimiento Administrativo del Estado de Jalisco",
}


# ─────────────────────────────────────────
# EMBEDDINGS Y CHROMA
# ─────────────────────────────────────────

def get_embedder():
    print(f"⏳ Cargando modelo de embeddings: {EMBED_MODEL}...")
    return SentenceTransformer(EMBED_MODEL)


def get_collection(embedder):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # Clase wrapper para ChromaDB con sentence-transformers
    class STEmbeddingFunction:
        def __init__(self, model):
            self.model = model
        def name(self):
            return "itosturre-st-embedder"
        def __call__(self, input):
            return self.model.encode(input, normalize_embeddings=True).tolist()
        def embed_documents(self, input):
            return self.model.encode(input, normalize_embeddings=True).tolist()
        def embed_query(self, input):
            if isinstance(input, str):
                input = [input]
            return self.model.encode(input, normalize_embeddings=True).tolist()

    ef = STEmbeddingFunction(embedder)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


# ─────────────────────────────────────────
# INGESTA
# ─────────────────────────────────────────

def is_legal_pdf(path: Path) -> bool:
    name = path.name
    for pat in EXCLUDE_PATTERNS:
        if pat.lower() in name.lower():
            return False
    return path.suffix.lower() == ".pdf"


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def ingest(directory: str):
    pdf_dir = Path(directory)
    pdfs = [p for p in pdf_dir.iterdir() if is_legal_pdf(p)]

    if not pdfs:
        print(f"❌ No se encontraron PDFs legales en: {directory}")
        sys.exit(1)

    print(f"📚 PDFs encontrados: {len(pdfs)}")

    embedder = get_embedder()
    collection = get_collection(embedder)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\nArtículo ", "\nARTÍCULO ", "\n\n", "\n", " "]
    )

    total_chunks = 0
    for pdf_path in pdfs:
        print(f"  🔍 Procesando: {pdf_path.name}")
        try:
            raw_text = extract_text_from_pdf(pdf_path)
            if len(raw_text.strip()) < 100:
                print(f"     ⚠️  Texto muy corto, omitiendo.")
                continue

            chunks = splitter.split_text(raw_text)
            print(f"     📄 {len(chunks)} chunks generados")

            # Insertar en lotes de 50
            batch_size = 50
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                ids = [f"{pdf_path.stem}_chunk_{i + j}" for j in range(len(batch))]
                metadatas = [{"source": pdf_path.name, "law": pdf_path.stem} for _ in batch]

                # Evitar duplicados
                existing = collection.get(ids=ids)
                existing_ids = set(existing["ids"])
                new_batch = [(id_, doc, meta) for id_, doc, meta in zip(ids, batch, metadatas)
                             if id_ not in existing_ids]

                if new_batch:
                    n_ids, n_docs, n_metas = zip(*new_batch)
                    collection.add(
                        ids=list(n_ids),
                        documents=list(n_docs),
                        metadatas=list(n_metas)
                    )

            total_chunks += len(chunks)
            print(f"     ✅ Indexado correctamente")

        except Exception as e:
            print(f"     ❌ Error procesando {pdf_path.name}: {e}")

    print(f"\n✅ INGESTA COMPLETADA")
    print(f"   PDFs procesados : {len(pdfs)}")
    print(f"   Chunks totales  : {total_chunks}")
    print(f"   Base vectorial  : {CHROMA_PATH}")
    print(f"   Colección       : {COLLECTION_NAME}")


# ─────────────────────────────────────────
# AUDITORÍA
# ─────────────────────────────────────────

def extract_references(text: str) -> list:
    """Extrae referencias a artículos y jurisprudencias del borrador."""
    refs = []

    # Artículos legales
    art_pattern = re.compile(
        r'[Aa]rt[íi]?(?:culo)?s?\.?\s+(\d+[\w\-]*)(?:[°º])?'
        r'(?:\s*,?\s*(?:fracci[oó]n|frac\.)\s+([\w\.]+))?'
        r'(?:\s+(?:del?|de la)\s+([\w\s,ÁÉÍÓÚÑ]+?))?'
        r'(?=[\s,\.;]|$)'
    )
    for m in art_pattern.finditer(text):
        art_num = m.group(1)
        frac = m.group(2) or ""
        law_raw = (m.group(3) or "").strip().rstrip(",")

        # Resolver alias de ordenamiento
        law_name = None
        for alias, full_name in LAW_ALIASES.items():
            if alias in text[max(0, m.start()-5):m.end()+60]:
                law_name = full_name
                break
        if not law_name and law_raw:
            law_name = law_raw

        refs.append({
            "type": "article",
            "article": art_num,
            "fraction": frac,
            "law": law_name or "desconocido",
            "raw": m.group(0).strip()
        })

    # Registros digitales SJF
    reg_pattern = re.compile(r'[Rr]egistro\s+(?:digital[:\s]+)?(\d{6,8})')
    for m in reg_pattern.finditer(text):
        refs.append({
            "type": "jurisprudencia",
            "registro": m.group(1),
            "raw": m.group(0).strip()
        })

    return refs


def audit(text: str) -> dict:
    """
    Audita el borrador contra el corpus legal.
    Retorna JSON con alerts y retrieved_sources.
    """
    embedder = get_embedder()

    # Verificar que existe la base vectorial
    chroma_path = Path(CHROMA_PATH)
    if not chroma_path.exists():
        return {
            "status": "error",
            "message": "Base vectorial no encontrada. Ejecuta primero: python OpenNotebook.py ingest --directory /ruta/pdfs/",
            "alerts": [],
            "retrieved_sources": []
        }

    collection = get_collection(embedder)

    if collection.count() == 0:
        return {
            "status": "error",
            "message": "La colección está vacía. Ejecuta primero el comando ingest.",
            "alerts": [],
            "retrieved_sources": []
        }

    refs = extract_references(text)
    alerts = []
    retrieved_sources = []
    verified_count = 0

    for ref in refs:
        if ref["type"] == "article":
            # Construir query de búsqueda
            query = f"Artículo {ref['article']}"
            if ref["fraction"]:
                query += f" fracción {ref['fraction']}"
            if ref["law"] and ref["law"] != "desconocido":
                query += f" {ref['law']}"

            results = collection.query(
                query_texts=[query],
                n_results=3
            )

            if results and results["documents"] and results["documents"][0]:
                best_doc = results["documents"][0][0]
                best_source = results["metadatas"][0][0]["source"] if results["metadatas"] else "desconocido"
                best_distance = results["distances"][0][0] if results.get("distances") else 1.0

                # Si la distancia coseno es alta (>0.6), posible alucinación
                if best_distance > 0.6:
                    alerts.append(
                        f"ALERTA: '{ref['raw']}' — no se encontró coincidencia confiable en el corpus "
                        f"(distancia: {best_distance:.2f}). Verificar manualmente."
                    )
                else:
                    retrieved_sources.append({
                        "reference": ref["raw"],
                        "law": ref["law"],
                        "article": ref["article"],
                        "source_file": best_source,
                        "relevance_score": round(1 - best_distance, 2),
                        "retrieved_text": best_doc[:500]
                    })
                    verified_count += 1
            else:
                alerts.append(
                    f"ALERTA: El borrador cita '{ref['raw']}' pero no se encontró en el corpus legal. "
                    f"Posible alucinación — verificar en fuente oficial."
                )

        elif ref["type"] == "jurisprudencia":
            # Buscar registro en corpus de jurisprudencia
            query = f"Registro digital {ref['registro']}"
            results = collection.query(
                query_texts=[query],
                n_results=2
            )

            # También buscar en el corpus local de tesis
            tesis_path = Path("/home/licjo/jurisprudencia")
            found_in_tesis = False
            if tesis_path.exists():
                for json_file in tesis_path.glob("*.json"):
                    try:
                        data = json.loads(json_file.read_text())
                        for item in (data if isinstance(data, list) else []):
                            if str(ref["registro"]) in str(item.get("registro", "")):
                                found_in_tesis = True
                                retrieved_sources.append({
                                    "reference": ref["raw"],
                                    "registro": ref["registro"],
                                    "source_file": json_file.name,
                                    "relevance_score": 1.0,
                                    "retrieved_text": item.get("texto_completo", "Tesis verificada en corpus SJF.")
                                })
                                verified_count += 1
                                break
                    except Exception:
                        continue

            if not found_in_tesis:
                alerts.append(
                    f"ALERTA: El borrador cita el Registro digital {ref['registro']} "
                    f"pero no fue encontrado en el corpus de jurisprudencia. "
                    f"Verificar en sjf2.scjn.gob.mx antes de citar."
                )

    return {
        "status": "ok",
        "total_references_found": len(refs),
        "verified": verified_count,
        "alerts_count": len(alerts),
        "alerts": alerts,
        "retrieved_sources": retrieved_sources,
        "summary": f"Auditoría RAG completada: {verified_count} fuentes verificadas, {len(alerts)} alertas."
    }


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OpenNotebook — RAG Legal Itosturre"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Comando: ingest
    ingest_parser = subparsers.add_parser("ingest", help="Indexar PDFs en ChromaDB")
    ingest_parser.add_argument(
        "--directory", required=True,
        help="Carpeta con PDFs legales"
    )

    # Comando: audit
    audit_parser = subparsers.add_parser("audit", help="Auditar un borrador legal")
    audit_group = audit_parser.add_mutually_exclusive_group(required=True)
    audit_group.add_argument("--text", help="Texto del borrador (string)")
    audit_group.add_argument("--file", help="Ruta al archivo del borrador (.md/.txt)")

    args = parser.parse_args()

    if args.command == "ingest":
        ingest(args.directory)

    elif args.command == "audit":
        if args.file:
            draft_text = Path(args.file).read_text(encoding="utf-8")
        else:
            draft_text = args.text

        result = audit(draft_text)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
