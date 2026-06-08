import os
import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import pass_context

from database.db import db_cv, DATABASE_PATH
from database.init_db import init_db
from config import SECRET_KEY

from routes import RedirectException
from routes.customer import router as customer_router
from routes.worker import router as worker_router
from routes.admin import router as admin_router

# Ensure database directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
# Initialize database structure and seed data
init_db()

app = FastAPI(title="AisleWise")

# Set up Session Middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


# Database session middleware using contextvars
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    conn = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    token = db_cv.set(conn)
    try:
        response = await call_next(request)
        conn.commit()
        return response
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
        db_cv.reset(token)


# Custom Exception Handler for RedirectException
@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    return RedirectResponse(url=exc.url, status_code=303)

def session_context_processor(request: Request) -> dict:
    return {"session": request.session}

# Setup Templates and static assets
templates = Jinja2Templates(directory="templates", context_processors=[session_context_processor])
app.mount("/static", StaticFiles(directory="static"), name="static")


from urllib.parse import urlencode
from starlette.routing import Route, Mount
import re

@pass_context
def custom_url_for(context, name: str, **params):
    request = context.get("request")
    if not request:
        return ""
    
    app = request.app
    
    def find_route_path(router_or_app, target_name):
        # Handle cases where router_or_app has .routes (FastAPI app or Router)
        routes = getattr(router_or_app, "routes", None)
        if not routes:
            return None
        for route in routes:
            if isinstance(route, Mount):
                path = find_route_path(route.app, target_name)
                if path is not None:
                    return path
            elif isinstance(route, Route) and route.name == target_name:
                return route.path
        return None

    route_path = find_route_path(app, name)
    if route_path is None:
        return str(request.url_for(name, **params))

    # Match parameter names in the path, e.g. {product_id} or {product_id:int}
    path_param_names = set(re.findall(r"\{([^:\}]+)(?::[^\}]+)?\}", route_path))
    
    path_params = {}
    query_params = {}
    for k, v in params.items():
        if k in path_param_names:
            path_params[k] = v
        else:
            query_params[k] = v
            
    base_url = str(request.url_for(name, **path_params))
    if query_params:
        base_url += "?" + urlencode(query_params)
        
    return base_url


# Custom flash message helper in Jinja2
@pass_context
def get_flashed_messages(context):
    request = context.get("request")
    if request:
        return request.session.pop("_flashes", [])
    return []


templates.env.globals["get_flashed_messages"] = get_flashed_messages
templates.env.globals["url_for"] = custom_url_for

# Expose templates to request via state
app.state.templates = templates

# Include routers
app.include_router(customer_router, prefix="/customer")
app.include_router(worker_router, prefix="/worker")
app.include_router(admin_router, prefix="/admin")


@app.get("/", response_class=HTMLResponse, name="home")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
