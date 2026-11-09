# ASKus OS shim: newer PyMuPDF is imported as "pymupdf", older Debian builds only as "fitz".
from fitz import *  # noqa: F401,F403
import fitz as _fitz
globals().update({k: getattr(_fitz, k) for k in dir(_fitz) if not k.startswith("__")})
