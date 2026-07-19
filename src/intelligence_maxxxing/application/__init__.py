"""Application layer: use-case orchestration.

Depends on the domain and on ports only. Never on FastAPI, SQLAlchemy or any
concrete infrastructure (protected by import-linter and constitutional tests).
"""
