import re
import requests
import pdfplumber
import streamlit as st

from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage

from pptx import Presentation
from pptx.util import Inches
from markitdown import MarkItDown

from utils import prompts, slide_structures

# Set the title of the app
st.title("🌿 Eco-centric Slide Generator")
st.markdown(
    """
    Upload a research paper, or provide a DOI/URL to generate ecology-specific presentation slides.
    """
)

# Input for OpenAI API key
openai_api_key = st.sidebar.text_input("🔑 OpenAI API Key", type="password")

# User input for presentation focus
presentation_focus = st.selectbox(
    "Select the target audience or purpose of the presentation:", list(prompts.keys())
)

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


# Function to dynamically extract keywords using LLM
def extract_keywords_with_llm(text, openai_api_key):
    llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=0.2, model_name="gpt-4o")
    prompt = f"Extract the key ecological terms and concepts from the following text:\n{text[:1000]}...\nList them as concise keywords without numbering only commas."
    messages = [HumanMessage(content=prompt)]
    response = llm(messages)
    keywords = [kw.strip() for kw in response.content.split(",")]
    return keywords


# Preprocessing for ecological context
def preprocess_text_for_ecology(text):
    # Remove unwanted elements like headers/footers and references
    cleaned_text = re.sub(r"\nReferences.*", "", text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\nPage \d+", "", cleaned_text)

    # Detect ecological keywords
    detected_keywords = extract_keywords_with_llm(cleaned_text, openai_api_key)

    st.sidebar.write("🔍 Detected Keywords:", detected_keywords)
    return cleaned_text


# Function to generate slide content dynamically
def generate_slide_content(preprocessed_text, presentation_focus, openai_api_key):
    llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=0.7, model_name="gpt-4")
    prompt = (
        prompts[presentation_focus] + "\n\n" + preprocessed_text[:2000]
    )  # Limiting to the first 2000 characters
    messages = [HumanMessage(content=prompt)]
    response = llm(messages)
    return response.content


# Function to generate and save presentation
def generate_presentation(slide_structure, slide_content):
    prs = Presentation()
    slide_layout = prs.slide_layouts[1]  # Title and Content layout

    # Parse content into sections based on the predefined slide structure
    content_sections = slide_content.split("\n")  # Split by single newlines for better flexibility

    # Assign content to slides based on slide structure
    for i, title in enumerate(slide_structure):
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title.strip()

        # Use content if available, otherwise assign default message
        if i < len(content_sections) and content_sections[i].strip():
            content = content_sections[i].strip()
        else:
            content = "Content not available or insufficient data."

        # Add content to the slide
        try:
            slide.placeholders[1].text = content
        except IndexError:
            # If no content placeholder exists, add a textbox
            textbox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(5))
            textbox.text = content

    # Save the presentation
    prs.save("generated_presentation.pptx")
    return "generated_presentation.pptx"


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
            extracted_text = extract_text_from_pdf(file_path, pdf_extractors)
            preprocessed_text = preprocess_text_for_ecology(extracted_text)

            # Generate slide content dynamically
            slide_content = generate_slide_content(
                preprocessed_text, presentation_focus, openai_api_key
            )

            # Generate and save presentation
            pptx_file = generate_presentation(slide_structures[presentation_focus], slide_content)

            # Provide download link
            st.success("🎉 Slides generated successfully!")
            st.download_button(
                label="📥 Download Presentation",
                data=open(pptx_file, "rb").read(),
                file_name="EcoHack_Presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )

            # Optional: Display slide content in preview
            st.write("### Presentation Preview")
            content_sections = slide_content.split("\n")
            for title, content in zip(slide_structures[presentation_focus], content_sections):
                st.markdown(f"#### {title}")
                st.text(content.strip())

else:
    if not openai_api_key:
        st.warning("Please enter your OpenAI API key.")
    elif not (uploaded_file or doi_or_url):
        st.warning("Please upload a PDF or enter a DOI/URL.")
