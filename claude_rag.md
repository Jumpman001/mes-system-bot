# Corporate RAG Assistant for MES System (Gemini + Multilingual)

## 📌 Описание задачи
Интеграция RAG (Retrieval-Augmented Generation) модуля в Telegram-бота (aiogram 3). 
Цель: Создать кросс-язычного AI-ассистента, отвечающего на технические вопросы цеха строго по документам (.pdf, .docx). Ассистент должен уметь искать ответы в английской документации и отвечать на русском. Толерантность к галлюцинациям: 0%.

## 🛠 Технический стек RAG
- Основной фреймворк: `langchain` + `langchain-google-genai`
- LLM Provider: Google Gemini (`gemini-1.5-flash` или `gemini-1.5-pro` для генерации ответов)
- Embeddings: Google (`text-embedding-004`)
- Векторная База: `Chroma` (локально в `chroma_db/`)
- Парсинг: `PyPDFLoader` (для .pdf), `Docx2txtLoader` (для .docx)

## 🏗 Архитектура пайплайна

### Процесс 1: Ingestion (Скрипт загрузки данных `ai_agent/ingest.py`)
1. Скрипт сканирует папку `data/docs/` на наличие файлов `.pdf` и `.docx`.
2. Использует соответствующие загрузчики LangChain.
3. Разбивает текст (`RecursiveCharacterTextSplitter`: chunk_size=1000, chunk_overlap=150).
4. Генерирует Google Embeddings и сохраняет векторы локально в `Chroma`.

### Процесс 2: Retrieval & Generation (Интеграция в Telegram `bot/handlers/ai_assistant.py`)
1. Команда `/ask <вопрос>`.
2. Поиск по ChromaDB (top_k=4).
3. Промпт: "Ты главный инженер завода. Отвечай на вопрос пользователя на том языке, на котором задан вопрос, используя ТОЛЬКО предоставленный контекст. Если ответа нет в тексте, скажи: 'В документации нет информации'. Не фантазируй."
4. Вызов Gemini LLM (через асинхронный `.ainvoke()`).

## 🤖 Правила для AI при написании кода
1. Добавь `GEMINI_API_KEY` в `core/config.py`.
2. Напиши скрипт `ingest.py` так, чтобы его можно было запускать отдельно из консоли для обновления базы знаний.
3. Напиши `rag_chain.py` (настройка цепочки) и `bot/handlers/ai_assistant.py` (хэндлер бота).
4. Не забывай про асинхронность при вызове LLM из хэндлера aiogram.