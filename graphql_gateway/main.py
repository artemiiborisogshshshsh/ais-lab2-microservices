
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from graphql_gateway.schema import schema
from graphql_gateway.products import create_product_loader


app = FastAPI(
    title="GraphQL Gateway",
    description="Единый GraphQL API для микросервисов Order и Catalog",
    version="1.0.0",
)


def get_context():
    return {
        "product_loader": create_product_loader()
    }


graphql_router = GraphQLRouter(
    schema,
    graphql_ide="graphiql",
    context_getter=get_context,
)


app.include_router(
    graphql_router,
    prefix="/graphql",
)
