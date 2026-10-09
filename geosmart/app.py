"""Initialize the Flask app and register GEOSMART routes."""

from geosmart.app_core import app
from geosmart.config import init_database, session_scope
from geosmart.services.complaint_service import bootstrap_sample_data
from geosmart.web_support import inject_session_context

app.context_processor(inject_session_context)
init_database()
with session_scope() as db_session:
    bootstrap_sample_data(db_session)

# Importing the modules registers route handlers on the shared app instance.
from geosmart.routes import api, errors, pages  # noqa: E402,F401
