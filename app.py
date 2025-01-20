import streamlit as st
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from pptx import Presentation
import requests
import pdfplumber
import re
from langchain.schema import HumanMessage
# Set the title of the app
st.title("🌿 Eco-centric Slide Generator")
st.markdown(
    """
    Upload a research paper, or provide a DOI/URL to generate ecology-specific presentation slides.
    """
)

# Input for OpenAI API key
openai_api_key = st.sidebar.text_input("🔑 OpenAI API Key", type="password")

# Options for input type
input_type = st.radio(
    "Select Input Type:",
    ["Upload PDF", "Enter DOI/URL"]
)

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
def extract_text_with_pdfplumber(file_path):
    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

# Function to dynamically extract keywords using LLM
def extract_keywords_with_llm(text, openai_api_key):
    llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=0.2, model_name='gpt-4o')
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
    # detected_keywords = [kw for kw in keywords if kw in cleaned_text.lower()]
    
    st.sidebar.write("🔍 Detected Keywords:", detected_keywords)
    return cleaned_text

# Main logic
if (uploaded_file or doi_or_url) and openai_api_key:
    with st.spinner("Processing the document..."):
        # Handle file input
        if uploaded_file:
            file_path = "uploaded_document.pdf"
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
        elif doi_or_url:
            file_path = download_pdf_from_url(doi_or_url)
        
        if file_path:
            # Extract text
            extracted_text = extract_text_with_pdfplumber(file_path)
            preprocessed_text = preprocess_text_for_ecology(extracted_text)

            # Split text into chunks
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            documents = text_splitter.split_text(preprocessed_text)

            # Generate embeddings and vector store
            embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
            vector_store = FAISS.from_texts(documents, embeddings)
            retriever = vector_store.as_retriever()

            # Create RetrievalQA chain
            llm = ChatOpenAI(temperature=0.7, openai_api_key=openai_api_key, model_name='gpt-4')
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=retriever
            )

            # Query AI for slide content
            query = "Summarize the ecological significance, methods, and results for a presentation."
            summary = qa_chain.run(query)
            sentences = summary.split('.')

            # Prepare slide content
            slide_content = [
                ("Title Slide", "Generated presentation based on ecological research"),
                ("Ecological Background", f"Summary of the background: {sentences[0]}" if len(sentences) > 0 else "No background information available."),
                ("Methods", f"Methods discussed in the paper: {sentences[1]}" if len(sentences) > 1 else "No methods information available."),
                ("Results", f"Key results: {sentences[2]}" if len(sentences) > 2 else "No results information available."),
                ("Conclusion", f"Takeaways and significance: {sentences[3]}" if len(sentences) > 3 else "No conclusion available."),
            ]

            # Generate and save presentation
            def generate_presentation(slide_content):
                prs = Presentation()
                slide_layout = prs.slide_layouts[1]  # Title and Content layout
                for title, content in slide_content:
                    slide = prs.slides.add_slide(slide_layout)
                    slide.shapes.title.text = title
                    slide.placeholders[1].text = content
                prs.save("generated_presentation.pptx")
                return "generated_presentation.pptx"

            pptx_file = generate_presentation(slide_content)

            # Provide download link
            st.success("🎉 Slides generated successfully!")
            st.download_button(
                label="📥 Download Presentation",
                data=open(pptx_file, "rb"),
                file_name="EcoHack_Presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
else:
    if not openai_api_key:
        st.warning("Please enter your OpenAI API key.")
    elif not (uploaded_file or doi_or_url):
        st.warning("Please upload a PDF or enter a DOI/URL.")
