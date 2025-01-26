# AutoDeckAI: 🌿 Eco-centric Slide Generator

**Transform Ecological Research into Stunning Presentations Effortlessly**

AutoDeckAI is an advanced AI-powered tool designed to help researchers, practitioners, and funding bodies create professional, audience-specific PowerPoint presentations directly from ecological research materials. Whether you have PDFs, abstracts, or supplementary materials, AutoDeckAI streamlines the process, saving you time and effort!

## 🌟 Features

- **Multiple Input Options**: Upload PDFs, enter DOI/URLs, or provide abstracts and supplementary materials.
- **Dynamic Content Extraction**: Automatically extracts text, figures, and tables using PyPDF2 and PyMuPDF.
- **Smart Captions**: GPT-4 generates concise and meaningful labels for figures and tables.
- **Audience-Specific Customization**: Tailor presentations for researchers, practitioners, or funding bodies.
- **Thematic Flexibility**: Customize themes for visually appealing slides.
- **High-Quality Outputs**: Generate structured PowerPoint presentations with integrated visuals, captions, and logical flow.

## 🚀 How It Works

1. **Choose Your Input**: Upload a PDF, enter a DOI/URL, or type an abstract.
2. **Set Your Configuration**: Select the target audience, number of slides, and theme.
3. **Generate Slides**: The tool processes your input, extracts key elements, and creates a tailored slide deck.
4. **Download & Preview**: Get a polished PowerPoint presentation and preview the slides in-app.

## 🔧 Tech Stack

- **Python**: Backend engine for processing.
- **Streamlit**: Interactive and user-friendly web interface.
- **PyPDF2 & PyMuPDF**: For content extraction from PDFs.
- **GPT-4**: Powers dynamic content generation and captioning.
- **FAISS**: Enables semantic search for relevant document segments.
- **python-pptx**: Generates high-quality PowerPoint presentations.

## 📝 Getting Started

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/AutoDeckAI.git
   cd AutoDeckAI
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:
   ```bash
   streamlit run app.py
   ```

## 🌍 Who Is This For?

- **Ecologists**: Communicate research findings effectively.
