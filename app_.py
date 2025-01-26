import os
import time
import tempfile
import streamlit as st
from faiss_vector_store_ import VectorStoreManager
from utils_ import (
    download_pdf_from_url,
    enhanced_extraction,
    parse_llm_response,
    clean_static_directory,
    generate_slides_with_retrieval,
    PresentationGenerator,
    extract_and_caption_pdf_elements,
    validate_openai_key,
    preprocess_text_for_ecology
)
openai_api_key = "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"
# =========================================
# UI Configuration & Constants
# =========================================
THEMES = {
    "Forest": {"primary": "#2E7D32", "secondary": "#81C784"},
    "Ocean": {"primary": "#0277BD", "secondary": "#4FC3F7"},
    "Soil": {"primary": "#5D4037", "secondary": "#8D6E63"}
}

SLIDE_TEMPLATES = {
    "Scientific": "templates/scientific_template.pptx",
    "Business": "templates/business_template.pptx",
    "Minimalist": "templates/minimalist_template.pptx"
}

def configure_page():
    """Set up Streamlit page configuration"""
    st.set_page_config(
        page_title="EcoDeck: Intelligent Slide Generator",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown("""
        <style>
            .stProgress > div > div > div > div {
                background-color: #4CAF50;
            }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
            }
        </style>
    """, unsafe_allow_html=True)

def validate_inputs(api_key, content_inputs):
    """Validate user inputs before processing"""
    if not api_key:
        st.error("Please provide a valid OpenAI API key")
        return False
    if not any(content_inputs):
        st.error("Please provide content via abstract, file upload, or URL/DOI")
        return False
    return True

def handle_file_input(uploaded_file, doi_url):
    """Handle file upload or URL/DOI input"""
    if uploaded_file:
        # Save uploaded file to temp location
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    elif doi_url:
        return download_pdf_from_url(doi_url)
    return None

def process_document(file_path):
    """Process document and return cleaned content"""
    try:
        extracted_content = enhanced_extraction(file_path)
        return preprocess_text_for_ecology(extracted_content["text"])
    except Exception as e:
        st.error(f"Document processing failed: {str(e)}")
        raise

def extract_visuals(file_path, api_key):
    """Extract and caption visual elements"""
    try:
        return extract_and_caption_pdf_elements(
            file_path,
            api_key,
            output_dir="./content/"
        )
    except Exception as e:
        st.warning(f"Visual extraction failed: {str(e)}")
        return []

def generate_slide_content(text_content, visual_elements, api_key, num_slides, audience):
    """Generate slide content using LLM"""
    vector_manager = VectorStoreManager()
    vectorstore = vector_manager.create_vectorstore(text_content, api_key)
    
    return generate_slides_with_retrieval(
        vectorstore=vectorstore,
        presentation_focus=audience,
        num_slides=num_slides,
        extracted_elements=visual_elements,
        openai_api_key=api_key
    )

def create_final_deck(slides, template, theme):
    """Create final presentation deck"""
    generator = PresentationGenerator(SLIDE_TEMPLATES[template])
    return generator.generate_from_slides(
        slides,
        {"theme": THEMES[theme], "title": st.session_state.get("presentation_title", "EcoDeck Presentation")}
    )

def present_download_options(pptx_file):
    """Show download options and preview"""
    with open(pptx_file, "rb") as f:
        st.download_button(
            label="📥 Download Presentation",
            data=f.read(),
            file_name="EcoDeck_Presentation.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    
    st.success("Preview of generated slides:")
    for i, slide in enumerate(st.session_state.slides):
        with st.expander(f"Slide {i+1}: {slide['title']}"):
            st.markdown(f"**{slide['title']}**")
            st.write(slide["content"])
            if "elements" in slide:
                for elem in slide["elements"]:
                    st.caption(f"{elem['type']}: {elem['caption']}")

def main():
    configure_page()
    
    # Session state initialization
    if "slides" not in st.session_state:
        st.session_state.slides = []
    
    # [Previous sidebar and main UI code remains the same...]

    # Updated Generation Controls
    if st.button("🚀 Generate Presentation", use_container_width=True):
        if not validate_inputs(openai_api_key, [abstract, uploaded_file, doi_url]):
            return
            
        with st.status("🛠️ Processing your request...", expanded=True) as status:
            try:
                process_start = time.time()
                
                # File handling
                file_path = handle_file_input(uploaded_file, doi_url)
                if not file_path:
                    raise ValueError("No valid input source found")
                
                # Content processing
                status.update(label="🔍 Extracting document content...")
                extracted_text = process_document(file_path)
                
                # Visual processing
                status.update(label="🖼️ Processing visual elements...")
                visual_elements = extract_visuals(file_path, openai_api_key)
                
                # Slide generation
                status.update(label="🧠 Generating slide content...")
                llm_response = generate_slide_content(
                    extracted_text,
                    visual_elements,
                    openai_api_key,
                    num_slides,
                    target_audience
                )
                st.session_state.slides = parse_llm_response(llm_response)
                
                # Presentation assembly
                status.update(label="🎨 Designing presentation...")
                pptx_file = create_final_deck(
                    st.session_state.slides,
                    template,
                    theme
                )
                
                # Final output
                st.success(f"✅ Presentation generated in {time.time()-process_start:.1f}s")
                present_download_options(pptx_file)
                
            except Exception as e:
                st.error(f"🚨 Error during processing: {str(e)}")
                st.exception(e)

if __name__ == "__main__":
    main()