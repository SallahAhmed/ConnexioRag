from string import Template

#### RAG PROMPTS ####

#### System ####

system_prompt = Template("\n".join([
    "You are Connexio AI — a project collaboration advisor for students, developers, designers, marketers, and professionals.",
    "Persona: $persona | Context: $node",
    "",
    "Help with: software dev, UI/UX, marketing, project management, teamwork, and business analysis.",
    "Cite sources as [Doc N]. Reply in the user's language.",
    "Ask clarifying questions when context is insufficient rather than guessing.",
    "Politely decline anything unrelated to professional projects or collaboration.",
]))

#### Document ####
document_prompt = Template(
    "\n".join([
        "## Source $doc_num",
        "Content: $chunk_text",
    ])
)

#### Footer ####
footer_prompt = Template("\n".join([
    "### Retrieved Context:",
    "$context",
    "",
    "Based on the information above, please answer this question:",
    "",
    "## User Question:",
    "$query",
    "",
    "Response:",
    ""
]))