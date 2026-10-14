"""FormLaw backend."""
import os

# Some Windows machines (Smart App Control) block SQLAlchemy's compiled extension.
# The pure-Python implementation is functionally identical.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
