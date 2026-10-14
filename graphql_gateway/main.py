from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from graphql_gateway.schema import schema


app = FastAPI(
    title="GraphQL Gateway",
    description="Единый GraphQL API для микросервисов Order и Catalog",
    version="1.0.0",
)


graphql_router = GraphQLRouter(
    schema,
    graphql_ide="graphiql",
)


app.include_router(
    graphql_router,
    prefix="/graphql",
)