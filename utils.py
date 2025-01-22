from pathlib import Path
from openai import OpenAI
# from markitdown import MarkItDown
import os
import re
import requests
import traceback
from typing import List, Dict, Any
from pptx import Presentation
from pptx.util import Inches, Pt
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def download_pdf_from_url(url: str) -> str:
    """Downloads a PDF from a given URL and returns the local file path."""
    response = requests.get(url)
    if response.status_code == 200:
        file_path = "downloaded_document.pdf"
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path
    return ""

def extract_content_from_pdf(file_path: str) -> str:
    """Loads a PDF and concatenates all page_content into a single text string."""
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    return "".join(doc.page_content for doc in documents)

def preprocess_text_for_ecology(text: str) -> str:
    """Removes headers, footers, or references to clean the text."""
    # cleaned_text = re.sub(r"\nReferences.*", "", text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\nPage \d+", "", text)
    return cleaned_text

def parse_llm_response(response_content: str) -> List[Dict[str, str]]:
    """Parses the LLM response into a list of slide dictionaries."""
    if not response_content or not isinstance(response_content, str):
        print("Invalid response content")
        return generate_default_slide_list()
        
    slides = []
    try:
        lines = [line.strip() for line in response_content.split('\n') if line.strip()]
        current_slide = None
        content_buffer = []
        
        for line in lines:
            if line == '---' or not line:
                continue
                
            line = line.replace('**', '')
            
            if 'Title:' in line and line.lower().startswith('slide'):
                if current_slide:
                    current_slide['content'] = '\n'.join(content_buffer).strip()
                    slides.append(current_slide)
                
                slide_title = line.split('Title:', 1)[1].strip()
                current_slide = {'title': slide_title}
                content_buffer = []
                
            elif 'Content:' in line and line.lower().startswith('slide'):
                content = line.split('Content:', 1)[1].strip()
                if content:
                    content_buffer.append(content)
            elif current_slide is not None:
                content_buffer.append(line)
        
        if current_slide:
            current_slide['content'] = '\n'.join(content_buffer).strip()
            slides.append(current_slide)
            
        return slides if slides else generate_default_slide_list()
        
    except Exception as e:
        print(f"Error parsing LLM response: {str(e)}")
        return generate_default_slide_list()

def generate_default_slide_list() -> List[Dict[str, str]]:
    """Generates a default list of slides."""
    return [
        {"title": "Document Overview", "content": "- Key points extracted from the document"},
        {"title": "Main Findings", "content": "- Important findings and insights\n- Key takeaways from the text"},
        {"title": "References", "content": "- Document sources and citations"},
        {"title": "Thank You", "content": "Thank you for your attention!"}
    ]

def clean_static_directory():
    """Clean the static directory before processing new files."""
    import shutil
    try:
        for dir_name in ["static", "content"]:
            if os.path.exists(dir_name):
                shutil.rmtree(dir_name)
            os.makedirs(dir_name)
        print("Successfully cleaned static and content directories")
    except Exception as e:
        print(f"Error cleaning directories: {str(e)}")

def generate_slides_with_retrieval(
    vectorstore: Any,
    presentation_focus: str,
    num_slides: int,
    extracted_elements: List[Dict[str, Any]],
    openai_api_key: str
) -> str:
    """Generates slides using retrieval-based approach."""
    try:
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10}
        )

        figures_info = "\nAvailable Figures and Tables:\n"
        for elem in extracted_elements:
            marker = f"[{elem['type'].upper()} {elem['figure_number']}]"
            figures_info += f"- {marker}: {elem['caption']}\n"

        prompt_text = create_slide_prompt(presentation_focus, num_slides, figures_info)

        chain = RetrievalQA.from_chain_type(
            llm=ChatOpenAI(
                openai_api_key=openai_api_key,
                model_name="gpt-4o",
                temperature=0.7,
                max_tokens=2000
            ),
            retriever=retriever,
            chain_type="stuff",
            return_source_documents=True
        )
        
        response = chain.invoke({"query": prompt_text})
        result = response.get('result', response.get('answer', str(response))) if isinstance(response, dict) else str(response)
        
        result = clean_llm_response(result)
        
        return result if "Slide 1 Title:" in result else generate_default_slides()
        
    except Exception as e:
        print(f"Error in slide generation: {str(e)}")
        return generate_default_slides()

