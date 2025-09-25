from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn


class ExternalQueryRequest(BaseModel):
    cadastral_number: str
    latitude: float
    longitude: float


class ExternalAPIResponse(BaseModel):
    cadastral_number: str
    status: str
    message: Optional[str] = None
    address: Optional[str] = None
    value: Optional[float] = None


app = FastAPI()


def generate_external_response(cadastral_number: str):
    if cadastral_number == "123456789012":
        return ExternalAPIResponse(
            cadastral_number=cadastral_number,
            address="Some Street, 123",
            value=1500000.50,
            status="Success"
        )
    elif cadastral_number == "987654321098":
        return ExternalAPIResponse(
            cadastral_number=cadastral_number,
            address="Another Ave, 45",
            value=2000000.00,
            status="Success"
        )
    else:
        return ExternalAPIResponse(
            cadastral_number=cadastral_number,
            status="NotFound",
            message="Cadastral number not found in mock data"
        )


@app.post("/mock_query/", response_model=ExternalAPIResponse)
async def handle_mock_query(request: ExternalQueryRequest):
    response_data = generate_external_response(request.cadastral_number)

    if response_data.status == "NotFound":
        raise HTTPException(status_code=404, detail=response_data.message)

    return response_data


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)