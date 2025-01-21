import re
import requests
import pdfplumber
import streamlit as st

from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage

from pptx import Presentation
from pptx.util import Inches
from markitdown import MarkItDown

from PIL import Image
import os

# Set the title of the app
st.title("🌿 Eco-centric Slide Generator")
st.markdown(
    """
    Upload a research paper, or provide a DOI/URL to generate ecology-specific presentation slides.
    """
)

# Input for OpenAI API key
# openai_api_key = st.sidebar.text_input("🔑 OpenAI API Key", type="password")
openai_api_key = "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"

# User input for presentation focus
presentation_focus = st.selectbox(
    "Select the target audience or purpose of the presentation:",
    ["Researcher", "Practitioner", "Funding Body"]
)

num_slides = st.number_input("Enter the number of slides to generate (including title slide):", min_value=1, value=7)

# Options for input type
input_type = st.radio("Select Input Type:", ["Upload PDF", "Enter DOI/URL"])

uploaded_file = None
doi_or_url = None

# Handle input
if input_type == "Upload PDF":
    uploaded_file = st.file_uploader("📄 Upload a PDF document", type=["pdf"])
elif input_type == "Enter DOI/URL":
    doi_or_url = st.text_input("🔗 Enter DOI or URL:")


# Function to download PDF from URL
def download_pdf_from_url(url):
    response = requests.get(url)
    if response.status_code == 200:
        file_path = "downloaded_document.pdf"
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path
    else:
        st.error("Failed to download PDF. Check the URL.")
        return None


# Function to extract text from PDF using pdfplumber
def extract_text_from_pdf(file_path, extractor):
    if extractor == "markitdown":
        md = MarkItDown()
        result = md.convert(file_path)
        text = result.text_content
    else:  # pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text()
    return text

def extract_content_from_pdf(file_path):
    loader = PyMuPDFLoader(file_path, extract_images=True)
    documents = loader.load()
    text_content = ""
    images = []
    tables = []

    for doc in documents:
        text_content += doc.page_content
        if 'image' in doc.metadata:
            image_data = doc.metadata['image']
            image = Image.open(image_data)
            images.append(image)
        if 'table' in doc.metadata:
            tables.append(doc.metadata['table'])

    return text_content, images, tables

# Function to dynamically extract keywords using LLM
# def extract_keywords_with_llm(text, openai_api_key):
#     llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=0.2, model_name="gpt-4o")
#     prompt = f"Extract the key ecological terms and concepts from the following text:\n{text[:1000]}...\nList them as concise keywords without numbering only commas."
#     messages = [HumanMessage(content=prompt)]
#     response = llm(messages)
#     keywords = [kw.strip() for kw in response.content.split(",")]
#     return keywords


# Preprocessing for ecological context
def preprocess_text_for_ecology(text):
    # Remove unwanted elements like headers/footers and references
    cleaned_text = re.sub(r"\nReferences.*", "", text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\nPage \d+", "", cleaned_text)

    # Detect ecological keywords
    # detected_keywords = extract_keywords_with_llm(cleaned_text, openai_api_key)

    # st.sidebar.write("🔍 Detected Keywords:", detected_keywords)
    return cleaned_text




def parse_llm_response(response_content: str):
    """
    Parse the LLM response into a list of slides with title and content.
    """
    slides = []
    lines = response_content.strip().split('\n')
    current_slide = {}
    content_lines = []

    for line in lines:
        if line.startswith("Slide") and "Title:" in line:
            # Save the current slide if it exists
            if current_slide:
                current_slide['content'] = "\n".join(content_lines).strip()
                slides.append(current_slide)
                current_slide = {}
                content_lines = []
            # Extract title
            current_slide['title'] = line.split("Title:", 1)[1].strip()
        elif line.startswith("Slide") and "Content:" in line:
            content_lines.append(line.split("Content:", 1)[1].strip())
        elif line.startswith("-"):
            content_lines.append(line.strip())

    print(content_lines)
    # Add the last slide
    if current_slide:
        current_slide['content'] = "\n".join(content_lines).strip()
        slides.append(current_slide)

    # Ensure all slides have content
    for slide in slides:
        if not slide.get('content'):
            slide['content'] = "Content not available. Please verify the source data or LLM prompt."

    return slides


def generate_presentation(slides: list):
    """Creates a PPTX file from a list of slide dictionaries and saves it."""
    prs = Presentation()
    slide_layout = prs.slide_layouts[1]  # Title and Content layout

    for slide_info in slides:
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = slide_info.get('title', 'Untitled Slide')

        content = slide_info.get('content', 'No content provided.')
        try:
            slide.placeholders[1].text = content
        except IndexError:
            # Add a textbox if the layout doesn't have a content placeholder
            textbox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(5))
            textbox.text = content

    output_filename = "generated_presentation.pptx"
    prs.save(output_filename)
    return output_filename

