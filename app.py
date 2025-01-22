# =========================================
# STEP 1: Imports & Basic Setup
# =========================================
import os
import streamlit as st

from utils import (
    download_pdf_from_url,
    extract_content_from_pdf,
    preprocess_text_for_ecology,
    parse_llm_response,
    clean_static_directory,
    generate_slides_with_retrieval,
    generate_presentation,
    extract_and_caption_pdf_elements,
)
from PyPDF2 import PdfReader
from faiss_vector_store import create_vectorstore


st.set_page_config(page_title="AutoDeckAI Eco-centric Slide Generator", layout="wide")
# st.title("")
st.title("AutoDeckAI: 🌿 Eco-centric Slide Generator")
st.markdown(
    """
    This tool helps **ecologist** to convert their idea into a **professionally formatted** PowerPoint slides.
    """
)

with st.sidebar:
    with st.expander("🔑 OpenAI API key", expanded=False):
        openai_api_key = st.text_input("Enter your OpenAI API key:", type="password")

    with st.expander("🛠️ Configuration", expanded=True):
        author_name = st.text_input("Enter the author's name:")

        presentation_focus = st.selectbox(
            "Select the target audience or purpose of the presentation:",
            ["Researcher", "Practitioner", "Funding Body"],
        )
        num_slides = st.number_input(
            "Enter the number of slides to generate (including title slide):", min_value=1, value=7
        )


# Create two columns
abstract, suplementary = st.columns([0.6, 0.4])

# Add widgets to the first column
with abstract:
    st.header("💭 Abstract")
    abstract = st.text_area("Enter the proposed abstract here:", height=200)


# Add widgets to the second column
with suplementary:
    st.header("⚡ Supplementaries")
    # File uploader for multiple files
    uploaded_files = st.file_uploader(
        "📚 Choose pictures or PDFs/Docs to upload:",
        # type=["pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "ppt", "pptx"],
        accept_multiple_files=True,
    )


uploaded_file = None
doi_or_url = None

# Create two columns
draft, type_ = st.columns([0.79, 0.21])
with type_:
    input_type = st.radio("Select Input Type:", ["Upload PDF", "Enter DOI/URL"])
with draft:
    if input_type == "Upload PDF":
        uploaded_file = st.file_uploader(
            "📄 Upload a draft version of your paper:", type=["pdf", "doc", "docx"]
        )
    elif input_type == "Enter DOI/URL":
        doi_or_url = st.text_input("🔗 Enter DOI or URL:")


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
            # Clean static directory before processing
            clean_static_directory()
            extracted_text = extract_content_from_pdf(file_path)
            cleaned_text = preprocess_text_for_ecology(extracted_text)

            progress_bar.progress(50)
            status_placeholder.info("Creating/Loading vector store...")

            vectorstore = create_vectorstore(cleaned_text, openai_api_key)

            # 3) NEW: Extract & caption PDF images/tables
            extracted_elements = extract_and_caption_pdf_elements(
                pdf_file_path=file_path, openai_api_key=openai_api_key, output_dir="content/"
            )

            # After extracting elements
            print(f"Extracted elements: {len(extracted_elements)}")
            for elem in extracted_elements:
                print(f"- {elem['type']} {elem['figure_number']}: {elem['caption'][:50]}...")

            progress_bar.progress(70)
            status_placeholder.info("Generating slides via LLM retrieval...")

            llm_response = generate_slides_with_retrieval(
                vectorstore, presentation_focus, num_slides, extracted_elements, openai_api_key
            )
            slides = parse_llm_response(llm_response)

            progress_bar.progress(90)
            status_placeholder.info("Creating PowerPoint presentation...")
            for elem in extracted_elements:
                if os.path.exists(elem["static_path"]):
                    print(f"File exists: {elem['static_path']}")
                else:
                    print(f"File missing: {elem['static_path']}")
            pptx_file = generate_presentation(slides, author_name, extracted_elements)

            progress_bar.progress(100)
            status_placeholder.success("🎉 Slides generated successfully!")
            st.download_button(
                label="📥 Download Presentation",
                data=open(pptx_file, "rb").read(),
                file_name="EcoHack_Presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )

            # Preview
            st.markdown("### 📄 Generated Slides Preview:")
            for slide in slides:
                st.markdown(f"**{slide['title']}**")
                st.write(slide["content"])
        else:
            st.warning("Unable to process the file. Please verify your input.")
else:
    st.info("Configure your inputs, then click 'Generate Slide Deck' to proceed.")
