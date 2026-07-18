import base64

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles

from pipeline.processing import process, PipelineStatus

app = FastAPI()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024 


@app.post("/solve")
async def solve_endpoint(file: UploadFile):
    """Browser POSTs a multipart form with a file field named 'file';
    FastAPI unpacks the multipart wrapper and hands us this UploadFile.
    """

    data = await file.read() #the raw bytes of the uploaded image

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large.")

    #bytes to BGR ndarray. wraps the bytes as
    #a 1-D array; imdecode parses the image format
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Not a valid image file.")

    result = process(image) #calling the pipeline

    response = {
        "status": result.status.name, 
        "message": result.status.message,
        "image": None,
    }

    if result.status is PipelineStatus.OK:
        ok, png = cv2.imencode(".png", result.image)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to encode result image.")
        response["image"] = base64.b64encode(png.tobytes()).decode("ascii")

    return response


app.mount("/", StaticFiles(directory="src/web/static", html=True), name="static")