prompts = {
    "Researcher": (
    "Summarize the following text, focusing on:\n"
    "1) The restoration or experimental methods (study design, controls, measurement metrics).\n"
    "2) The key ecological outcomes (quantitative results, species recovery, habitat quality improvements).\n"
    "3) Data reliability (sample size, statistical significance, possible biases).\n"
    "4) Methodological limitations and future research directions.\n"
    "Please provide bullet points suitable for a presentation slide."
    ),
    "Practitioner": (
  "Summarize the following text, emphasizing:\n"
    "1) Practical restoration techniques (implementation steps, required materials).\n"
    "2) Observable ecological benefits and improvements (species abundance, habitat condition).\n"
    "3) Field guidelines (maintenance requirements, common pitfalls, monitoring schedules).\n"
    "4) Real-world lessons learned for on-site application.\n"
    "Please provide bullet points suitable for a presentation slide."
    ),
    "Funding Body": (
    "Summarize the following text, highlighting:\n"
    "1) The project's objectives and ecological significance.\n"
    "2) Achieved and measurable outcomes (metrics, data indicating success).\n"
    "3) Funding justification (return on investment, societal or environmental impact).\n"
    "4) Future investment opportunities or scalability.\n"
    "Please provide bullet points suitable for a presentation slide."
    )
}

slide_structures = {
    "Researcher": [
    "Title Slide",
    "Introduction & Context",
    "Methods & Study Design",
    "Results & Ecological Outcomes",
    "Data Reliability & Limitations",
    "Recommendations & Future Research",
    "Conclusion"
    ],
    "Practitioner": [
    "Title Slide",
    "Context & Introduction",
    "Techniques Implemented",
    "Ecological Benefits",
    "Implementation Challenges & Guidelines",
    "Maintenance & Monitoring",
    "Conclusion & Next Steps"
    ],
    "Funding Body": [
    "Title Slide",
    "Project Overview",
    "Objectives & Significance",
    "Achieved & Measurable Outcomes",
    "Funding Justification & ROI",
    "Future Investment & Scalability",
    "Conclusion & Next Steps"
    ]
}


    prompt = (
        f"As a **{presentation_focus}**, you have the following ecological text:\n\n"
        f"{preprocessed_text}\n\n"
        "Please **create a presentation** with "
        f"**{num_slides} slides**, covering **all crucial details** in an **eco-centric** context.\n"
        "\n**Requirements:**\n"
        "1. Each slide must have a **Title** and **Content**.\n"
        "2. Titles should be **concise** but **descriptive**.\n"
        "3. Content should be in **bullet-point format**, emphasizing:\n"
        "   - Key ecological findings\n"
        "   - Methodological or practical details\n"
        "   - Data reliability or evidence strength (where applicable)\n"
        "   - Real-world applications or ROI (depending on the audience)\n"
        "4. Maintain **logical flow** across slides (e.g., introduction, methods, results, discussion, etc.).\n"
        "5. Address **limitations**, **challenges**, or **open questions** if relevant.\n"
        "6. **Format** your response strictly as:\n"
        "Slide 1 Title: [Title]\n"
        "Slide 1 Content: [Content]\n"
        "Slide 2 Title: [Title]\n"
        "Slide 2 Content: [Content]\n"
        "...and so on, up to Slide N.\n"
        "\n**Important:**\n"
        " - Keep each slide **succinct** but **informative**.\n"
        " - Tailor your language and detail level to a **{presentation_focus}** audience.\n"
        " - Incorporate any **crucial metrics** or **supporting data** from the text (if available).\n"
        " - Ensure the final structure is suitable for a slide deck.\n\n"
        "Now, generate the slides according to these instructions."
    )