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


#### Changes in the base.py file and .env file 

note that the .env file should be on the same level as main.py to see the variables in postman or swagger ui 

#### text splitters have types on lang-chain website, you need to know them before making the chunks 