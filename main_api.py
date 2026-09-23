import logging
import uvicorn
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if __name__ == "__main__":
    uvicorn.run("app.api:app", host=settings.api_host, port=settings.api_port, reload=False)