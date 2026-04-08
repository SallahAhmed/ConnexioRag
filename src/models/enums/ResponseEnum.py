from enum import Enum

class ResponseSignal(Enum):

    FILE_VALIDATED_SUCCESS = "file_validate_successfully"
    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    FILE_UPLOAD_SUCCESS = "file_upload_success"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    PROCESSING_FAILED= "processing_failed"
    PROCESSING_SUCCESS= "processing_success"
    NO_FILES_FOUND = "no_files_found"
    FILE_ID_ERROR = "no_file_found_with_this_id"
    INSERT_INTO_VECTORDB_ERROR = "insert_into_vector_db_error"
    INSERT_INTO_VECTORDB_SUCCESS = "insert_into_vector_db_success"
    VECTORDB_COLLECTION_RETRIEVED = "vector_db_collection_retrieved"
    VECTORDB_SEARCH_ERROR = "vector_db_search_error"
    VECTORDB_SEARCH_SUCCESS = "vector_db_search_success"
    RAG_ANSWER_ERROR = "rag_answer_error"
    RAG_ANSWER_SUCCESS = "rag_answer_success"
    PROJECT_NOT_FOUND_ERROR = "project_not_found_error"
    GENERATION_CLIENT_ERROR = "generation_client_error"
    EMBEDDING_CLIENT_ERROR = "embedding_client_error"
    VECTORDB_CLIENT_ERROR = "vector_db_client_error"
    TEMPLATE_PARSER_ERROR = "template_parser_error"
    