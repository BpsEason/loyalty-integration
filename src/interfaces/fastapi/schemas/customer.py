from pydantic import BaseModel


class IdentifyByQrRequest(BaseModel):
    qr_token: str