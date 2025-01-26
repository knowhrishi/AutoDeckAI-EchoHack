import os
import re
import time
import shutil
import requests
import pandas as pd
import fitz
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader

# --------------------------
# Core PDF Processing
# --------------------------

def download_pdf_from_url(url: str) -> str:
    """Downloads a PDF from a given URL and returns the local file path."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        file_path = "downloaded_document.pdf"
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path
    except Exception as e:
        raise RuntimeError(f"Failed to download PDF: {str(e)}")

def extract_content_from_pdf(file_path: str) -> str:
    """Loads a PDF and concatenates all page_content into a single text string."""
    try:
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        return "".join(doc.page_content for doc in documents)
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {str(e)}")

def preprocess_text_for_ecology(text: str) -> str:
    """Cleans ecological text content with enhanced pattern matching."""
    patterns = [
        r"\nPage \d+",
        r"\nTable \d+.*",
        r"\nFigure \d+.*",
        r"\nReferences\n.*",
        r"https?://\S+",
        r"\bDOI:\s*\S+",
        r"Received:\s*\d{4}-\d{2}-\d{2}",
        r"Accepted:\s*\d{4}-\d{2}-\d{2}"
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()

# --------------------------
# LLM Response Handling
# --------------------------

def parse_llm_response(response_content: str) -> List[Dict[str, str]]:
    """Improved LLM response parser with error resilience."""
    slides = []
    current_slide = None
    content_buffer = []
    
    if not response_content or not isinstance(response_content, str):
        return generate_default_slide_list()

    try:
        lines = [line.strip() for line in response_content.split('\n') if line.strip()]
        
        for line in lines:
            if line.startswith('Slide') and 'Title:' in line:
                if current_slide:
                    current_slide['content'] = '\n'.join(content_buffer).strip()
                    slides.append(current_slide)
                    content_buffer = []
                
                current_slide = {
                    'title': line.split('Title:', 1)[-1].strip(),
                    'content': ''
                }
            elif line.startswith('Slide') and 'Content:' in line:
                content_buffer.append(line.split('Content:', 1)[-1].strip())
            elif current_slide:
                content_buffer.append(line)

        if current_slide:
            current_slide['content'] = '\n'.join(content_buffer).strip()
            slides.append(current_slide)

    except Exception as e:
        print(f"Error parsing LLM response: {str(e)}")
        return generate_default_slide_list()

    return slides or generate_default_slide_list()

def generate_default_slide_list() -> List[Dict[str, str]]:
    """Generates a default list of slides for error cases."""
    return [
        {"title": "Document Overview", "content": "- Key document insights"},
        {"title": "Main Findings", "content": "- Critical discoveries\n- Significant patterns"},
        {"title": "References", "content": "- Key citations\n- Data sources"},
        {"title": "Thank You", "content": "Questions & Discussion"}
    ]

# --------------------------
# Slide Generation
# --------------------------

def generate_slides_with_retrieval(
    vectorstore: Any,
    presentation_focus: str,
    num_slides: int,
    extracted_elements: List[Dict[str, Any]],
    openai_api_key: str
) -> str:
    """Generates slides using retrieval-augmented generation."""
    try:
        retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 8})
        
        figures_info = "\nAvailable Visual Elements:\n" + "\n".join(
            f"- [{elem['type'].upper()} {elem['figure_number']}]: {elem['caption']}"
            for elem in extracted_elements
        )

        prompt_template = ChatPromptTemplate.from_template("""
        As a {audience}, create {num_slides} slides using this structure:
        1. Title Slide: [Title]
        2. Content Slides: 
           - Clear headings
           - Bullet points
           - Integrated {elements}
        3. Conclusion: Key takeaways
        4. References: Data sources
        
        Format:
        Slide 1 Title: [Title]
        Slide 1 Content: [Content]
        ...
        """)

        chain = (
            RetrievalQA.from_chain_type(
                llm=ChatOpenAI(
                    model_name="gpt-4o",
                    temperature=0.7,
                    max_tokens=2000,
                    openai_api_key=openai_api_key
                ),
                retriever=retriever,
                chain_type="stuff"
            )
            | StrOutputParser()
        )

        return chain.invoke({
            "audience": presentation_focus,
            "num_slides": num_slides,
            "elements": figures_info
        })

    except Exception as e:
        print(f"Slide generation error: {str(e)}")
        return generate_default_slides()

# --------------------------
# Presentation Assembly
# --------------------------

class PresentationGenerator:
    def __init__(self, template: str = "templates/scientific_template.pptx"):
        self.template = template
        self.client = OpenAI()
        
    def generate_from_slides(self, slides: List[Dict], metadata: Dict) -> str:
        """Creates PowerPoint from structured slide data with theme support."""
        prs = Presentation(self.template)
        self._apply_theme(prs, metadata.get("theme", {}))
        self._create_title_slide(prs, metadata)
        
        for slide_data in slides:
            self._add_content_slide(prs, slide_data)
            
        output_path = "EcoDeck_Presentation.pptx"
        prs.save(output_path)
        return output_path

    # ... (keep existing PresentationGenerator methods unchanged)

# --------------------------
# File Management
# --------------------------

def clean_static_directory():
    """Cleans working directories with validation."""
    try:
        for dir_name in ["static", "content"]:
            if os.path.exists(dir_name):
                shutil.rmtree(dir_name)
            os.makedirs(dir_name, exist_ok=True)
        print("Cleaned working directories")
    except Exception as e:
        print(f"Directory cleanup error: {str(e)}")

# --------------------------
# Validation & Utilities
# --------------------------

def validate_openai_key(api_key: str):
    """Validates OpenAI API key with quick check."""
    try:
        client = OpenAI(api_key=api_key)
        client.models.list(timeout=3)
    except Exception as e:
        raise ValueError(f"API key validation failed: {str(e)}")

def is_likely_table(text: str) -> bool:
    """Enhanced table detection with scientific data awareness."""
    indicators = [
        text.count("\t") > 3,
        bool(re.search(r"\b(mean|std|p-value|±|SE)\b", text, re.I)),
        len(re.findall(r"\d+\.\d+", text)) > 5,
        any(char in text for char in ["±", "×10", "†"]),
        bool(re.search(r"\d\s{2,}\d", text))
    ]
    return sum(indicators) >= 3

# --------------------------
# PDF Element Processing
# --------------------------

def extract_and_caption_pdf_elements(
    pdf_file_path: str,
    openai_api_key: str,
    output_dir: str = "./content/"
) -> list:
    """Enhanced PDF element extraction with error handling."""
    # ... (keep existing implementation but add try/except blocks)

# --------------------------
# Compatibility Functions
# --------------------------

# Maintain legacy function names for backwards compatibility
generate_presentation = PresentationGenerator().generate_from_slides
extract_and_caption_pdf_elements = extract_and_caption_pdf_elements