def create_slide_prompt(presentation_focus: str, num_slides: int, figures_info: str) -> str:
    """Creates the prompt for slide generation."""
    return (
        f"As a **{presentation_focus}**, create a slide presentation with **{num_slides}** total slides "
        "using the content provided. You have access to the following figures and tables that you MUST incorporate:\n"
        f"{figures_info}\n"
        "Your presentation must include:\n\n"
        "1. **Title Page** (Slide 1):\n"
        "   - Only the main title (paper or project name) and author name(s).\n\n"
        "2. **Main Slides** (Slides 2 through N-2):\n"
        "   - Each slide has:\n"
        "       - A clear, descriptive title\n"
        "       - Bullet-pointed content that summarizes key points\n"
        "       - You MUST use the exact figure/table references as shown above\n"
        "       - Place each figure reference on its own line after related bullet points\n\n"
        "3. **Conclusion** (Slide N-1):\n"
        "   - Summarize main findings or takeaways\n"
        "   - Include any recommendations\n\n"
        "4. **References** (Slide N):\n"
        "   - List sources and include attributions for figures used\n\n"
        "5. **Thank You** (Final Slide):\n"
        "   - Brief closing message\n\n"
        "Format each slide EXACTLY as follows:\n"
        "Slide 1 Title: [Title]\n"
        "Slide 1 Content: [Content]\n"
        "... and so on.\n"
    )

def clean_llm_response(result: str) -> str:
    """Cleans up the LLM response."""
    result = result.strip()
    if result.startswith('Here\'s') or result.startswith('---'):
        first_slide_idx = result.find('Slide 1 Title:')
        if first_slide_idx != -1:
            result = result[first_slide_idx:]
    return result

def generate_default_slides() -> str:
    """Generates default slides when the main generation fails."""
    return """
    Slide 1 Title: Document Overview
    Slide 1 Content: - Key points extracted from the document
    
    Slide 2 Title: Main Findings
    Slide 2 Content: - Important findings and insights
    - Key takeaways from the text
    
    Slide 3 Title: References
    Slide 3 Content: - Document sources and citations
    
    Slide 4 Title: Thank You
    Slide 4 Content: Thank you for your attention!
    """

# PDF Element Processing Functions
def is_likely_table(text: str) -> bool:
    """Heuristics to guess if a block is tabular data."""
    indicators = [
        text.count("|") > 2,
        text.count("\t") > 2,
        text.count("  ") > 8,
        bool(re.search(r"Table \d+[:.]\s", text, re.IGNORECASE)),
        len(re.findall(r"\d+\s+\d+\s+\d+", text)) > 0,
        bool(re.search(r"(\w+\s+){3,}\n(\w+\s+){3,}", text)),
        any(word in text.lower() for word in ["total", "sum", "average", "mean", "std", "min", "max"]),
        text.count("%") > 2,
        len(re.findall(r"\d+\.\d+", text)) > 3
    ]
    return sum(indicators) >= 2

def is_valid_figure(base_image: dict, min_size: int = 10000) -> bool:
    """Determines if an image is likely to be a meaningful figure."""
    try:
        image_bytes = base_image["image"]
        if len(image_bytes) < min_size:
            return False
            
        width = base_image.get("width", 0)
        height = base_image.get("height", 0)
        
        if width > 0 and height > 0:
            if width < 100 or height < 100 or width > 3000 or height > 3000:
                return False
                
        return base_image["ext"].lower() in {"jpg", "jpeg", "png", "bmp"}
        
    except Exception as e:
        print(f"Error checking image validity: {str(e)}")
        return False

