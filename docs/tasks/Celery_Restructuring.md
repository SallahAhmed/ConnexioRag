# Task List - Celery Restructuring

- [x] Create `tasks` package
    - [x] Create `src/tasks/__init__.py`
    - [x] Create `src/tasks/file_processing.py`
- [x] Migrate task logic
    - [x] Move `process_and_index_documents` logic from `celery_worker.py` to `src/tasks/file_processing.py`
    - [x] Rename task to `process_project_files`
- [x] Update `celery_app.py`
    - [x] Fix `task_ignore_resul` typo
    - [x] Verify `include` and `task_routes`
- [x] Clean up redundant files
    - [x] Remove `src/celery_worker.py`
- [x] Verification
    - [x] Start Celery worker and check for errors