# -------------- New: Vector DB + Retrieval Logic --------------

def create_vectorstore_from_text(text: str, openai_api_key: str, persist_directory: str = "chroma_storage"):
    """
    Creates a Chroma vector store from the text,
    splitting into chunks, embedding with OpenAIEmbeddings, and returning the store.
    """
    # Split text into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    chunks = text_splitter.split_text(text)

    # Initialize the OpenAI Embeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=openai_api_key)

    # Check if the persist directory exists and contains the necessary files
    if os.path.exists(persist_directory) and os.listdir(persist_directory):
        # Load the existing Chroma vector store
        vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )
        print("Loaded existing Chroma vector store from disk.")
    else:
        # Split text into manageable chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=500)
        chunks = text_splitter.split_text(text)

        # Create a new Chroma vector store
        vectorstore = Chroma.from_texts(
            texts=chunks,
            embedding=embeddings,
            persist_directory=persist_directory
        )
        # Persist the Chroma database to disk
        vectorstore.persist()
        print("Created and persisted a new Chroma vector store.")

    return vectorstore

def generate_slides_with_retrieval(vectorstore, presentation_focus: str, num_slides: int, openai_api_key: str):
    """
    1. Retrieves the most relevant chunks from the vector store (for demonstration, we'll retrieve many chunks).
    2. Sends them to the LLM with a carefully engineered prompt to produce the slides.
    """

    # 1) Construct a retrieval wrapper
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 8})

    # 2) Formulate the final 'question' or instruction
    # You can refine or expand the prompt to ensure we get well-structured slides
    prompt_text = (
        f"As a **{presentation_focus}**, create a presentation with **{num_slides} slides** "
        "from the retrieved ecological content below. "
        "Each slide must include:\n"
        "- A descriptive Title (e.g., Slide 1 Title: Introduction)\n"
        "- Bullet-pointed Content (e.g., Slide 1 Content: - Key finding 1)\n"
        "Focus on key ecological findings, data reliability, methods, or ROI as relevant.\n"
        "Format exactly as:\n"
        "Slide 1 Title: [Title]\nSlide 1 Content: [Content]\n...\n"
        "... up to Slide N.\n"
    )

    # 3) Build a QA chain with your chosen LLM
    chain = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(openai_api_key=openai_api_key, model_name="gpt-4o", temperature=0.7),
        retriever=retriever,
        chain_type="stuff"  # "stuff" merges all retrieved chunks into one prompt
    )

    # 4) Run the chain with the final instruction
    # The chain automatically appends the retrieved text from the vector DB
    # to your 'question' for context.
    slide_text = chain.run(prompt_text)

    return slide_text

pdf_extractors = st.sidebar.selectbox("Select the pdf Exractor", ["markitdown", "pdfplumber"])

# Main logic
if (uploaded_file or doi_or_url) and openai_api_key:
    with st.spinner("Processing the document..."):
        if uploaded_file:
            file_path = "uploaded_document.pdf"
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
        elif doi_or_url:
            file_path = download_pdf_from_url(doi_or_url)

        if file_path:
            # extracted_text = extract_text_from_pdf(file_path, pdf_extractors)
            extracted_text, images, tables = extract_content_from_pdf(file_path)
            preprocessed_text = preprocess_text_for_ecology(extracted_text)

            # 3) Create the vectorstore
            vectorstore = create_vectorstore_from_text(preprocessed_text, openai_api_key)
            st.write("Number of Chunks in Vector Store:", len(vectorstore))


            # 4) Generate slides using retrieval from the vector DB
            llm_response = generate_slides_with_retrieval(
                vectorstore=vectorstore,
                presentation_focus=presentation_focus,
                num_slides=num_slides,
                openai_api_key=openai_api_key
            )

            # 5) Parse slides from LLM response
            slides = parse_llm_response(llm_response)
            # Generate and save presentation
            pptx_file = generate_presentation(slides)

            # Provide download link
            st.success("🎉 Slides generated successfully!")
            st.download_button(
                label="📥 Download Presentation",
                data=open(pptx_file, "rb").read(),
                file_name="EcoHack_Presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )

            # Display the generated slides
            st.markdown("### 📄 Generated Slides:")
            for slide in slides:
                st.markdown(f"#### {slide['title']}")
                st.write(slide['content'])

else:
    if not openai_api_key:
        st.warning("Please enter your OpenAI API key.")
    elif not (uploaded_file or doi_or_url):
        st.warning("Please upload a PDF or enter a DOI/URL.")
