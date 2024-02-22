import logging
import os

from prisma.models import APIRouteSpec, Function

from codex.api_model import Identifiers
from codex.develop.develop import DevelopAIBlock
from codex.develop.model import FunctionDef

RECURSION_DEPTH_LIMIT = int(os.environ.get("RECURSION_DEPTH_LIMIT", 3))

logger = logging.getLogger(__name__)

# hacky way to list all generated functions, will be replaced with a vector-lookup
generated_function_defs: list[FunctionDef] = []


async def develop_route(
    ids: Identifiers,
    route_description: str,
    func_name: str,
    api_route: APIRouteSpec,
) -> Function:
    global generated_function_defs
    generated_function_defs = []

    route_function: Function = await DevelopAIBlock().invoke(
        ids=ids,
        invoke_params={
            "function_name": func_name,
            "description": route_description,
            "provided_functions": [
                f.function_template
                for f in generated_function_defs
                if f.name != func_name
            ],
            # api_route is not used by the prompt, but is used by the function
            "api_route": api_route,
        },
    )

    if route_function.ChildFunction:
        for child in route_function.ChildFunction:
            # We don't need to store the output here,
            # as the function will be stored in the database
            await recursive_create_function(ids, route_description, child, api_route)

    return route_function


async def recursive_create_function(
    ids: Identifiers,
    route_description: str,
    function_def: Function,
    api_route: APIRouteSpec,
    depth: int = 0,
) -> Function:
    """
    Recursively creates a function and its child functions
    based on the provided function definition.

    Args:
        ids (Identifiers): The identifiers for the function.
        route_description (str): The description of the route.
        function_def (Function): The function definition.
        api_route (APIRouteSpec): The API route specification.

    Returns:
        Function: The created function.
    """
    if depth > 0:
        logger.warning(f"Recursion depth: {depth} for route {route_description}")
    if depth > RECURSION_DEPTH_LIMIT:
        raise ValueError("Recursion depth exceeded")

    description = f"""
{function_def.template}

High-level Goal: {route_description}"""

    route_function: Function = await DevelopAIBlock().invoke(
        ids=ids,
        invoke_params={
            "function_name": function_def.functionName,
            "description": description,
            "provided_functions": [
                f.function_template
                for f in generated_function_defs
                if f.name != function_def.functionName
            ],
            # api_route is not used by the prompt, but is used by the function
            "api_route": api_route,
            # function_id is used so we can update the function with the implementation
            "function_id": function_def.id,
        },
    )

    if route_function.ChildFunction:
        for child in route_function.ChildFunction:
            # We don't need to store the output here,
            # as the function will be stored in the database
            await recursive_create_function(
                ids, route_description, child, api_route, depth + 1
            )

    return route_function
