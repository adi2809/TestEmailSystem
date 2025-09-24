# Email Advising System

This repository contains a lightweight "Email Advising System" that helps an academic advising team answer routine student questions quickly and consistently. The system reads a free-form email, ranks the most relevant knowledge base articles, and produces either a ready-to-send reply or a draft that advisors can review when confidence is lower than 95%.

## Key features

- **Knowledge base driven responses** – Advising templates and follow-up prompts are stored in `data/knowledge_base.json`, making it easy to update content without touching the code.
- **Smarter query understanding** – Domain-specific synonyms, token augmentation, and utterance similarity create robust matches even when students use unfamiliar phrasing.
- **Confidence-aware automation** – Responses are auto-sent only when similarity exceeds the 0.95 threshold and all template fields are satisfied. Otherwise, the system supplies a draft and clear reasons for human review.
- **Ambiguity detection** – When multiple templates score similarly, the advisor flags the message for human review rather than guessing.
- **Explainable ranking** – The top matches (with confidence scores) are returned with every decision so advisors can understand why a template was chosen.
- **Command line interface** – Generate responses locally from the terminal or integrate with other systems via JSON output.
- **Extensible Python package** – Core components are organized as a reusable module (`email_advising`) with clean data models and utilities.
- **Automatic metadata enrichment** – The advisor can infer student names, terms, and deadline dates from the incoming message to fill in template placeholders.
- **Retrieval-augmented references** – The advisor surfaces supporting documents from `data/reference_corpus.json` (or a custom corpus) and adds citation-style references with URLs to every response using diversity-aware re-ranking.
- **LLM-ready composition** – Swap the default template composer for the `LLMEmailComposer` to let a large language model polish the draft while still grounding the answer in retrieved references.

## Getting started

1. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies (only `pytest` is required for tests):**
   ```bash
   pip install -r requirements.txt  # optional if you maintain a requirements file
   ```
   The package itself depends only on the Python standard library.

3. **Run the command line interface:**
   ```bash
   python -m email_advising --query "How do I order my transcript?" --student-name "Alex" --format text
   ```

   Example JSON output:
   ```bash
   python -m email_advising --query "I might need to withdraw from a course" \
       --student-name "Jordan" --term "Fall 2024" --withdrawal-deadline "October 21" \
       --format json
   ```

4. **Customize defaults:** Provide additional metadata (e.g., `--registration-deadline`, `--financial-aid-email`) to enrich the templates and increase the likelihood of auto-sending responses. Use `--max-references 5` to control how many citations to include, `--reference-corpus` to load a different JSON corpus, or `--disable-references` to skip retrieval entirely.

## Extending the knowledge base

- Add or edit entries in `data/knowledge_base.json`. Each entry contains:
  - `id`: unique identifier.
  - `subject`: email subject line.
  - `utterances`: sample phrases used for similarity matching.
  - `response_template`: email body template supporting `{placeholder}` substitution.
  - `follow_up_questions`: suggested prompts for advisors when manual review is required.
- Restart the CLI (or reload the module) after saving changes so the vectorizer is rebuilt.

## Extending the reference corpus

- Supporting documents used for retrieval augmented generation live in `data/reference_corpus.json`.
- Each entry includes `id`, `title`, `content`, optional `url`, and optional `tags` to boost recall for related topics.
- Provide a different corpus to the CLI via `--reference-corpus path/to/custom.json` or load it programmatically with `load_reference_corpus` and `TfidfRetriever`.
- References are returned on every response via `AdvisorResponse.references` and appended to the email body using `[n]` citation markers.

## Automatic metadata enrichment

- Incoming questions are scanned for names (e.g., “My name is Taylor”), academic terms (“Fall 2024”), and contextual date mentions (“before October 21”) to pre-fill template placeholders.
- Extracted metadata is added only when the caller did not explicitly provide a value so human-provided data always wins.
- Each inferred value is logged in the response `reasons` field for auditability.

## Composing emails with LLMs

The default `TemplateEmailComposer` uses the knowledge base verbatim. For more natural phrasing, pair the advisor with an LLM that returns JSON containing `subject` and `body` keys:

```python
from openai import OpenAI

from email_advising import (
    EmailAdvisor,
    LLMEmailComposer,
    TfidfRetriever,
    load_knowledge_base,
    load_reference_corpus,
)

client = OpenAI()


def call_openai(prompt: str) -> str:
    response = client.responses.create(model="gpt-4o-mini", input=prompt)
    # The composer expects the model to return a JSON string with "subject" and "body" keys.
    return response.output_text


knowledge_base = load_knowledge_base()
corpus = load_reference_corpus()
retriever = TfidfRetriever(corpus)
composer = LLMEmailComposer(call_openai)
advisor = EmailAdvisor(knowledge_base, retriever=retriever, composer=composer)

result = advisor.process_query("Can you help me withdraw from a class?", {"student_name": "Riley"})
print(result.body)
```

Any callable that accepts a prompt and returns a JSON string can be used—mock implementations make it easy to test offline.

## Automated tests

Run the test suite with:

```bash
pytest
```

Tests cover article ranking, the 95% auto-send threshold, manual-review handling, and the inclusion of follow-up prompts.
Additional tests verify the synonym-powered ranking, metadata enrichment, and ambiguous query handling.

## Repository structure

```
email_advising/      Core Python package
├── advisor.py         Matching, retrieval, and response generation engine
├── cli.py             Command line interface
├── composers.py       Template and LLM-based email composition strategies
├── knowledge_base.py  Loader for the knowledge base JSON file
├── rag.py             Retrieval utilities and TF–IDF retriever for references
├── similarity.py      Minimal TF–IDF implementation
├── text_processing.py Text normalization utilities
└── __main__.py        Entry point for `python -m email_advising`

data/                Knowledge base content
├── knowledge_base.json
└── reference_corpus.json

tests/               Pytest-based unit tests
└── test_advisor.py
```

## License

This project is provided as-is for demonstration purposes.
