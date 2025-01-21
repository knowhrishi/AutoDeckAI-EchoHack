# =========================================
# STEP 1: Imports & Basic Setup
# =========================================
import os
import re
import requests
import streamlit as st
import chromadb

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

from unstructured.partition.pdf import partition_pdf
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import base64

from chromadb.config import Settings
from langchain_core.documents import Document

from PyPDF2 import PdfReader


def extract_and_caption_pdf_elements(
    pdf_file_path: str,
    openai_api_key: str,
    output_dir: str = "./content/"
) -> list:
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    all_results = []
    
    def is_likely_table(text: str) -> bool:
        """Enhanced table detection logic"""
        indicators = [
            #WORKAROUND TO FETCH TABLES
            # Basic table indicators
            text.count("|") > 2,
            text.count("\t") > 2,
            text.count("  ") > 8,
            
            # Common table headers
            bool(re.search(r"Table \d+[:.]\s", text, re.IGNORECASE)),
            
            # Number patterns (multiple numbers in sequence often indicate tables)
            len(re.findall(r"\d+\s+\d+\s+\d+", text)) > 0,
            
            # Column-like structure
            bool(re.search(r"(\w+\s+){3,}\n(\w+\s+){3,}", text)),
            
            # Common table words
            any(word in text.lower() for word in ["total", "sum", "average", "mean", "std", "min", "max"]),
            
            # Multiple percentage signs often indicate tables
            text.count("%") > 2,
            
            # Multiple decimal numbers often indicate tables
            len(re.findall(r"\d+\.\d+", text)) > 3
        ]
        return sum(indicators) >= 2  # If at least 2 indicators are present
    
    try:
        reader = PdfReader(pdf_file_path)
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=openai_api_key
        )
        
        # Process each page
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            page_text_blocks = text.split('\n\n')  # Split into logical blocks
            
            # Process each text block for tables
            for block_index, block in enumerate(page_text_blocks):
                if is_likely_table(block):
                    table_filename = f"table_{i}_{block_index}.txt"
                    table_path = os.path.join(output_dir, table_filename)
                    
                    with open(table_path, "w", encoding="utf-8") as f:
                        f.write(block)
                    
                    table_prompt = ChatPromptTemplate.from_template("""
                    Analyze this potential table content and provide a brief summary:
                    {content}
                    
                    If this appears to be tabular data, summarize what information it contains in 1-2 sentences.
                    If this is not actually a table, respond with "Not a table".
                    """)
                    
                    table_chain = table_prompt | llm | StrOutputParser()
                    
                    try:
                        caption = table_chain.invoke({"content": block})
                        if "not a table" not in caption.lower():
                            all_results.append({
                                "type": "table",
                                "file_path": table_path,
                                "caption": caption
                            })
                    except Exception as e:
                        print(f"Error analyzing table on page {i}: {str(e)}")
            
            # Look for figure references
            figure_references = re.findall(r"(?i)figure\s+\d+|fig\.\s*\d+", text)
            if figure_references:
                figure_filename = f"figure_context_{i}.txt"
                figure_path = os.path.join(output_dir, figure_filename)
                
                with open(figure_path, "w", encoding="utf-8") as f:
                    f.write(text)
                
                figure_prompt = ChatPromptTemplate.from_template("""
                This page contains references to figures: {figures}
                Based on the surrounding text, provide a brief description of what these figures might show:
                {content}
                Describe in 1-2 sentences what type of visual information might be presented.
                """)
                
                figure_chain = figure_prompt | llm | StrOutputParser()
                
                try:
                    caption = figure_chain.invoke({
                        "figures": ", ".join(figure_references),
                        "content": text
                    })
                    
                    all_results.append({
                        "type": "figure_reference",
                        "file_path": figure_path,
                        "caption": caption
                    })
                except Exception as e:
                    print(f"Error analyzing figures on page {i}: {str(e)}")
    
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return []
    
    return all_results




# =========================================
# STEP 2: Streamlit UI & Inputs
# =========================================
st.set_page_config(page_title="Eco-centric Slide Generator", layout="centered")
st.title("🌿 Eco-centric Slide Generator")
st.markdown(
    """
    This tool converts **ecological research PDFs** (or via a DOI/URL) into **professionally formatted** PowerPoint slides.
    """
)
author_name = st.sidebar.text_input("Enter the author's name:")

