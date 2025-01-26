# app.py
import os
import time
import random, tempfile
import asyncio

import concurrent.futures
import streamlit as st
from utils import (
    extract_content_from_file,
    parse_llm_response,
    clean_static_directory,
    generate_slides_with_retrieval,
    generate_presentation,
    extract_and_caption_pdf_elements,
    ECO_LOADING_MESSAGES,
    ECO_TIPS,
    get_llm,
    validate_ecological_terms
)
from faiss_vector_store import create_vectorstore, cleanup_vector_cache

cleanup_vector_cache(max_cache_size_mb=500, min_cache_age_days=1)

st.set_page_config(page_title="AutoDeckAI Eco-centric Slide Generator", layout="wide")
st.title("AutoDeckAI: 🌿 Eco-centric Slide Generator")

st.markdown(
    """This tool helps **ecologists** convert research papers and other docs into **practice-oriented presentations**."""
)
# Add warning banner here
st.warning("""
⚠️ **Note:** Hugging Face model integration is currently under development. 
For production use, please select OpenAI as your model provider.
""")
# Custom CSS for ecological theme
st.markdown("""
    <style>
    .progress-bar-wrapper { margin: 10px 0; }
    .eco-tip {
        padding: 10px;
        background-color: #e8f5e9;
        border-left: 3px solid #4caf50;
        margin: 10px 0;
    }
    .stButton>button {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)
# Show random eco tip
st.sidebar.markdown(f'<div class="eco-tip">{random.choice(ECO_TIPS)}</div>', unsafe_allow_html=True)

# =========================================
# Sidebar: API Key & Configuration
# =========================================
with st.sidebar:
    with st.expander("🔑 API Configuration", expanded=False):
        # Model selection
        model_provider = st.selectbox(
            "Select Model Provider:",
            [
                "OpenAI", 
                "Hugging Face (Open Source)"
            ],
            index=0,
            key="model_provider_selectbox_1"  
        )
        
        if model_provider == "OpenAI":
            openai_api_key = st.text_input(
                "OpenAI API Key:", 
                type="password",
                key="openai_api_key_text_input"  
            )
            model_name = st.selectbox(
                "OpenAI Model:",
                ["gpt-4o"],
                index=0,
                key="openai_model_selectbox"  
            )
        else:
            hf_api_key = st.text_input(
                "Hugging Face Token (optional):", 
                type="password", 
                help="Required for some private/gated models",
                key="hf_api_key_text_input"  
            )
            model_name = st.selectbox(
                "Hugging Face Model:",
                [
                    "mistralai/Mixtral-8x7B-Instruct-v0.1", 
                    "google/flan-t5-xxl",
    
                ],
                index=0,
                key="hf_model_selectbox"  
            )
            
            # Image captioning model selection
            caption_model_name = st.selectbox(
                "Image Captioning Model:",
                [
                    "Salesforce/blip-image-captioning-base",
                    "nlpconnect/vit-gpt2-image-captioning",
                ],
                index=0,
                key="caption_model_selectbox"  
            )


    with st.expander("🛠️ Configuration", expanded=True):
        author_name = st.text_input(
            "Enter the author's name:", 
            key="author_name_text_input"  
        )
        presentation_focus = st.selectbox(
            "Select presentation focus:",
            ["Researcher", "Practitioner", "Funding Body"],
            index=0,
            key="presentation_focus_selectbox"  
        )
        num_slides = st.number_input(
            "Number of slides (including title slide):",
            min_value=5, max_value=25, value=9, step=1,
            key="num_slides_number_input"  
        )
    with st.expander("🌍 Ecological Settings", expanded=True):

        ecological_theme = st.selectbox(
            "Visual Theme:",
            ["Forest Ecosystem", "Marine Biology", "Climate Science", "Wildlife Conservation"],
            index=0
        )

        include_metrics = st.checkbox("Include Sustainability Metrics", True)
        data_visualization = st.multiselect(
            "Preferred Visualizations:",
            ["Heatmaps", "Species Distribution", "Carbon Footprint", "Water Quality"]
        )
        




       

# =========================================
# Main Page: Inputs
# =========================================
st.header("1. Optional Abstract")
abstract_text = st.text_area("Enter your abstract (optional):", height=150)

st.header("2. Upload Any Documents (PDF, Word, PPT, Text, etc.)")
uploaded_files = st.file_uploader(
    "Select or drop multiple files here:",
    type=["pdf", "docx", "pptx", "txt"],
    accept_multiple_files=True
)

# =========================================
# Function to Process All Content
# =========================================
@st.cache_data
def process_all_content(abstract: str, files) -> str:
    """Process content with temporary files and ecological validation"""
    corpus_parts = []
    
    if abstract.strip():
        validated_abstract = validate_ecological_terms(abstract)
        corpus_parts.append(validated_abstract)

    with tempfile.TemporaryDirectory() as temp_dir:
        for file in uploaded_files:
            file_path = os.path.join(temp_dir, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            text = extract_content_from_file(file_path)
            if text and text.strip():
                validated_text = validate_ecological_terms(text)
                corpus_parts.append(validated_text)

    return "\n\n".join(corpus_parts).strip()



def process_pdfs_parallel(files, model_provider, model_name, api_key):
    """Process PDFs in parallel"""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                extract_and_caption_pdf_elements,
                file.name,
                model_provider,
                model_name,
                api_key
            )
            for file in files if file.name.lower().endswith('.pdf')
        ]
        results = []
        for future in concurrent.futures.as_completed(futures):
            results.extend(future.result())
    return results

# =========================================
# Core Action: Generate Slide Deck
# =========================================
if st.button("🚀 Generate Slide Deck"):
    # Check for API key
    if model_provider == "OpenAI" and not openai_api_key:
            st.error("❌ OpenAI requires an API key")
            st.stop()
    elif model_provider == "Hugging Face (Open Source)" and any(m in model_name for m in ["llama", "mixtral"]) and not hf_api_key:
        st.warning("⚠️ Some models require Hugging Face token for access")
    try:
        # with st.spinner("🔍 Processing your inputs..."):
                # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(progress, message):
            progress_bar.progress(progress)
            status_text.text(random.choice(ECO_LOADING_MESSAGES) + "\n" + message)

        # Document processing (20%)
        update_progress(0.2, "Processing documents...")
        # full_corpus = process_all_content(abstract_text, uploaded_files)
        # 1. Combine abstract + all files into one text corpus
        full_corpus = process_all_content(abstract_text, uploaded_files)

        # If there's no text at all, warn or use some fallback
        if not full_corpus:
            st.warning("No content found. Please provide an abstract or upload documents.")
            st.stop()

        # 2. Create vector store from combined text
        # st.info("🧠 Creating knowledge base from text...")
        update_progress(0.4, "Creating knowledge base...")

        vectorstore = create_vectorstore(
            full_corpus, 
            openai_api_key if model_provider == "OpenAI" else hf_api_key,
            model_provider
            )
        # 3. Extract visual elements from any PDFs
        # st.info("🖼️ Extracting data from uploaded documents...")
        update_progress(0.6, "Extracting visual elements...")

        clean_static_directory()  # Wipe old static content
        all_extracted_elements = []

        # For each PDF, do figure/table extraction
        for file in uploaded_files:
            if file.name.lower().endswith(".pdf"):
                pdf_path = file.name
                # This function returns a list of extracted elements
                extracted_elements = extract_and_caption_pdf_elements(
                    pdf_path,
                    model_provider=model_provider,
                    model_name=caption_model_name if model_provider != "OpenAI" else "gpt-4o-mini",
                    api_key=openai_api_key if model_provider == "OpenAI" else hf_api_key
                )
                all_extracted_elements.extend(extracted_elements)
        
        print(f"Extracted {len(all_extracted_elements)} elements:")
        for elem in all_extracted_elements:
            print(f"- {elem['type']} {elem['figure_number']} at {elem['static_path']}")

        # 4. Generate slides via retrieval from the entire text corpus
        # st.info("🖋️ Generating slides...")
        update_progress(0.8, "Crafting your presentation...")

        llm_response = generate_slides_with_retrieval(
            vectorstore=vectorstore,
            presentation_focus=presentation_focus,
            num_slides=num_slides,
            extracted_elements=all_extracted_elements,
            model_provider=model_provider,
            model_name=model_name,
            api_key=openai_api_key if model_provider == "OpenAI" else hf_api_key,
            ecological_theme=ecological_theme,
            data_visualization=data_visualization
        )

        slides = parse_llm_response(llm_response)

        # 5. Build the PowerPoint
        # st.info("🎨 Assembling the PowerPoint deck...")
        update_progress(0.9, "Adding visual flourishes...")

        # pptx_file
        # Get text LLM for table processing
        text_llm = get_llm(model_provider, model_name, 
                          openai_api_key if model_provider == "OpenAI" else hf_api_key)
        
        # Create event loop and run async presentation generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pptx_file = loop.run_until_complete(
            generate_presentation(
                slides=slides,
                author_name=author_name,
                extracted_elements=all_extracted_elements,
                text_llm=text_llm
            )
        )
        loop.close()

        # Complete (100%)
        update_progress(1.0, "✨ Your eco-focused presentation is ready!")
        time.sleep(1) 
        progress_bar.empty()
        status_text.empty()

        st.success("✅ Presentation generated successfully!")
        with open(pptx_file, "rb") as f:
            st.download_button(
                label="📥 Download PPTX",
                data=f.read(),
                file_name="EcoDeck.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

        # Optional: Show a preview of slides
        with st.expander("📄 Slide Preview"):
            for i, slide in enumerate(slides, 1):
                st.markdown(f"**Slide {i}: {slide['title']}**")
                st.write(slide["content"])

    except Exception as e:
        st.error(f"❌ Error generating slides: {str(e)}")
        st.stop()
