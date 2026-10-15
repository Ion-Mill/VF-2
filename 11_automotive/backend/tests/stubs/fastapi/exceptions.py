class RequestValidationError(Exception):
    def errors(self):
        return []
