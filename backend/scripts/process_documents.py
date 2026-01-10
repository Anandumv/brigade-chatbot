"""
Document processing pipeline for PDFs and Excel files.
Extracts text, chunks content, and prepares for embedding generation.
"""

import pdfplumber
import PyPDF2
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of document content with metadata."""
    content: str
    metadata: Dict[str, Any]
    chunk_index: int


class PDFProcessor:
    """Process PDF documents and extract structured content."""

    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        """
        Initialize PDF processor.

        Args:
            chunk_size: Target number of tokens per chunk (approx 3200 characters)
            overlap: Number of tokens to overlap between chunks
        """
        self.chunk_size = chunk_size * 4  # Approx 4 chars per token
        self.overlap = overlap * 4

    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from PDF with page numbers and structure.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of page dictionaries with content and metadata
        """
        pages = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()

                    if text and text.strip():
                        # Clean up text
                        text = self._clean_text(text)

                        pages.append({
                            "page_number": page_num,
                            "content": text,
                            "total_pages": len(pdf.pages)
                        })
                        logger.info(f"Extracted page {page_num}/{len(pdf.pages)} from {Path(pdf_path).name}")

        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            # Fallback to PyPDF2
            pages = self._extract_with_pypdf2(pdf_path)

        return pages

    def _extract_with_pypdf2(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Fallback extraction using PyPDF2."""
        pages = []
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages, start=1):
                    text = page.extract_text()

                    if text and text.strip():
                        text = self._clean_text(text)
                        pages.append({
                            "page_number": page_num,
                            "content": text,
                            "total_pages": total_pages
                        })
        except Exception as e:
            logger.error(f"PyPDF2 extraction also failed for {pdf_path}: {e}")

        return pages

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters that might cause issues
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', '', text)

        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        return text.strip()

    def chunk_document(
        self,
        pages: List[Dict[str, Any]],
        document_name: str,
        doc_type: str = "brochure",
        project_name: Optional[str] = None
    ) -> List[DocumentChunk]:
        """
        Chunk document pages into smaller segments with overlap.

        Args:
            pages: List of page dictionaries from extract_text_from_pdf
            document_name: Name of the document
            doc_type: Type of document (brochure, pricing, etc.)
            project_name: Name of the project

        Returns:
            List of DocumentChunk objects
        """
        chunks = []
        chunk_index = 0

        for page in pages:
            page_num = page["page_number"]
            content = page["content"]

            # If page content is smaller than chunk size, treat as single chunk
            if len(content) <= self.chunk_size:
                chunk = DocumentChunk(
                    content=content,
                    metadata={
                        "document": document_name,
                        "doc_type": doc_type,
                        "page": page_num,
                        "section": f"Page {page_num}",
                        "project": project_name,
                        "total_pages": page["total_pages"]
                    },
                    chunk_index=chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1
            else:
                # Split page into multiple chunks with overlap
                page_chunks = self._split_with_overlap(content, page_num, document_name, doc_type, project_name, page["total_pages"])
                for chunk in page_chunks:
                    chunk.chunk_index = chunk_index
                    chunks.append(chunk)
                    chunk_index += 1

        logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages of {document_name}")
        return chunks

    def _split_with_overlap(
        self,
        text: str,
        page_num: int,
        document_name: str,
        doc_type: str,
        project_name: Optional[str],
        total_pages: int
    ) -> List[DocumentChunk]:
        """Split long text into overlapping chunks."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Find a good breaking point (sentence boundary)
            if end < len(text):
                # Look for sentence endings near the chunk boundary
                search_start = max(start, end - 200)
                search_end = min(len(text), end + 200)
                sentence_ends = [m.end() for m in re.finditer(r'[.!?]\s+', text[search_start:search_end])]

                if sentence_ends:
                    # Use the closest sentence end
                    closest_end = min(sentence_ends, key=lambda x: abs(x - (end - search_start)))
                    end = search_start + closest_end

            chunk_text = text[start:end].strip()

            if chunk_text:
                # Determine section based on content analysis
                section = self._identify_section(chunk_text, page_num)

                chunk = DocumentChunk(
                    content=chunk_text,
                    metadata={
                        "document": document_name,
                        "doc_type": doc_type,
                        "page": page_num,
                        "section": section,
                        "project": project_name,
                        "total_pages": total_pages,
                        "chunk_within_page": len(chunks) + 1
                    },
                    chunk_index=0  # Will be set by caller
                )
                chunks.append(chunk)

            # Move start position with overlap
            start = end - self.overlap

        return chunks

    def _identify_section(self, text: str, page_num: int) -> str:
        """
        Identify the section of the document based on content keywords.

        Args:
            text: The chunk text
            page_num: The page number

        Returns:
            Section identifier
        """
        text_lower = text.lower()

        # Define section keywords
        section_keywords = {
            "Project Overview": ["overview", "about", "introduction", "project", "located"],
            "Sustainability Features": ["net zero", "sustainability", "carbon", "green", "eco", "environment"],
            "Amenities": ["amenities", "facilities", "clubhouse", "swimming pool", "gym", "play"],
            "Specifications": ["specifications", "flooring", "kitchen", "toilet", "doors", "windows"],
            "Floor Plans": ["floor plan", "unit plan", "bedroom", "toilet", "balcony", "carpet area"],
            "Location": ["location", "connectivity", "nearby", "distance", "map"],
            "Pricing": ["price", "cost", "payment", "emi"],
            "Legal": ["rera", "registration", "legal", "approval"]
        }

        # Check for section keywords
        for section, keywords in section_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return f"Page {page_num}: {section}"

        # Default section
        return f"Page {page_num}"


class ExcelProcessor:
    """Process Excel files for structured data."""

    def extract_projects_data(self, excel_path: str) -> List[Dict[str, Any]]:
        """
        Extract project data from Excel file.

        Args:
            excel_path: Path to Excel file

        Returns:
            List of project dictionaries
        """
        import pandas as pd

        try:
            df = pd.read_excel(excel_path)

            # Convert DataFrame to list of dictionaries
            projects = df.to_dict('records')

            logger.info(f"Extracted {len(projects)} projects from {Path(excel_path).name}")
            return projects
        except Exception as e:
            logger.error(f"Error extracting data from {excel_path}: {e}")
            return []


def process_brigade_citrine_brochure(pdf_path: str) -> List[DocumentChunk]:
    """
    Process Brigade Citrine brochure and return chunks.

    Args:
        pdf_path: Path to the Brigade Citrine PDF

    Returns:
        List of document chunks
    """
    processor = PDFProcessor(chunk_size=800, overlap=100)

    # Extract text from PDF
    pages = processor.extract_text_from_pdf(pdf_path)

    # Chunk the document
    chunks = processor.chunk_document(
        pages=pages,
        document_name="Brigade Citrine E-Brochure 01-1",
        doc_type="brochure",
        project_name="Brigade Citrine"
    )

    return chunks


def process_avalon_brochure(pdf_path: str) -> List[DocumentChunk]:
    """
    Process Avalon brochure and return chunks.

    Args:
        pdf_path: Path to the Avalon PDF

    Returns:
        List of document chunks
    """
    processor = PDFProcessor(chunk_size=800, overlap=100)

    # Extract text from PDF
    pages = processor.extract_text_from_pdf(pdf_path)

    # Chunk the document
    chunks = processor.chunk_document(
        pages=pages,
        document_name="E-Brochure - Avalon",
        doc_type="brochure",
        project_name="Brigade Avalon"
    )

    return chunks


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python process_documents.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    project_name = "Brigade Citrine" if "citrine" in pdf_path.lower() else "Brigade Avalon"

    processor = PDFProcessor()
    pages = processor.extract_text_from_pdf(pdf_path)
    chunks = processor.chunk_document(pages, Path(pdf_path).stem, "brochure", project_name)

    print(f"\nProcessed {pdf_path}")
    print(f"Total pages: {len(pages)}")
    print(f"Total chunks: {len(chunks)}")
    print(f"\nSample chunk:")
    print(f"Content: {chunks[0].content[:200]}...")
    print(f"Metadata: {chunks[0].metadata}")
