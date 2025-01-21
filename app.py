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
from pptx.util import Inches


# =========================================
# STEP 2: Streamlit UI & Inputs
# =========================================
st.title("🌿 Eco-centric Slide Generator")
st.markdown("Upload a research paper, or provide a DOI/URL to generate ecology-specific presentation slides.")

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
    uploaded_file = st.file_uploader("📄 Upload a PDF document", type=["pdf"])
elif input_type == "Enter DOI/URL":
    doi_or_url = st.text_input("🔗 Enter DOI or URL:")


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

def generate_presentation(slides: list):
    """
    Creates a PowerPoint file from the list of slides (dicts),
    each with 'title' and 'content', then returns the file path.
    """
    prs = Presentation()
    slide_layout = prs.slide_layouts[1]

    for slide_data in slides:
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = slide_data.get('title', 'Untitled Slide')
        content = slide_data.get('content', 'No content provided.')

        try:
            slide.placeholders[1].text = content
        except IndexError:
            textbox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(5))
            textbox.text = content

    output_filename = "generated_presentation.pptx"
    prs.save(output_filename)
    return output_filename

def create_chroma_vectorstore(text: str, openai_api_key: str, persist_dir: str = "chroma_storage"):
    """
    Splits text into chunks, embeds them with OpenAIEmbeddings,
    and creates or loads a local Chroma vector store.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    chunks = splitter.split_text(text)
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=openai_api_key)

    # If the directory already has an index, load it; otherwise create a new one
    if os.path.exists(persist_dir) and os.listdir(persist_dir):
        vectorstore = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
    else:
        vectorstore = Chroma.from_texts(texts=chunks, embedding=embeddings, persist_directory=persist_dir)
        vectorstore.persist()
    return vectorstore

def generate_slides_with_retrieval(vectorstore, presentation_focus: str, num_slides: int, openai_api_key: str):
    """
    Uses a RetrievalQA chain (with 'stuff' approach) to combine retrieved content
    into a final LLM prompt that yields slides in structured format.
    """
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 8})
    prompt_text = (
        f"As a **{presentation_focus}**, create a presentation with **{num_slides} slides** "
        "using the following content. Each slide has:\n"
        "- A descriptive Title (Slide X Title: ...)\n"
        "- Bullet-pointed content (Slide X Content: ...)\n"
        "Include ecological or relevant scientific details if available.\n"
        "Format:\n"
        "Slide 1 Title: [Title]\n"
        "Slide 1 Content: [Content]\n"
        "... up to Slide N.\n"
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
if (uploaded_file or doi_or_url) and openai_api_key:
    with st.spinner("Processing your document..."):
        # 4A. Obtain PDF
        if uploaded_file:
            file_path = "uploaded_document.pdf"
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
        elif doi_or_url:
            file_path = download_pdf_from_url(doi_or_url)

        # 4B. Extract & Preprocess Text
        if file_path:
            extracted_text = extract_content_from_pdf(file_path)
            cleaned_text = preprocess_text_for_ecology(extracted_text)

            # 4C. Create/Load Chroma Vector Store
            vectorstore = create_chroma_vectorstore(cleaned_text, openai_api_key)

            # 4D. Generate Slides
            llm_response = generate_slides_with_retrieval(vectorstore, presentation_focus, num_slides, openai_api_key)
            slides = parse_llm_response(llm_response)
            pptx_file = generate_presentation(slides)

            # 4E. Download & Preview
            st.success("🎉 Slides generated successfully!")
            st.download_button(
                label="📥 Download Presentation",
                data=open(pptx_file, "rb").read(),
                file_name="EcoHack_Presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

            st.markdown("### 📄 Generated Slides:")
            for slide in slides:
                st.markdown(f"#### {slide['title']}")
                st.write(slide['content'])

else:
    if not openai_api_key:
        st.warning("Please enter your OpenAI API key.")
    elif not (uploaded_file or doi_or_url):
        st.warning("Please upload a PDF or enter a DOI/URL.")
