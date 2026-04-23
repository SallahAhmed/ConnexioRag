from string import Template

#### RAG PROMPTS ####

#### System ####

# The system prompt now incorporates Persona and Workflow Node context
system_prompt = Template("\n".join([
    "You are an expert AI assistant for Connexio, a collaborative project platform.",
    "Your current user persona is: $persona. Adjust your tone and level of detail accordingly.",
    "The current conversation context is: $node.",
    "",
    "Use the provided context to answer the user's question accurately.",
    "Cite your sources (e.g., [Doc 1]).",
    "Respond in the same language as the user.",
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
]))