def get_surrounding_text(page: Any, rect: Any, buffer: int = 50) -> str:
    """Get text surrounding an image with a buffer zone."""
    import pymupdf as fitz
    try:
        x0 = max(0, rect.x0 - buffer)
        y0 = max(0, rect.y0 - buffer)
        x1 = min(page.rect.width, rect.x1 + buffer)
        y1 = min(page.rect.height, rect.y1 + buffer)
        
        clip_rect = fitz.Rect(x0, y0, x1, y1)
        return page.get_text("text", clip=clip_rect)
    except Exception as e:
        print(f"Error getting surrounding text: {str(e)}")
        return page.get_text()

# Presentation Generation Functions
def remove_slide(prs: Presentation, slide_index: int):
    """Removes a slide from the presentation by its index."""
    slide_id = prs.slides._sldIdLst[slide_index].rId
    prs.part.drop_rel(slide_id)
    del prs.slides._sldIdLst[slide_index]

def update_slide_content_with_figures(content: str, element_lookup: Dict[str, Any]) -> str:
    """Updates slide content with correct figure references."""
    updated_content = content
    number_to_elem = {
        elem['figure_number']: elem 
        for elem in element_lookup.values()
    }
    
    for num in range(1, len(number_to_elem) + 1):
        figure_pattern = f"[FIGURE {num}]"
        table_pattern = f"[TABLE {num}]"
        
        if figure_pattern in content or table_pattern in content:
            if num in number_to_elem:
                elem = number_to_elem[num]
                pattern = figure_pattern if elem['type'].lower() == 'figure' else table_pattern
                updated_content = updated_content.replace(
                    pattern,
                    f"{pattern} {elem['file_path']}"
                )
    
    return updated_content

