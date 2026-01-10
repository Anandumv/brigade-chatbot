# Vectorization Guide: From Brochure to Bot 🧞‍♂️

This guide explains how to take a PDF (like a property brochure) and make it searchable by Pinclick Genie using vector embeddings.

## Overview
1.  **Parse**: Convert PDF to clean text chunks.
2.  **Embed**: Convert text chunks into vector arrays (numbers) using Voyage AI or OpenAI.
3.  **Store**: Save vectors + text to Supabase `document_chunks` table.

## Step 1: Parsing (PDF -> Text)
Use a tool like `PyPDF2` or `LlamaParse` to extract text.

```python
# Example: Simple Text Extraction
from pypdf import PdfReader

reader = PdfReader("brochure.pdf")
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n"
```

## Step 2: Chunking
Don't embed the whole PDF at once. Split it into chunks (e.g., 500 words).

```python
# Split by paragraphs or fixed size
chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
```

## Step 3: Embedding (Text -> Vector)
Use the `voyage-3-lite` (or OpenAI) model to generate embeddings.

```python
import voyageai

vo = voyageai.Client()
documents = ["This is a chunk of text from the brochure..."]
embeddings = vo.embed(documents, model="voyage-3-lite", input_type="document").embeddings
# each embedding is an array of 512 floats
```

## Step 4: Storing in Supabase
Push the text and its corresponding vector to the database.

```sql
-- The table structure looks like this:
-- document_chunks (
--    id uuid PRIMARY KEY,
--    content text,
--    embedding vector(512),
--    metadata jsonb
-- )
```

```python
import supabase

data = []
for i, chunk in enumerate(chunks):
    data.append({
        "content": chunk,
        "embedding": embeddings[i],
        "metadata": {
            "source": "brochure.pdf",
            "page": i
        }
    })

supabase.table("document_chunks").insert(data).execute()
```

## Best Practices
*   **Metadata**: Always tag chunks with `project_id` and `source_type` ("brochure", "price_sheet").
*   **Cleaning**: Remove footers/headers (like "Page 1 of 10") before embedding.
*   **Tables**: PDF tables are tricky. Convert them to JSON or Markdown text before embedding.
