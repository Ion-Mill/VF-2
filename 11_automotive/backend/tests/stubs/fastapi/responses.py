class StreamingResponse:
    def __init__(self, content, media_type=None, headers=None):
        self.content, self.media_type, self.headers = content, media_type, headers


class JSONResponse:
    def __init__(self, status_code=200, content=None):
        self.status_code, self.content = status_code, content
