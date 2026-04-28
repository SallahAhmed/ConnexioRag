# [MODIFY] src/flowerconfig.py
from dotenv import dotenv_values
config = dotenv_values(".env")
# Flower configuration
port = 5556
max_tasks = 10000
auto_refresh = True
# Add this line to fix the NaN issue
broker_api = config.get("CELERY_FLOWER_BROKER_API") 
# Authentication
basic_auth = [f'admin:{config["CELERY_FLOWER_PASSWORD"]}']