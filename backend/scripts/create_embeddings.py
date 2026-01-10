"""
Generate embeddings for document chunks using OpenAI and store in Supabase.
"""

import asyncio
import sys
from pathlib import Path
from typing import List
import logging

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from openai import OpenAI
from config import settings
from database.supabase_client import supabase_client
from scripts.process_documents import (
    process_brigade_citrine_brochure,
    process_avalon_brochure,
    DocumentChunk
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for text using OpenAI."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.model = settings.embedding_model
        self.batch_size = 100  # Process in batches to avoid rate limits

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                encoding_format="float"
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise


async def insert_chunks_with_embeddings(
    chunks: List[DocumentChunk],
    project_id: str,
    document_id: str,
    embedding_generator: EmbeddingGenerator
) -> int:
    """
    Generate embeddings for chunks and insert into Supabase.

    Args:
        chunks: List of document chunks
        project_id: UUID of the project
        document_id: UUID of the document
        embedding_generator: EmbeddingGenerator instance

    Returns:
        Number of successfully inserted chunks
    """
    inserted_count = 0
    batch_size = embedding_generator.batch_size

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        try:
            # Generate embeddings for batch
            texts = [chunk.content for chunk in batch]
            embeddings = embedding_generator.generate_embeddings_batch(texts)

            # Insert each chunk with its embedding
            for chunk, embedding in zip(batch, embeddings):
                chunk_data = {
                    "document_id": document_id,
                    "project_id": project_id,
                    "content": chunk.content,
                    "embedding": embedding,
                    "section": chunk.metadata.get("section", ""),
                    "source_type": "internal",
                    "confidence_weight": 1.0,
                    "chunk_index": chunk.chunk_index,
                    "metadata": chunk.metadata
                }

                chunk_id = await supabase_client.insert_document_chunk(chunk_data)
                if chunk_id:
                    inserted_count += 1

            logger.info(f"Inserted batch {i // batch_size + 1}: {len(batch)} chunks")

        except Exception as e:
            logger.error(f"Error processing batch {i // batch_size + 1}: {e}")

    return inserted_count


async def process_and_store_brigade_citrine(pdf_path: str, project_id: str) -> None:
    """
    Process Brigade Citrine brochure and store in Supabase.

    Args:
        pdf_path: Path to the Brigade Citrine PDF
        project_id: UUID of the Brigade Citrine project in database
    """
    logger.info("Processing Brigade Citrine brochure...")

    # Process PDF into chunks
    chunks = process_brigade_citrine_brochure(pdf_path)
    logger.info(f"Created {len(chunks)} chunks from Brigade Citrine brochure")

    # Insert document record
    document_id = await supabase_client.insert_document(
        project_id=project_id,
        title="Brigade Citrine E-Brochure 01-1",
        doc_type="brochure",
        file_path=pdf_path,
        version="1.0"
    )

    if not document_id:
        logger.error("Failed to insert document record")
        return

    logger.info(f"Created document record with ID: {document_id}")

    # Generate embeddings and insert chunks
    embedding_generator = EmbeddingGenerator()
    inserted_count = await insert_chunks_with_embeddings(
        chunks=chunks,
        project_id=project_id,
        document_id=document_id,
        embedding_generator=embedding_generator
    )

    logger.info(f"Successfully inserted {inserted_count}/{len(chunks)} chunks for Brigade Citrine")


async def process_and_store_avalon(pdf_path: str, project_id: str) -> None:
    """
    Process Avalon brochure and store in Supabase.

    Args:
        pdf_path: Path to the Avalon PDF
        project_id: UUID of the Avalon project in database
    """
    logger.info("Processing Avalon brochure...")

    # Process PDF into chunks
    chunks = process_avalon_brochure(pdf_path)
    logger.info(f"Created {len(chunks)} chunks from Avalon brochure")

    # Insert document record
    document_id = await supabase_client.insert_document(
        project_id=project_id,
        title="E-Brochure - Avalon",
        doc_type="brochure",
        file_path=pdf_path,
        version="1.0"
    )

    if not document_id:
        logger.error("Failed to insert document record")
        return

    logger.info(f"Created document record with ID: {document_id}")

    # Generate embeddings and insert chunks
    embedding_generator = EmbeddingGenerator()
    inserted_count = await insert_chunks_with_embeddings(
        chunks=chunks,
        project_id=project_id,
        document_id=document_id,
        embedding_generator=embedding_generator
    )

    logger.info(f"Successfully inserted {inserted_count}/{len(chunks)} chunks for Avalon")


async def main():
    """Main function to process documents and generate embeddings."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate embeddings for real estate project documents")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--project-id", required=True, help="Project UUID in database")
    parser.add_argument("--project-name", required=True, choices=["citrine", "avalon"], help="Project name")

    args = parser.parse_args()

    if args.project_name == "citrine":
        await process_and_store_brigade_citrine(args.pdf, args.project_id)
    elif args.project_name == "avalon":
        await process_and_store_avalon(args.pdf, args.project_id)


if __name__ == "__main__":
    asyncio.run(main())
