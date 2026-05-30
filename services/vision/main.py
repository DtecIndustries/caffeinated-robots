import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config import CAMERA_INDEX, CAMERA_URL, STREAM_HOST, STREAM_PORT
from camera.capture import Camera
from camera.stream import router as stream_router, set_camera


cam = Camera(CAMERA_URL if CAMERA_URL else CAMERA_INDEX)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cam.start()
    yield
    cam.stop()


app = FastAPI(lifespan=lifespan)
set_camera(cam)
app.include_router(stream_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host=STREAM_HOST, port=STREAM_PORT, reload=False)