def generate_presentation(slides: list, author_name: str, extracted_elements: list) -> str:
    """Creates a PowerPoint presentation with integrated figures and tables."""
    try:
        # Debug print of extracted elements
        print("\nAvailable elements for presentation:")
        for elem in extracted_elements:
            print(f"- {elem['type']} {elem['figure_number']}: {elem['static_path']}")

        # Create element lookup from extracted_elements
        element_lookup = {}
        for elem in extracted_elements:
            if elem['type'].lower() == 'figure':
                element_lookup[f"[FIGURE {elem['figure_number']}]"] = elem
            else:
                element_lookup[f"[TABLE {elem['figure_number']}]"] = elem

        # Load template
        prs = Presentation('autodeckai2.pptx')
        
        # Remove existing slides
        for i in range(len(prs.slides) - 1, -1, -1):
            remove_slide(prs, i)
        
        # Layout indices
        TITLE_SLIDE_LAYOUT = 0
        CONTENT_SLIDE_LAYOUT = 1
        REFERENCES_SLIDE_LAYOUT = 2
        THANK_YOU_SLIDE_LAYOUT = 3
        
        # Title Slide
        title_slide = prs.slides.add_slide(prs.slide_layouts[TITLE_SLIDE_LAYOUT])
        title = title_slide.shapes.title
        subtitle = title_slide.placeholders[1]
        title.text = slides[0].get('title', 'Presentation Title')
        subtitle.text = f"Author: {author_name}"
        
        # Content Slides
        main_slides = slides[1:-2] if len(slides) > 3 else slides[1:2]
        
        for slide_data in main_slides:
            slide = prs.slides.add_slide(prs.slide_layouts[CONTENT_SLIDE_LAYOUT])
            
            # Add title
            title = slide.shapes.title
            title.text = slide_data.get('title', 'Untitled Slide')
            
            # Process content
            content = slide.placeholders[1].text_frame
            content.clear()
            
            # First pass: Process text content
            text_content = []
            figures_to_add = []
            
            content_lines = slide_data.get('content', '').split('\n')
            for line in content_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check for figure/table references
                has_ref = False
                for ref, elem in element_lookup.items():
                    if ref in line:
                        has_ref = True
                        figures_to_add.append(elem)
                        line = line.replace(ref, '').strip()
                        print(f"Found reference {ref} in line, will add {elem['type']} {elem['figure_number']}")
                
                if line and not has_ref:
                    text_content.append(line)
            
            # Add text content
            for line in text_content:
                p = content.add_paragraph()
                if line.startswith('-') or line.startswith('*'):
                    p.bullet = True
                    p.text = line.lstrip('*- ').strip()
                else:
                    p.text = line
                p.font.size = Pt(18)
            
            # Add figures below text
            current_y = Inches(3)  # Start figures below text
            for elem in figures_to_add:
                try:
                    file_path = elem['static_path']
                    print(f"Adding {elem['type']} {elem['figure_number']} from {file_path}")
                    
                    if not os.path.exists(file_path):
                        print(f"File not found: {file_path}")
                        continue
                    
                    if elem['type'].lower() == 'figure':
                        # Add image
                        img_width = Inches(6)
                        img_left = Inches(1.5)
                        
                        picture = slide.shapes.add_picture(
                            file_path,
                            img_left,
                            current_y,
                            width=img_width
                        )
                        
                        # Add caption
                        caption_top = current_y + Inches(picture.height / 914400) + Inches(0.1)
                        caption_box = slide.shapes.add_textbox(
                            img_left,
                            caption_top,
                            img_width,
                            Inches(0.5)
                        )
                        caption_para = caption_box.text_frame.add_paragraph()
                        caption_para.text = f"Figure {elem['figure_number']}: {elem['caption']}"
                        caption_para.font.size = Pt(12)
                        caption_para.font.italic = True
                        
                        current_y = caption_top + Inches(0.7)
                        
                    else:  # Table
                        current_y = Inches(add_formatted_table_element(slide, elem, current_y/Inches(1)))
                        
                        
                    print(f"Successfully added {elem['type']} {elem['figure_number']}")
                    
                except Exception as e:
                    print(f"Error adding {elem['type']} {elem['figure_number']}: {str(e)}")
                    continue

        # Add References slide
        ref_slide = prs.slides.add_slide(prs.slide_layouts[REFERENCES_SLIDE_LAYOUT])
        ref_title = ref_slide.shapes.title
        ref_title.text = slides[-2].get('title', 'References')
        
        ref_content = ref_slide.placeholders[1]
        ref_frame = ref_content.text_frame
        ref_frame.clear()
        
        # Add references
        references_text = slides[-2].get('content', '')
        for line in references_text.split('\n'):
            if line.strip():
                p = ref_frame.add_paragraph()
                p.text = line.strip()
                p.bullet = True
                p.font.size = Pt(16)
        
        # Add Thank You slide
        thanks_slide = prs.slides.add_slide(prs.slide_layouts[THANK_YOU_SLIDE_LAYOUT])
        thanks_title = thanks_slide.shapes.title
        thanks_title.text = slides[-1].get('title', 'Thank You')
        
        if len(thanks_slide.placeholders) > 1:
            thanks_subtitle = thanks_slide.placeholders[1]
            thanks_subtitle.text = slides[-1].get('content', 'Thank you for your attention!')
        
        # Save presentation
        output_filename = "generated_presentation.pptx"
        prs.save(output_filename)
        print("Presentation saved successfully")
        return output_filename
        
    except Exception as e:
        print(f"Error generating presentation: {str(e)}")
        import traceback
        traceback.print_exc()
        return ""
    


