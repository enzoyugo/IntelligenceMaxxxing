"""Pure domain layer.

Constitutional constraint: this package is pure Python. It must not import
FastAPI, SQLAlchemy, httpx, psycopg, or any infrastructure/API module.
Protected by import-linter contracts and tests/constitutional.
"""
