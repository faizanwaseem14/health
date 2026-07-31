"""
This is the entry point of the MedVault backend.

"Entry point" means: when you start the server, this is the file that runs
first and sets everything up.

Today (Day 1, Task 1) this file is intentionally tiny. It just proves the
server boots and responds to a request. Later tasks will add:
  - environment/config loading (Task 2)
  - a real /health route that checks the database (Task 14)
  - routers for auth, reports, etc. (later days)
"""

from fastapi import FastAPI

# Create the FastAPI application object. Everything (routes, middleware,
# error handlers) gets attached to this single `app` object.
app = FastAPI(title="MedVault API")


@app.get("/")
def read_root():
    """
    A tiny placeholder route so you can confirm the server is running.

    Visiting http://127.0.0.1:8000/ in a browser should show this JSON.
    """
    return {"service": "MedVault API", "status": "running"}
