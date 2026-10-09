"""Flask route modules, registered on the shared application instance."""

from . import api, errors, pages

__all__ = ["api", "errors", "pages"]
