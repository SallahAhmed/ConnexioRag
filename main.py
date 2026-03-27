import fastapi
app = fastapi.FastAPI()

@app.get("/welcome")
def welcome():
    return {
        "message": "Hello world"
    }