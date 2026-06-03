"""QLoRA fine-tuning pipeline for VideoGameWizard.

Objective: adapt Llama 3.1 8B into a better *grounded RAG reader* — fluent at
answering from retrieved context in the VideoGameWizard voice. Fine-tuning here
teaches task/format/style; the RAG pipeline still supplies the facts. See
``README.md`` (the model card) in this directory.
"""
