"""
Скрипт загрузки документов в ChromaDB (Ingestion Pipeline).

Сканирует data/docs/ на .pdf и .docx файлы, нарезает на чанки
и сохраняет эмбеддинги (HuggingFace all-MiniLM-L6-v2) в локальную ChromaDB.

Запуск:
    python -m ai_agent.ingest
"""

import sys
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# ── Пути ────────────────────────────────────────────────────────────────
# Корень проекта — на два уровня выше этого файла
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "data" / "docs"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

# ── Параметры ───────────────────────────────────────────────────────────
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "mes_docs"


def load_documents(docs_dir: Path) -> list:
    """Загружает все .pdf и .docx файлы из указанной директории."""
    documents = []

    if not docs_dir.exists():
        print(f"❌ Папка {docs_dir} не найдена. Создайте её и положите туда документы.")
        sys.exit(1)

    files = list(docs_dir.glob("*.pdf")) + list(docs_dir.glob("*.docx"))

    if not files:
        print(f"⚠️  В папке {docs_dir} нет .pdf или .docx файлов.")
        sys.exit(1)

    for file_path in sorted(files):
        print(f"  📄 Загружаю: {file_path.name}")
        try:
            if file_path.suffix.lower() == ".pdf":
                loader = PyPDFLoader(str(file_path))
            else:
                loader = Docx2txtLoader(str(file_path))
            documents.extend(loader.load())
        except Exception as e:
            print(f"  ⚠️  Ошибка при загрузке {file_path.name}: {e}")

    return documents


def split_documents(documents: list) -> list:
    """Разбивает документы на чанки."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    return chunks


def create_vectorstore(chunks: list) -> None:
    """Создаёт / перезаписывает ChromaDB из чанков."""
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # Если база уже существует — удаляем, чтобы пересоздать с нуля
    if CHROMA_DIR.exists():
        import shutil
        shutil.rmtree(CHROMA_DIR)
        print("  🗑  Старая ChromaDB удалена.")

    print(f"  💾 Сохраняю {len(chunks)} чанков в ChromaDB ({CHROMA_DIR}) …")

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
    )

    print("  ✅ ChromaDB успешно создана!")


def main() -> None:
    print("=" * 60)
    print("🚀 MES RAG Ingestion Pipeline (Local HuggingFace Embeddings)")
    print("=" * 60)

    # 1. Загрузка документов
    print("\n📂 Шаг 1/3 — Загрузка документов …")
    documents = load_documents(DOCS_DIR)
    print(f"  → Загружено {len(documents)} страниц/секций.\n")

    # 2. Нарезка на чанки
    print("✂️  Шаг 2/3 — Нарезка на чанки …")
    chunks = split_documents(documents)
    print(f"  → Получено {len(chunks)} чанков "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}).\n")

    # 3. Векторизация и сохранение
    print("🧠 Шаг 3/3 — Генерация эмбеддингов и сохранение …")
    create_vectorstore(chunks)

    print("\n" + "=" * 60)
    print("🎉 Ingestion завершён! База знаний готова.")
    print("=" * 60)


if __name__ == "__main__":
    main()
