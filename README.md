# mini-rag

this is a Rag model for our graduation project that answers/retrives users questions/requirements for the project teammates.

## Requirements 


### Setup the environment variables

''' bash
$ cp .env.example .env
'''
Set your environment variables in the '.env' file. Like "OPENAI_API_KEY" value.

#### Run the fastapi server

''' bash
$ uvicorn main:app --reload --host 0.0.0.0 --port 5000
'''