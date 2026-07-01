"""
Shared FastAPI dependency helpers used across route modules.

Centralises the NLPController factory so every router creates it
with the same parameters and shares the cached singleton.
"""
from fastapi import Request
from controllers import NLPController


def get_nlp_controller(request: Request) -> NLPController:
    """Return a cached NLPController backed by the app's shared clients.

    Created once at first call and reused across requests.  Avoids
    recreating ToolManager (with expensive SQLDatabase init) per request.
    """
    controller = getattr(request.app, '_nlp_controller', None)
    if controller is None:
        controller = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            utility_client=getattr(request.app, 'utility_client', None),
            embedding_client=request.app.embedding_client,
            template_parser=request.app.template_parser,
            settings=getattr(request.app, 'settings', None),
            db_client=getattr(request.app, 'db_client', None),
            reranker=getattr(request.app, 'reranker', None),
            backend_client=getattr(request.app, 'backend_client', None),
            masarx_client=getattr(request.app, 'masarx_client', None),
        )
        request.app._nlp_controller = controller
    return controller


def make_nlp_controller(request: Request, **overrides) -> NLPController:
    """Build a fresh (non-cached) NLPController, optionally overriding fields.

    Use this when a caller needs a lightweight controller that doesn't
    carry settings/tool-manager (e.g. data routes that only need
    ``create_collection_name``).
    """
    kwargs = dict(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )
    kwargs.update(overrides)
    return NLPController(**kwargs)
