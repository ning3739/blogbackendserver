from pydantic import Field
from app.core.config.base import EnvBaseSettings


class DomainSettings(EnvBaseSettings):
    DOMAIN_URL: str = Field(..., description="Domain for the application")
    COOKIE_DOMAIN: str = Field(
        default=".heyxiaoli.com",
        description="Cookie domain (with leading dot for subdomain sharing, e.g., .heyxiaoli.com)",
    )
