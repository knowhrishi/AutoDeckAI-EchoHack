# AutoDeckAI: 🌿 Eco-centric Slide Generator

**Transform Ecological Research into Practice-Oriented Presentations with AI**

AutoDeckAI is an intelligent tool designed for ecologists and environmental scientists to convert research papers, reports, and abstracts into professional PowerPoint presentations. Leveraging state-of-the-art AI, it maintains scientific rigor while enhancing communication effectiveness for diverse audiences.

<!-- Will add real images here -->

![Eco-centric Interface](https://via.placeholder.com/800x400.png?text=Streamlit+Interface+Preview)

## 🌟 Enhanced Features

- **Multi-Format Support**: Process PDFs, Word documents, PPTX files, and raw text
- **AI-Powered Insights**: GPT-4/Hugging Face integration for content generation and analysis
- **Smart Visualization**:
  - Automated figure/table extraction from PDFs
  - Context-aware image captioning
  - Dynamic data visualization options (Heatmaps, Species Distribution, etc.)
- **Ecological Focus**:
  - Term validation against ecological taxonomy
  - Sustainability metric integration
  - Theme customization (Forest, Marine, Climate, Wildlife)
- **Efficient Processing**:
  - FAISS vector caching for rapid retrieval
  - Parallel PDF processing
  - Automatic cache management

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- OpenAI API key (for GPT-4 features)
- Hugging Face token (optional for open-source models)

### Installation

```bash
git clone https://github.com/your-username/AutoDeckAI.git
cd AutoDeckAI

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

_Sample requirements.txt:_

```text
streamlit>=1.29.0
langchain>=0.1.0
python-pptx>=0.6.21
pymupdf>=1.22.0
transformers>=4.30.0
faiss-cpu>=1.7.4
langchain-openai>=0.0.1
```

### Running the Application

```bash
export OPENAI_API_KEY="your-api-key"  # Optional for Hugging Face mode
streamlit run app.py
```

## 🛠️ Configuration

1. **API Setup**:

   - Obtain OpenAI API key from [platform.openai.com](https://platform.openai.com/)
   - (Optional) Hugging Face token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

2. **Interface Options**:
   ```python
   # In app.py sidebar:
   - Select model provider (OpenAI/Hugging Face)
   - Choose ecological theme
   - Set visualization preferences
   - Configure slide count (5-25 slides)
   ```

## 📊 Workflow

1. **Input**:

   - Upload research documents (PDF/DOCX/PPTX/TXT)
   - Optional abstract input
   - Select target audience (Researcher/Practitioner/Funding Body)

2. **Processing**:

   ```mermaid
   graph TD
       A[Upload Files] --> B[Text Extraction]
       B --> C[Ecological Term Validation]
       C --> D[FAISS Vectorization]
       D --> E[AI Slide Generation]
       E --> F[PPTX Assembly]
   ```

3. **Output**:
   - Download ready-to-use PowerPoint file
   - In-app slide preview
   - Automatic figure/table citations

## 🧠 Technical Architecture

```python
# Core Components
- app.py              # Streamlit interface
- faiss_vector_store  # Vector database management
- utils.py            # Processing pipelines & AI integration
```

**Key Technologies**:

- **Natural Language Processing**: GPT-4, Mixtral-8x7B, BLIP models
- **Vector Search**: FAISS with OpenAI/Hugging Face embeddings
- **Document Processing**: PyMuPDF, python-docx, python-pptx
- **MLOps**: LangChain, Transformers, concurrent.futures

## 🌍 Environmental Impact

AutoDeckAI promotes sustainable research communication by:

- Reducing paper waste through digital-first outputs
- Optimizing energy use with efficient caching
- Encouraging reuse of visual assets
- Providing sustainability metrics in outputs

## 📜 License

MIT License - See [LICENSE](LICENSE) for details

---

**Empowering Ecological Communication Through AI**  
[Report Issue](https://github.com/knowhrishi/AutoDeckAI-EchoHack/issues) |  
[Request Feature](https://github.com/knowhrishi/AutoDeckAI-EchoHack/issues)
