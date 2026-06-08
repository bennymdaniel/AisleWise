from fastapi import Request

class RedirectException(Exception):
    def __init__(self, url: str):
        self.url = url

def flash(request: Request, message: str):
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    request.session["_flashes"].append(message)
