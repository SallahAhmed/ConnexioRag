from fastapi import FastAPI, APIRouter, Depends
import os
from helpers.config import get_settings, Settings
from time import sleep
import logging 

logger = logging.getLogger(__name__)

base_router = APIRouter(
    prefix ="/api/v1",
    tags=["api_v1"]
)

@base_router.get("/")
async def welcome(app_settings: Settings = Depends(get_settings)):

    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION

    # app_name = os.getenv("APP_NAME")
    # app_version = os.getenv("APP_VERSION")

    return {
        "app_name": app_name,
        "app_version": app_version,
    }

@base_router.get("/send_reports")
async def send_reports(app_settings: Settings = Depends(get_settings)):

    for ix in range(15):
        logger.info(f"Sending report {ix}")
        sleep(3)
    
    return {
        "success":True,
        "message": "Reports sent successfully"
    }    
