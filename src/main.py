import fastapi
from dotenv import load_dotenv
load_dotenv(".env")

from Routes import base
app = fastapi.FastAPI()

app.include_router(base.base_router)
