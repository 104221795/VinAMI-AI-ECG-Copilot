"""Safe clinical-case workspace header; it makes no decision."""

import streamlit as st


def render() -> None:
    st.subheader("Clinical Case Workspace")
    st.caption("Research-use prototype. AI-supported findings require physician review.")
    st.warning(
        "Demonstration pathway only. No automatic AMI rule-out, diagnosis, or cath-lab activation."
    )