def extract_and_caption_pdf_elements(
    pdf_file_path: str,
    openai_api_key: str,
    output_dir: str = "./content/"
) -> list:
    """
    1) Extract figure images and possible table blocks using PyMuPDF (fitz).
    2) Generate short LLM-based captions for each figure/table.
    3) Return a list of dictionaries, each containing:
       {
         "type": "figure" or "table",
         "file_path": ...,
         "static_path": ...,
         "caption": ...,
         "figure_number": ...
       }
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    all_results = []
    
    # Install PyMuPDF if missing
    try:
        import pymupdf as fitz
    except ImportError:
        print(ImportError)
        # print("Installing PyMuPDF...")
        # pip.main(['install', '--quiet', '--no-cache-dir', 'PyMuPDF==1.21.1'])
        # import fitz
    print(fitz.__version__)

    try:
        print(f"PyMuPDF version: {fitz.version}")
        # Try opening the PDF
        try:
            doc = fitz.Document(pdf_file_path)
            print("Opened PDF with fitz.Document")
        except Exception as e1:
            try:
                doc = fitz.open(pdf_file_path)
                print("Opened PDF with fitz.open")
            except Exception as e2:
                raise Exception(f"Could not open PDF: {str(e1)}, {str(e2)}")
        
        # We will use a single LLM instance for captions
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=openai_api_key
        )
        
        figure_counter = 1
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            print(f"Processing page {page_num + 1} of {len(doc)}")
            
            # Get page dimensions
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height
            
            # Extract images
            image_list = page.get_images(full=True)
            
            for img_index, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    
                    if not base_image:
                        continue
                        
                    # Validate image
                    if not is_valid_figure(base_image):
                        continue
                    
                    # Check image position
                    image_rects = page.get_image_rects(xref)
                    valid_image = False
                    surrounding_text = ""
                    
                    for img_rect in image_rects:
                        # Skip header/footer
                        if img_rect.y0 < page_height * 0.1 or img_rect.y1 > page_height * 0.9:
                            continue
                            
                        # Check relative size
                        img_area = (img_rect.x1 - img_rect.x0) * (img_rect.y1 - img_rect.y0)
                        page_area = page_width * page_height
                        if img_area < page_area * 0.05:  # Less than 5% of page
                            continue
                            
                        valid_image = True
                        surrounding_text = get_surrounding_text(page, img_rect)
                        break
                    
                    if not valid_image:
                        continue
                    
                    # Save image files
                    ext = base_image["ext"].lower()
                    if ext == "jpeg":
                        ext = "jpg"
                    
                    image_filename = f"figure_{page_num}_{img_index}.{ext}"
                    image_path = os.path.join(output_dir, image_filename)
                    static_path = os.path.join("static", image_filename)
                    
                    # Save as bytes
                    image_bytes = base_image["image"]
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)
                    with open(static_path, "wb") as f:
                        f.write(image_bytes)
                    
                    # Generate caption
                    caption_chain = (
                        ChatPromptTemplate.from_template(
                            "Provide a short 1-2 sentence description of this image context:\n{text}"
                        )
                        | llm
                        | StrOutputParser()
                    )
                    caption = caption_chain.invoke({"text": surrounding_text})
                    
                    result = {
                        "type": "figure",
                        "file_path": image_path,
                        "static_path": static_path,
                        "caption": caption,
                        "figure_number": figure_counter
                    }
                    figure_counter += 1
                    all_results.append(result)
                    print(f"Added figure {figure_counter-1}")
                    
                except Exception as e:
                    print(f"Error processing image {img_index} on page {page_num+1}: {str(e)}")
                    continue
            
            # Process tables
            text = page.get_text()
            text_blocks = text.split('\n\n')
            
            for block_index, block in enumerate(text_blocks):
                if is_likely_table(block):
                    try:
                        table_filename = f"table_{page_num}_{block_index}.txt"
                        table_path = os.path.join(output_dir, table_filename)
                        static_table_path = os.path.join("static", table_filename)
                        
                        with open(table_path, "w", encoding="utf-8") as f:
                            f.write(block)
                        with open(static_table_path, "w", encoding="utf-8") as f:
                            f.write(block)
                        
                        table_prompt = ChatPromptTemplate.from_template("""
                        Analyze this potential table content and provide a brief summary:
                        {content}
                        """)
                        table_chain = table_prompt | llm | StrOutputParser()
                        caption = table_chain.invoke({"content": block})
                        
                        if "not a table" not in caption.lower():
                            result = {
                                "type": "table",
                                "file_path": table_path,
                                "static_path": static_table_path,
                                "caption": caption,
                                "figure_number": figure_counter
                            }
                            figure_counter += 1
                            all_results.append(result)
                            print(f"Added table {figure_counter-1}")
                            
                    except Exception as e:
                        print(f"Error processing table: {str(e)}")
                        continue
        
        doc.close()
        print(f"Extraction complete. Found {len(all_results)} items.")
        return all_results
        
    except Exception as e:
        print(f"Error in PDF processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    
def format_table_content(content: str) -> list:
    """Convert table text content into structured rows."""
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    rows = []
    current_row = []
    
    for line in lines:
        # Split by common delimiters
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        elif '\t' in line:
            cells = [cell.strip() for cell in line.split('\t') if cell.strip()]
        else:
            # For text that might be cell content
            cells = [line]
            
        if cells:
            current_row.extend(cells)
            
        # Start new row if we have enough cells or special markers
        if len(current_row) > 0 and (len(current_row) >= 3 or line.endswith('.')):
            rows.append(current_row)
            current_row = []
            
    # Add any remaining content
    if current_row:
        rows.append(current_row)
        
    return rows

def add_table_to_slide(slide, content: str, left: float, top: float, width: float) -> float:
    """Add a formatted table to the slide and return the bottom position."""
    try:
        # Format the content into rows
        rows = format_table_content(content)
        if not rows:
            return top
            
        # Determine number of columns
        max_cols = max(len(row) for row in rows)
        
        # Create table
        table_height = Inches(0.4) * len(rows)  # Estimate height
        table = slide.shapes.add_table(
            len(rows), max_cols,
            Inches(left),
            Inches(top),
            Inches(width),
            table_height
        ).table
        
        # Format table
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                if j < max_cols:  # Ensure we don't exceed table columns
                    table.cell(i, j).text = cell.strip()
                    # Format text
                    paragraph = table.cell(i, j).text_frame.paragraphs[0]
                    paragraph.font.size = Pt(10)
                    paragraph.font.name = "Calibri"
                    
                    # First row formatting
                    if i == 0:
                        paragraph.font.bold = True
                        table.cell(i, j).fill.solid()
                        table.cell(i, j).fill.fore_color.rgb = RGBColor(240, 240, 240)
        
        # Auto-fit
        table.columns[0].width = Inches(width / max_cols)
        
        # Return the position below the table
        return top + (table_height / Inches(1)) + 0.2
        
    except Exception as e:
        print(f"Error adding table: {str(e)}")
        return top

def add_formatted_table_element(slide, elem, current_y):
    """Add a table element with proper formatting."""
    try:
        # Set dimensions
        table_width = 6  # inches
        table_left = 1.5  # inches
        
        # Read table content
        with open(elem['static_path'], 'r', encoding='utf-8') as f:
            table_content = f.read()
        
        # Add table
        new_y = add_table_to_slide(slide, table_content, table_left, current_y, table_width)
        
        # Add caption
        caption_box = slide.shapes.add_textbox(
            Inches(table_left),
            Inches(new_y),
            Inches(table_width),
            Inches(0.5)
        )
        caption_para = caption_box.text_frame.add_paragraph()
        caption_para.text = f"Table {elem['figure_number']}: {elem['caption']}"
        caption_para.font.size = Pt(12)
        caption_para.font.italic = True
        
        return new_y + 0.7  # Return position below caption
        
    except Exception as e:
        print(f"Error adding formatted table: {str(e)}")
        return current_y + 3  # Return estimated position in case of error