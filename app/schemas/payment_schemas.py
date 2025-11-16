from pydantic import BaseModel, Field


class PaymentIntentRequest(BaseModel):
    project_id: int = Field(..., description="The project id to be paid")
    cover_url: str = Field(..., description="The cover url of the project")
    project_name: str = Field(..., description="The name of the project")
    project_description: str = Field(...,
                                     description="The description of the project")
    project_price: float = Field(..., description="The price of the project")
    tax_name: str = Field(..., description="The name of the tax")
    tax_rate: float = Field(..., description="The rate of the tax")
    tax_amount: float = Field(..., description="The amount of the tax")
    final_amount: float = Field(...,
                                description="The final amount of the project")
