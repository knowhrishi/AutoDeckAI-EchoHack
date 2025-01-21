# =========================================
# STEP 1: Imports & Basic Setup
# =========================================
import os
import re
import requests
import streamlit as st

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

# openai_api_key = st.sidebar.text_input("Enter your OpenAI API key:", type="password")
openai_api_key = "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"

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


def generate_presentation(slides: list, author_name: str) -> str:
    """
    1) Loads 'autodeckai2.pptx' and removes all existing slides.
    2) Adds a Title slide, content slides, a References slide, and a final Thank You slide.
    3) Correctly formats lines as bullet points, ensures references are bullet-pointed, etc.
    """

    # -- Load your custom PPTX template
    prs = Presentation('autodeckai2.pptx')

    # -- Remove all existing slides from the template
    for i in range(len(prs.slides) - 1, -1, -1):
        remove_slide(prs, i)

    # == LAYOUT INDICES ==
    # Adjust these so they match the order in autodeckai2.pptx:
    TITLE_SLIDE_LAYOUT     = 0
    CONTENT_SLIDE_LAYOUT   = 1
    REFERENCES_SLIDE_LAYOUT= 2
    THANK_YOU_SLIDE_LAYOUT = 3

    # == A. TITLE SLIDE ==
    title_layout = prs.slide_layouts[TITLE_SLIDE_LAYOUT]
    title_slide  = prs.slides.add_slide(title_layout)
    title_placeholder = title_slide.shapes.title
    subtitle_placeholder = title_slide.placeholders[1]  # Usually the second placeholder is for subtitle

    title_placeholder.text = slides[0].get('title', 'Presentation Title')
    subtitle_placeholder.text = f"Author: {author_name}"

    # == B. MAIN CONTENT SLIDES ==
    # slides[1:-2] => excludes the first (title), second-last (references), last (thank you)
    main_slides = slides[1:-2]

    for slide_data in main_slides:
        layout = prs.slide_layouts[CONTENT_SLIDE_LAYOUT]
        slide = prs.slides.add_slide(layout)

        # Slide title
        title_ph = slide.shapes.title
        title_ph.text = slide_data.get('title', 'Untitled Slide')

        # Content placeholder
        content_ph = slide.placeholders[1]
        text_frame = content_ph.text_frame
        text_frame.clear()

        content_text = slide_data.get('content', 'No content provided.')
        lines = content_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue  # Skip blank lines
            paragraph = text_frame.add_paragraph()
            # If the line starts with '-', we'll treat it as a bullet
            if line.startswith('-'):
                paragraph.bullet = True
                paragraph.text = line.lstrip('-').strip()
            else:
                paragraph.text = line

            paragraph.font.size = Pt(18)
            paragraph.font.color.rgb = RGBColor(0, 0, 0)
            paragraph.alignment = PP_ALIGN.LEFT
            # paragraph.font.name = "Calibri"  # Uncomment if you want a specific font

    # == C. REFERENCES SLIDE ==
    ref_data = slides[-2]
    ref_layout = prs.slide_layouts[REFERENCES_SLIDE_LAYOUT]
    ref_slide = prs.slides.add_slide(ref_layout)

    # Title
    ref_title = ref_slide.shapes.title
    ref_title.text = ref_data.get('title', 'References')

    # Reference placeholder
    ref_content_ph = ref_slide.placeholders[1]
    ref_text_frame = ref_content_ph.text_frame
    ref_text_frame.clear()

    references_text = ref_data.get('content', 'No references available.')
    ref_lines = references_text.split('\n')

    # Format each reference line as a bullet
    for line in ref_lines:
        line = line.strip()
        if not line:
            continue
        p = ref_text_frame.add_paragraph()
        p.text = line
        p.bullet = True
        p.font.size = Pt(16)
        p.font.color.rgb = RGBColor(80, 80, 80)
        p.alignment = PP_ALIGN.LEFT
        # p.font.name = "Calibri"

    # == D. THANK YOU SLIDE ==
    thanks_data = slides[-1]
    thanks_layout = prs.slide_layouts[THANK_YOU_SLIDE_LAYOUT]
    thanks_slide = prs.slides.add_slide(thanks_layout)

    thanks_slide.shapes.title.text = thanks_data.get('title', 'Thank You')
    if len(thanks_slide.placeholders) > 1:
        thanks_subtitle = thanks_slide.placeholders[1]
        thanks_subtitle.text = thanks_data.get('content', 'We appreciate your attention!')

    # == SAVE ==
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


def create_chroma_vectorstore(text: str, openai_api_key: str, persist_dir: str = "chroma_storage"):
    """
    Splits text into chunks, embeds them with OpenAIEmbeddings,
    and creates or loads a local Chroma vector store.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    chunks = splitter.split_text(text)
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=openai_api_key)

    # If the directory already has an index, load it; otherwise create a new one
    # if os.path.exists(persist_dir) and os.listdir(persist_dir):
    #     vectorstore = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
    # else:
    vectorstore = Chroma.from_texts(texts=chunks, embedding=embeddings, persist_directory=persist_dir)
    # vectorstore.persist()
    return vectorstore

def generate_slides_with_retrieval(vectorstore, presentation_focus: str, num_slides: int, openai_api_key: str):
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
    prompt_text = (
        f"As a **{presentation_focus}**, create a slide presentation with **{num_slides}** total slides "
        "using the content provided. Your presentation must include:\n\n"
        "1. **Title Page** (Slide 1):\n"
        "   - Only the main title (paper or project name) and author name(s).\n\n"
        "2. **Main Slides** (Slides 2 through N-2):\n"
        "   - Each slide has:\n"
        "       - A clear, descriptive title (e.g., 'Methodology', 'Results', etc.).\n"
        "       - Bullet-pointed content that summarizes key points relevant for an ecological or scientific audience.\n"
        "   - Incorporate ecological or scientific details if available.\n\n"
        "3. **Conclusion** (Slide N-1):\n"
        "   - Summarize main findings or takeaways.\n"
        "   - Include any recommendations or final thoughts.\n\n"
        "4. **References** (Slide N):\n"
        "   - List relevant sources or citations extracted from the PDF if possible.\n"
        "   - Use a simple bullet format. If no references are found, you may list 'No references available.'\n\n"
        "5. **Thank You** (Final Slide, if it fits within the same slide or add one more):\n"
        "   - A brief closing message like 'Thank you for your attention!'\n\n"
        "Format your response with the exact structure:\n"
        "Slide 1 Title: [Title]\n"
        "Slide 1 Content: [Content]\n"
        "Slide 2 Title: [Title]\n"
        "Slide 2 Content: [Content]\n"
        "... up to Slide N.\n\n"
        "Remember:\n"
        "- The first slide (Slide 1) has only title and author.\n"
        "- The final slides must include Conclusion, References, and a Thank You message.\n"
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

            progress_bar.progress(70)
            status_placeholder.info("Generating slides via LLM retrieval...")

            llm_response = generate_slides_with_retrieval(vectorstore, presentation_focus, num_slides, openai_api_key)
            slides = parse_llm_response(llm_response)

            progress_bar.progress(90)
            status_placeholder.info("Creating PowerPoint presentation...")

            pptx_file = generate_presentation(slides, author_name)

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