openai_api_key = st.sidebar.text_input("Enter your OpenAI API key:", type="password")

presentation_focus = st.sidebar.selectbox(
    "Select the target audience or purpose of the presentation:",
    ["Researcher", "Practitioner", "Funding Body"]
)
num_slides = st.sidebar.number_input("Enter the number of slides to generate (including title slide):", min_value=1, value=7)

input_type = st.sidebar.radio("Select Input Type:", ["Upload PDF", "Enter DOI/URL"])
uploaded_file = None
doi_or_url = None

if input_type == "Upload PDF":
    uploaded_file = st.sidebar.file_uploader("📄 Upload a PDF document", type=["pdf"])
elif input_type == "Enter DOI/URL":
    doi_or_url = st.sidebar.text_input("🔗 Enter DOI or URL:")


# =========================================
# STEP 3: Utility Functions
# =========================================
def download_pdf_from_url(url: str) -> str:
    """Downloads a PDF from a given URL and returns the local file path."""
    response = requests.get(url)
    if response.status_code == 200:
        file_path = "downloaded_document.pdf"
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path
    else:
        st.error("Failed to download PDF. Check the URL.")
        return ""

def extract_content_from_pdf(file_path: str) -> str:
    """
    Loads a PDF using PyPDFLoader (or PyMuPDFLoader) and
    concatenates all page_content into a single text string.
    """
    loader = PyPDFLoader(file_path)  # Or PyMuPDFLoader(file_path)
    documents = loader.load()
    combined_text = ""
    for doc in documents:
        combined_text += doc.page_content
    return combined_text

