class HTTPException(Exception):
    def __init__(self, status_code=500, detail=None):
        self.status_code, self.detail = status_code, detail
