"""Streamlit entry point for the R&D Intelligence MVP."""

import streamlit as st


def main() -> None:
    """Render the initial project home page."""
    st.set_page_config(page_title="R&D Intelligence", page_icon="🔬")
    st.title("R&D Intelligence MVP")
    st.markdown(
        "Welcome to R&D Intelligence: a workspace for organizing research, "
        "exploring evidence, and supporting informed R&D decisions.\n\n"
        "This initial project foundation provides a home page only. "
        "Data ingestion, analytics, and integrations will be added in future work. "
        "No business data or credentials are required."
    )


if __name__ == "__main__":
    main()
