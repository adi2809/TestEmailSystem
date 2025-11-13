"""Simple web interface for the Email Advising System."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

from flask import Flask, render_template, request

from .advisor import EmailAdvisor
from .knowledge_base import load_knowledge_base
from .rag import TfidfRetriever, load_reference_corpus


def _build_advisor() -> EmailAdvisor:
    """Create a default :class:`EmailAdvisor` instance for the UI."""

    knowledge_base = load_knowledge_base()
    try:
        corpus = load_reference_corpus()
    except FileNotFoundError:
        retriever: Optional[TfidfRetriever] = None
    else:
        retriever = TfidfRetriever(corpus)
    return EmailAdvisor(knowledge_base, retriever=retriever)


def create_app(advisor: Optional[EmailAdvisor] = None) -> Flask:
    """Create and configure the Flask application."""

    templates = Path(__file__).with_name("templates")
    static = Path(__file__).with_name("static")
    app = Flask(
        __name__,
        template_folder=str(templates),
        static_folder=str(static),
    )

    active_advisor = advisor or _build_advisor()

    metadata_fields: Iterable[dict[str, str]] = (
        {"key": "student_name", "label": "Student name", "placeholder": "Jordan"},
        {"key": "student_id", "label": "Student ID", "placeholder": "A00123456"},
        {"key": "term", "label": "Academic term", "placeholder": "Fall 2024"},
        {
            "key": "registration_deadline",
            "label": "Registration deadline",
            "placeholder": "August 15",
        },
        {
            "key": "withdrawal_deadline",
            "label": "Withdrawal deadline",
            "placeholder": "October 21",
        },
        {
            "key": "financial_aid_email",
            "label": "Financial aid email",
            "placeholder": "finaid@university.edu",
        },
        {
            "key": "financial_aid_phone",
            "label": "Financial aid phone",
            "placeholder": "(555) 123-4567",
        },
    )

    @app.context_processor
    def inject_metadata_fields() -> Dict[str, Iterable[dict[str, str]]]:
        return {"metadata_fields": metadata_fields}

    @app.route("/", methods=["GET", "POST"])
    def index():  # type: ignore[override]
        query = ""
        error = None
        result = None
        submitted_metadata: Dict[str, str] = {}

        if request.method == "POST":
            query = (request.form.get("query") or "").strip()
            for field in metadata_fields:
                value = (request.form.get(field["key"]) or "").strip()
                if value:
                    submitted_metadata[field["key"]] = value
            if not query:
                error = "Please paste a student email or question before submitting."
            else:
                try:
                    result = active_advisor.process_query(query, submitted_metadata)
                except Exception as exc:  # pragma: no cover - defensive
                    error = f"An error occurred while generating a response: {exc}"

        return render_template(
            "index.html",
            query=query,
            metadata=submitted_metadata,
            result=result,
            error=error,
        )

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover - manual use
    app.run(debug=True)
