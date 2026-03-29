from .BaseController import BaseController
from .ProjectController import ProjectController
from fastapi import UploadFile
from models import ResponseSignal
import os
import re


class DataController(BaseController):
    def __init__(self):
        super().__init__() # super is for calling BaseController, and self is for DataController
        self.size_scale = 1048576 # to convert MB to Bytes


    def validate_uploaded_file(self, file: UploadFile):
        print("Validating file: ", file.content_type)

        allowed_types = self.app_settings.FILE_ALLOWED_TYPES
        allowed_exts = [ext.lower() for ext in [getattr(self.app_settings, 'FILE_ALLOWED_EXTENSIONS', None)] if ext]  # fallback if you add FILE_ALLOWED_EXTENSIONS
        filename = file.filename or ""
        file_ext = os.path.splitext(filename)[-1].lower()

        # If content_type is application/octet-stream, check extension
        if file.content_type == "application/octet-stream":
            # Accept only if extension is allowed (txt, pdf, etc.)
            if file_ext not in ['.txt', '.pdf']:
                return False, ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value
        else:
            if file.content_type not in allowed_types:
                return False, ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value

        # Check file size if available
        if hasattr(file, 'size') and file.size is not None:
            if file.size > self.app_settings.FILE_MAX_SIZE * self.size_scale:
                return False, ResponseSignal.FILE_SIZE_EXCEEDED.value

        return True, ResponseSignal.FILE_VALIDATED_SUCCESS.value
    def generate_unique_filepath(self, orig_file_name: str, project_id: str):

        random_key = self.generate_random_string()
        project_path = ProjectController().get_project_path(project_id=project_id)

        cleaned_file_name = self.get_clean_file_name(
            orig_file_name=orig_file_name
        )

        new_file_path = os.path.join(
            project_path,
            random_key + "_" + cleaned_file_name
        )

        while os.path.exists(new_file_path):
            random_key = self.generate_random_string()
            new_file_path = os.path.join(
                project_path,
                random_key + "_" + cleaned_file_name
            )

        return new_file_path, random_key + "_" + cleaned_file_name

    def get_clean_file_name(self, orig_file_name: str):

        # remove any special characters, except underscore and .
        cleaned_file_name = re.sub(r'[^\w.]', '', orig_file_name.strip())

        # replace spaces with underscore
        cleaned_file_name = cleaned_file_name.replace(" ", "_")

        return cleaned_file_name