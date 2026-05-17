"""
Document Processing Utilities
Supports: PDF, TXT, DOCX, MD, CSV
"""

import os
import fitz  # PyMuPDF
from docx import Document
import pandas as pd
from typing import Tuple, List, Dict


class DocumentProcessor:
    """Process various document formats"""
    
    SUPPORTED_FORMATS = ['.pdf', '.txt', '.docx', '.md', '.csv']
    
    def process_file(self, file_path: str) -> Tuple[str, Dict]:
        """Process any supported document file"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"❌ Unsupported format: {ext}")
        
        print(f"📄 Processing {ext} file...")
        
        if ext == '.pdf':
            return self._process_pdf(file_path)
        elif ext in ['.txt', '.md']:
            return self._process_text(file_path)
        elif ext == '.docx':
            return self._process_docx(file_path)
        elif ext == '.csv':
            return self._process_csv(file_path)
    
    def _process_pdf(self, file_path: str) -> Tuple[str, Dict]:
        """Extract text from PDF"""
        doc = fitz.open(file_path)
        text = ""
        
        for page_num, page in enumerate(doc):
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page.get_text()
        
        metadata = {
            "source": os.path.basename(file_path),
            "total_pages": len(doc),
            "format": "pdf"
        }
        
        doc.close()
        print(f"✅ PDF: {metadata['total_pages']} pages extracted")
        return text, metadata
    
    def _process_docx(self, file_path: str) -> Tuple[str, Dict]:
        """Extract text from DOCX"""
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        
        metadata = {
            "source": os.path.basename(file_path),
            "total_paragraphs": len(paragraphs),
            "format": "docx"
        }
        
        print(f"✅ DOCX: {metadata['total_paragraphs']} paragraphs")
        return text, metadata
    
    def _process_text(self, file_path: str) -> Tuple[str, Dict]:
        """Extract text from TXT or MD file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        metadata = {
            "source": os.path.basename(file_path),
            "format": os.path.splitext(file_path)[1][1:],
            "char_count": len(text)
        }
        
        print(f"✅ Text: {metadata['char_count']} characters")
        return text, metadata
    
    def _process_csv(self, file_path: str) -> Tuple[str, Dict]:
        """Extract data from CSV"""
        df = pd.read_csv(file_path)
        text = df.to_string()
        
        metadata = {
            "source": os.path.basename(file_path),
            "format": "csv",
            "rows": len(df),
            "columns": list(df.columns)
        }
        
        print(f"✅ CSV: {metadata['rows']} rows")
        return text, metadata


class TextChunker:
    """Smart text chunking with overlap"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks"""
        if not text:
            return []
        
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += "\n\n" + para if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                if len(para) > self.chunk_size:
                    sentences = para.split('. ')
                    current_chunk = ""
                    for sent in sentences:
                        if len(current_chunk) + len(sent) <= self.chunk_size:
                            current_chunk += ". " + sent if current_chunk else sent
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sent
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        print(f"✅ Created {len(chunks)} chunks")
        return chunks


if __name__ == "__main__":
    print("✅ Document Utils module loaded successfully!")
    print(f"📋 Supported formats: {DocumentProcessor.SUPPORTED_FORMATS}")