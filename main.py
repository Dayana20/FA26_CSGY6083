"""Entry point for the Cruise Trip Booking API.

Start the development server from the project root with:

    uvicorn main:app --reload

The API documentation is then at http://127.0.0.1:8000/docs.
"""

from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.router import api_router

# Load the MySQL settings from .env into the environment before anything
# connects to the database.
load_dotenv()

# Create the FastAPI application and register every endpoint
# (see app/api/router.py for the list).
app = FastAPI()
app.include_router(api_router)
