import fitz  # pymupdf
from pathlib import Path
from openai import OpenAI
from markitdown import MarkItDown


def extract_pdf_images(pdf_path, min_width=128, min_height=128):
    output_dir = Path("extracted_images")
    output_dir.mkdir(exist_ok=True)

    pdf = fitz.open(pdf_path)

    img_index = 0
    images = []
    for page in pdf:
        for img in page.get_images(full=True):
            xref = img[0]
            base_image = pdf.extract_image(xref)
            img_data, extension, width, height = [
                base_image[attr] for attr in ["image", "ext", "width", "height"]
            ]
            # Filter based on dimensions
            if width <= min_width or height <= min_height:
                continue
            img_filename = output_dir / f"img_{(img_index:=img_index+1):02d}.{extension}"
            images.append(str(img_filename))
            with open(img_filename, "wb") as f:
                f.write(img_data)
    return images


def get_pdf_images_captions(pdf_path, api_key):
    images = extract_pdf_images(pdf_path)
    captions = []

    client = OpenAI(api_key=api_key)
    md = MarkItDown(llm_client=client, llm_model="gpt-4o")

    for image in images:
        result = md.convert(image)
        if result:
            captions.append((image, result.text_content))

    return captions






# def generate_presentation(slides: list):
#     """
#     Creates a PowerPoint file from the list of slides (dicts),
#     each with 'title' and 'content', then returns the file path.
#     """
#     prs = Presentation()
#     slide_layout = prs.slide_layouts[1]

#     for slide_data in slides:
#         slide = prs.slides.add_slide(slide_layout)
#         slide.shapes.title.text = slide_data.get('title', 'Untitled Slide')
#         content = slide_data.get('content', 'No content provided.')

#         try:
#             slide.placeholders[1].text = content
#         except IndexError:
#             textbox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(5))
#             textbox.text = content

#     output_filename = "generated_presentation.pptx"
#     prs.save(output_filename)
#     return output_filename

# def generate_presentation(slides: list, author_name: str) -> str:
#     """
#     Creates a professionally formatted PowerPoint file using 'my_template.pptx'.
#     The first slide is a Title slide with Title & Author, followed by content slides,
#     a References slide, and a final Thank You slide. Each dictionary in 'slides'
#     contains 'title' and 'content' keys.
#     """
    
#     # 1. Load a custom PPTX template
#     #    Make sure 'my_template.pptx' is in the same directory or provide full path.
#     prs = Presentation("autodeckai_template.pptx")
    
#     # 2. Create the Title Slide (assumes slide_layouts[0] is a Title Slide in your template)
#     title_slide_layout = prs.slide_layouts[0]
#     title_slide = prs.slides.add_slide(title_slide_layout)
#     title_placeholder = title_slide.shapes.title
#     subtitle_placeholder = title_slide.placeholders[1]
    
#     title_placeholder.text = slides[0].get('title', 'Presentation Title')
#     subtitle_placeholder.text = f"Author: {author_name}"

#     # 3. Create the Content Slides
#     #    We'll assume that references are in the second-last slide from LLM, 
#     #    and the final "Thank You" is the last slide. So, main content slides
#     #    are from slides[1] to slides[-3].
#     main_slides = slides[1:-2]

#     # This layout index must match the layout in your template for typical content slides
#     content_layout = prs.slide_layouts[1]

#     for slide_data in main_slides:
#         slide = prs.slides.add_slide(content_layout)
#         title_placeholder = slide.shapes.title
#         body_placeholder = slide.placeholders[1]

#         # -- Set Slide Title --
#         title_placeholder.text = slide_data.get('title', 'Untitled Slide')
        
#         # -- Format Content as Bullets --
#         content_text = slide_data.get('content', 'No content provided.')
#         text_frame = body_placeholder.text_frame
#         text_frame.clear()
        
#         # Split by newline for multiple bullet points
#         lines = content_text.split('\n')
#         for line in lines:
#             paragraph = text_frame.add_paragraph()
#             # If a line starts with '-' we treat it as a bullet
#             if line.strip().startswith('-'):
#                 paragraph.text = line.lstrip('-').strip()
#                 paragraph.bullet = True
#             else:
#                 paragraph.text = line.strip()
#             paragraph.font.size = Pt(18)
#             paragraph.font.color.rgb = RGBColor(0, 0, 0)
#             paragraph.alignment = PP_ALIGN.LEFT
#             paragraph.font.name = "Calibri"

#         # Example shape highlight if slide has "Results" in its title
#         if 'Results' in slide_data.get('title', ''):
#             shape = slide.shapes.add_shape(
#                 MSO_SHAPE.ROUNDED_RECTANGLE,
#                 Inches(0.5), Inches(0.5),
#                 Inches(3), Inches(1.5)
#             )
#             shape.text = "Key Results"
#             shape.text_frame.paragraphs[0].font.size = Pt(14)
#             shape.text_frame.paragraphs[0].font.bold = True
#             shape.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
#             shape.fill.solid()
#             shape.fill.fore_color.rgb = RGBColor(91, 155, 213)

#     # 4. References Slide
#     #    We assume the LLM places references in the second-last item in 'slides'
#     references_data = slides[-2]
#     ref_slide = prs.slides.add_slide(content_layout)
#     ref_slide.shapes.title.text = references_data.get('title', 'References')
#     ref_content_frame = ref_slide.placeholders[1].text_frame
#     ref_content_frame.clear()

#     references_text = references_data.get('content', 'No references available.')
#     for line in references_text.split('\n'):
#         paragraph = ref_content_frame.add_paragraph()
#         # We treat each line as a bullet
#         paragraph.text = line.strip()
#         paragraph.bullet = True
#         paragraph.font.size = Pt(16)
#         paragraph.font.color.rgb = RGBColor(50, 50, 50)
#         paragraph.font.name = "Calibri"

#     # 5. Thank You Slide
#     #    We assume the last item in 'slides' is the Thank You content
#     thank_you_data = slides[-1]
#     thank_layout = prs.slide_layouts[0]  # or another if you have a custom "closing slide" layout
#     thank_slide = prs.slides.add_slide(thank_layout)
#     thank_slide.shapes.title.text = thank_you_data.get('title', 'Thank You')
#     if len(thank_slide.placeholders) > 1:
#         thank_subtitle = thank_slide.placeholders[1]
#         thank_subtitle.text = thank_you_data.get('content', 'We appreciate your attention!')

#     # 6. Save and Return
#     output_filename = "generated_presentation.pptx"
#     prs.save(output_filename)
#     return output_filename