def preprocess_text_for_ecology(text: str) -> str:
    """
    Removes headers, footers, or references to
    clean the text for ecological summarization.
    """
    cleaned_text = re.sub(r"\nReferences.*", "", text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\nPage \d+", "", cleaned_text)
    return cleaned_text

def parse_llm_response(response_content: str):
    """
    Parses the LLM response into a list of slide dicts: [{title:..., content:...}, ...].
    Expects lines like:
      Slide 1 Title: ...
      Slide 1 Content: ...
    """
    slides = []
    lines = response_content.strip().split('\n')
    current_slide = {}
    content_buffer = []

    for line in lines:
        if line.startswith("Slide") and "Title:" in line:
            # If we already have a slide, finalize it
            if current_slide:
                current_slide['content'] = "\n".join(content_buffer).strip()
                slides.append(current_slide)
            current_slide = {'title': line.split("Title:", 1)[1].strip()}
            content_buffer = []
        elif line.startswith("Slide") and "Content:" in line:
            content_buffer.append(line.split("Content:", 1)[1].strip())
        elif line.startswith("-"):
            content_buffer.append(line.strip())

    # Add last slide if present
    if current_slide:
        current_slide['content'] = "\n".join(content_buffer).strip()
        slides.append(current_slide)

    # Ensure no slide is empty
    for slide in slides:
        if not slide.get('content'):
            slide['content'] = "Content not available."

    return slides

def remove_slide(prs, slide_index):
    """
    Removes a slide from the presentation by its index.
    """
    slide_id = prs.slides._sldIdLst[slide_index].rId
    prs.part.drop_rel(slide_id)
    del prs.slides._sldIdLst[slide_index]


def generate_presentation(slides: list, author_name: str, extracted_elements: list) -> str:
    """
    Creates a PowerPoint presentation with integrated figures and tables using efficient lookup.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    
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
    
    # Create element lookup for efficient reference matching
    element_lookup = {elem['file_path']: elem for elem in extracted_elements}
    
    # == A. Title Slide ==
    title_slide = prs.slides.add_slide(prs.slide_layouts[TITLE_SLIDE_LAYOUT])
    title_placeholder = title_slide.shapes.title
    subtitle_placeholder = title_slide.placeholders[1]
    
    title_placeholder.text = slides[0].get('title', 'Presentation Title')
    subtitle_placeholder.text = f"Author: {author_name}"
    
    # == B. Main Content Slides ==
    main_slides = slides[1:-2]
    
    for slide_data in main_slides:
        slide = prs.slides.add_slide(prs.slide_layouts[CONTENT_SLIDE_LAYOUT])
        
        # Add title
        title_shape = slide.shapes.title
        title_shape.text = slide_data.get('title', 'Untitled Slide')
        
        # Content placeholder
        content_shape = slide.placeholders[1]
        text_frame = content_shape.text_frame
        text_frame.clear()
        
        # Process content and look for figure/table references
        content_text = slide_data.get('content', '')
        lines = content_text.split('\n')
        
        # Track layout position
        current_y = Inches(2)
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for any referenced elements using lookup
            referenced_path = None
            for path in element_lookup.keys():
                if path in line:
                    referenced_path = path
                    break
            
            if referenced_path:
                # Get the element from lookup
                referenced_element = element_lookup[referenced_path]
                
                # Add the text without the file path
                clean_line = line.replace(referenced_path, '').strip()
                if clean_line:
                    p = text_frame.add_paragraph()
                    p.text = clean_line
                    if line.startswith('-'):
                        p.bullet = True
                    p.font.size = Pt(18)
                
                try:
                    # Add the figure/table
                    if referenced_element['type'] in ['figure_reference', 'table']:
                        img_width = Inches(6)
                        img_left = Inches(1.5)
                        
                        # Add figure
                        slide.shapes.add_picture(
                            referenced_path,  # Use the path from lookup
                            img_left,
                            current_y,
                            width=img_width
                        )
                        
                        # Add caption
                        caption_left = img_left
                        caption_top = current_y + Inches(3)
                        caption_width = img_width
                        caption_height = Inches(0.5)
                        
                        caption_box = slide.shapes.add_textbox(
                            caption_left, caption_top,
                            caption_width, caption_height
                        )
                        caption_frame = caption_box.text_frame
                        caption_para = caption_frame.add_paragraph()
                        caption_para.text = referenced_element['caption']
                        caption_para.font.size = Pt(12)
                        caption_para.font.italic = True
                        
                        current_y = caption_top + Inches(0.7)
                        
                except Exception as e:
                    print(f"Error adding element {referenced_path}: {str(e)}")
            else:
                # Regular text line
                p = text_frame.add_paragraph()
                if line.startswith('-'):
                    p.bullet = True
                    p.text = line.lstrip('-').strip()
                else:
                    p.text = line
                
                p.font.size = Pt(18)
                p.font.color.rgb = RGBColor(0, 0, 0)
                p.alignment = PP_ALIGN.LEFT
    
    # == C. References Slide ==
    ref_slide = prs.slides.add_slide(prs.slide_layouts[REFERENCES_SLIDE_LAYOUT])
    ref_title = ref_slide.shapes.title
    ref_title.text = slides[-2].get('title', 'References')
    
    ref_content = ref_slide.placeholders[1]
    ref_frame = ref_content.text_frame
    ref_frame.clear()
    
    references_text = slides[-2].get('content', 'No references available.')
    ref_lines = references_text.split('\n')
    
    # Add references
    for line in ref_lines:
        line = line.strip()
        if not line:
            continue
        p = ref_frame.add_paragraph()
        p.text = line
        p.bullet = True
        p.font.size = Pt(16)
        p.font.color.rgb = RGBColor(80, 80, 80)
        p.alignment = PP_ALIGN.LEFT
    
    # Add figure/table attributions using lookup
    if element_lookup:
        p = ref_frame.add_paragraph()
        p.text = "Figure and Table Sources:"
        p.font.bold = True
        p.font.size = Pt(16)
        
        for path, elem in element_lookup.items():
            p = ref_frame.add_paragraph()
            p.text = f"{elem['type'].title()}: {elem['caption']}"
            p.bullet = True
            p.font.size = Pt(14)
    
    # == D. Thank You Slide ==
    thanks_slide = prs.slides.add_slide(prs.slide_layouts[THANK_YOU_SLIDE_LAYOUT])
    thanks_title = thanks_slide.shapes.title
    thanks_title.text = slides[-1].get('title', 'Thank You')
    
    if len(thanks_slide.placeholders) > 1:
        thanks_subtitle = thanks_slide.placeholders[1]
        thanks_subtitle.text = slides[-1].get('content', 'We appreciate your attention!')
    
    # Save the presentation
    output_filename = "generated_presentation.pptx"
    prs.save(output_filename)
    return output_filename

# ================================
# Example usage in Streamlit code
# ================================
# st.title("Eco-centric Slide Deck Generator")
st.sidebar.write("---")
# For demonstration:
st.sidebar.markdown("🛠️ Only for testing purpose")
if st.sidebar.button("Create Demo Slides"):
    # add markdown saying that it is for testing purposes
    sample_slides = [
        {"title": "Introduction", "content": ""},
        {"title": "Overview", "content": "- Purpose\n- Scope\n- Approach"},
        {"title": "Results", "content": "- Observed data\n- Statistical insights\n\n- Graphical analysis"},
        {"title": "References", "content": "- Smith et al. 2020\n- Doe and Roe, 2019"},
        {"title": "Thank You", "content": "Feel free to reach out with any questions!"}
    ]
    file_path = generate_presentation(sample_slides, author_name="Jane Doe")
    st.success("Presentation generated!")
    with open(file_path, "rb") as f:
        st.download_button("Download PPTX", f.read(), "generated_presentation.pptx")


def create_chroma_vectorstore(text: str, openai_api_key: str, persist_dir: str = "./chroma_db"):
    """
    Creates a vector store using ChromaDB with proper tenant handling and persistence.
    
    Args:
        text (str): The input text to be processed
        openai_api_key (str): OpenAI API key for embeddings
        persist_dir (str): Directory to persist the vector store
    """
    import os
    import shutil
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma
    import chromadb
    from chromadb.config import Settings
    
    collection_name = "eco_slides"
    
    # Initialize embeddings
    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002", 
        openai_api_key=openai_api_key
    )
    
    # Text splitting
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    chunks = splitter.split_text(text)
    
    try:
        # Clean up existing directory if it exists
        if os.path.exists(persist_dir):
            shutil.rmtree(persist_dir)
        
        # Create fresh persistence directory
        os.makedirs(persist_dir, exist_ok=True)
        
        # Initialize ChromaDB client with explicit settings
        settings = Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_dir,
            anonymized_telemetry=False
        )
        
        # Create new vector store
        vectorstore = Chroma.from_texts(
            texts=chunks,
            embedding=embeddings,
            persist_directory=persist_dir,
            client_settings=settings,
            collection_name=collection_name
        )
        
        # Ensure persistence
        try:
            vectorstore.persist()
        except Exception as persist_error:
            print(f"Warning: Persistence error: {str(persist_error)}")
        
        return vectorstore
        
    except Exception as e:
        print(f"Error in ChromaDB setup: {str(e)}")
        
        # If everything fails, use in-memory FAISS as fallback
        from langchain_community.vectorstores import FAISS
        print("Falling back to in-memory FAISS vectorstore")
        return FAISS.from_texts(
            texts=chunks,
            embedding=embeddings
        )

def generate_slides_with_retrieval(vectorstore, presentation_focus: str, num_slides: int, extracted_elements: list, openai_api_key: str):
    """
    Uses a RetrievalQA chain (with 'stuff' approach) to combine retrieved content
    into a final LLM prompt that yields slides in structured format.
    """
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 8})
    # prompt_text = (
    #     f"As a **{presentation_focus}**, create a presentation with **{num_slides} slides** "
    #     "using the following content. Each slide has:\n"
    #     "- A descriptive Title (Slide X Title: ...)\n"
    #     "- Bullet-pointed content (Slide X Content: ...)\n"
    #     "Include ecological or relevant scientific details if available.\n"
    #     "Format:\n"
    #     "Slide 1 Title: [Title]\n"
    #     "Slide 1 Content: [Content]\n"
    #     "... up to Slide N.\n"
    # )
    figures_info = "\nAvailable Figures and Tables:\n"
    for elem in extracted_elements:
        figures_info += f"- {elem['type'].title()}: {elem['caption']}\n"
    
    prompt_text = (
        f"As a **{presentation_focus}**, create a slide presentation with **{num_slides}** total slides "
        "using the content provided. You have access to the following figures and tables that you can incorporate:\n"
        f"{figures_info}\n"
        "Your presentation must include:\n\n"
        "1. **Title Page** (Slide 1):\n"
        "   - Only the main title (paper or project name) and author name(s).\n\n"
        "2. **Main Slides** (Slides 2 through N-2):\n"
        "   - Each slide has:\n"
        "       - A clear, descriptive title (e.g., 'Methodology', 'Results', etc.)\n"
        "       - Bullet-pointed content that summarizes key points\n"
        "       - Where appropriate, include [FIGURE X] or [TABLE X] markers to indicate where specific figures "
        "         or tables should be placed (use the exact file paths from the available figures)\n"
        "   - When referencing figures or tables, integrate them naturally into the content\n"
        "   - Ensure proper attribution for any included figures\n\n"
        "3. **Conclusion** (Slide N-1):\n"
        "   - Summarize main findings or takeaways\n"
        "   - Include any recommendations\n\n"
        "4. **References** (Slide N):\n"
        "   - List sources and include attributions for any used figures\n\n"
        "5. **Thank You** (Final Slide):\n"
        "   - Brief closing message\n\n"
        "Format each slide as:\n"
        "Slide X Title: [Title]\n"
        "Slide X Content: [Content]\n"
        "[Optional] Slide X Figure: [full file path from available figures]\n\n"
        "Important:\n"
        "- When including figures, specify the exact file path\n"
        "- Place figure references where they naturally fit in the content\n"
        "- Include proper attribution in the references slide\n"
    )


    chain = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(openai_api_key=openai_api_key, model_name="gpt-4o", temperature=0.7),
        retriever=retriever,
        chain_type="stuff"
    )
    return chain.run(prompt_text)


# =========================================
# STEP 4: Main Logic
# =========================================

st.write("---")
generate_slides_clicked = st.button("Generate Slide Deck")
if generate_slides_clicked:
    if not openai_api_key:
        st.error("Please provide a valid OpenAI API key.")
    elif not (uploaded_file or doi_or_url):
        st.error("Please upload a PDF or provide a DOI/URL.")
    else:

        status_placeholder = st.empty()

        progress_bar = st.progress(0)
        status_placeholder.info("Processing your input...")

        # A. Download or store PDF
        file_path = ""
        if uploaded_file:
            file_path = "uploaded_document.pdf"
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
        elif doi_or_url:
            file_path = download_pdf_from_url(doi_or_url)

        if file_path:
            progress_bar.progress(25)
            status_placeholder.info("Extracting and cleaning text...")

            extracted_text = extract_content_from_pdf(file_path)
            cleaned_text = preprocess_text_for_ecology(extracted_text)

            progress_bar.progress(50)
            status_placeholder.info("Creating/Loading vector store...")


            vectorstore = create_chroma_vectorstore(cleaned_text, openai_api_key)

                # 3) NEW: Extract & caption PDF images/tables
            extracted_elements = extract_and_caption_pdf_elements(
                pdf_file_path=file_path,
                openai_api_key=openai_api_key,
                output_dir="content/"
            )

            # 4) (Optional) Print or log the extracted elements
            st.write("Extracted Tables/Images:")
            for elem in extracted_elements:
                st.write(f"Type: {elem['type']}, File: {elem['file_path']}, Caption: {elem['caption']}")


            progress_bar.progress(70)
            status_placeholder.info("Generating slides via LLM retrieval...")

            llm_response = generate_slides_with_retrieval(vectorstore, presentation_focus, num_slides, extracted_elements, openai_api_key)
            slides = parse_llm_response(llm_response)

            progress_bar.progress(90)
            status_placeholder.info("Creating PowerPoint presentation...")

            pptx_file = generate_presentation(slides, author_name, extracted_elements)

            progress_bar.progress(100)
            st.success("🎉 Slides generated successfully!")
            st.download_button(
                label="📥 Download Presentation",
                data=open(pptx_file, "rb").read(),
                file_name="EcoHack_Presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

            # Preview
            st.markdown("### 📄 Generated Slides Preview:")
            for slide in slides:
                st.markdown(f"**{slide['title']}**")
                st.write(slide['content'])
        else:
            st.warning("Unable to process the file. Please verify your input.")
else:
    st.info("Configure your inputs, then click 'Generate Slide Deck' to proceed.")

