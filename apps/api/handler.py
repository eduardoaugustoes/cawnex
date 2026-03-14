"""
Lambda entry point — wraps FastAPI with Mangum.

This file lives at the package root so the Lambda handler path is handler.handler.
"""

from mangum import Mangum

from src.main import app

handler = Mangum(app, lifespan="off")
