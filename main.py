from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import pathlib, asyncio

# Credenziali di TEST (login)
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"  # SOLO per prove

app = FastAPI()

# Static (CSS, immagini, ecc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Storage in memoria
REQUESTS = {}
MESSAGES = {}
STREAMS = {}
RID = 1


# ---------------- LOGIN / LOGOUT / DASHBOARD ----------------

@app.get("/", response_class=HTMLResponse)
def login_form(req: Request):
    """
    Pagina di login.
    Se l'utente è già loggato, lo mando direttamente in dashboard.
    """
    user = req.cookies.get("user")
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": req, "error": None})


@app.post("/login")
def login(req: Request, username: str = Form(...), password: str = Form(...)):
    """
    Verifica le credenziali di test e, se corrette,
    imposta il cookie e reindirizza SEMPRE alla dashboard.
    """
    if username == TEST_USERNAME and password == TEST_PASSWORD:
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie("user", username, httponly=True)
        return resp

    # credenziali sbagliate: torno sulla login con messaggio di errore
    return templates.TemplateResponse(
        "login.html",
        {"request": req, "error": "Credenziali non valide."},
        status_code=401
    )


@app.get("/logout")
def logout():
    """
    Cancella il cookie e torna alla pagina di login.
    """
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("user")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(req: Request):
    """
    Dashboard principale (quella con i tile).
    Accessibile solo se loggato.
    """
    user = req.cookies.get("user")
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": req,
            "items": list(REQUESTS.values()),
            "user": user
        }
    )


# ---------------- FORM RC PROFESSIONALE ----------------

@app.get("/rc-professionale", response_class=HTMLResponse)
def rc_professionale(req: Request):
    user = req.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("rc_professionale.html", {"request": req})


# ---------------- CREAZIONE NUOVA RICHIESTA ----------------

@app.post("/new")
async def new_request(
    customer_name: str = Form(...),
    customer_tax_id: str = Form(...),
    lob: str = Form(...),
    notes: str = Form("")
):
    global RID
    REQUESTS[RID] = {
        "id": RID,
        "customer_name": customer_name,
        "customer_tax_id": customer_tax_id,
        "lob": lob,
        "notes": notes,
        "created_at": datetime.utcnow().isoformat()
    }
    MESSAGES[RID] = []
    STREAMS[RID] = asyncio.Queue()
    rid = RID
    RID += 1
    return RedirectResponse(url=f"/r/{rid}", status_code=303)


# ---------------- DETTAGLIO RICHIESTA ----------------

@app.get("/r/{rid}", response_class=HTMLResponse)
def request_page(req: Request, rid: int):
    user = req.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if rid not in REQUESTS:
        return RedirectResponse("/", 303)

    return templates.TemplateResponse(
        "request.html",
        {
            "request": req,
            "item": REQUESTS[rid],
            "messages": MESSAGES[rid]
        }
    )


# ---------------- UPLOAD FILE ----------------

@app.post("/r/{rid}/upload")
async def upload_file(rid: int, file: UploadFile = File(...)):
    if rid not in REQUESTS:
        return RedirectResponse("/", 303)

    folder = pathlib.Path("uploads") / f"req-{rid}"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / file.filename
    dest.write_bytes(await file.read())

    msg = {
        "who": "system",
        "text": f"📎 File caricato: {file.filename}",
        "ts": datetime.utcnow().isoformat()
    }
    MESSAGES[rid].append(msg)
    await STREAMS[rid].put(msg)

    return RedirectResponse(url=f"/r/{rid}", status_code=303)


# ---------------- NUOVO MESSAGGIO ----------------

@app.post("/r/{rid}/msg")
async def add_msg(rid: int, text: str = Form(...)):
    if rid not in REQUESTS:
        return RedirectResponse("/", 303)

    txt = text.strip()
    if not txt:
        return RedirectResponse(url=f"/r/{rid}", status_code=303)

    msg = {
        "who": "utente",
        "text": txt,
        "ts": datetime.utcnow().isoformat()
    }
    MESSAGES[rid].append(msg)
    await STREAMS[rid].put(msg)

    return RedirectResponse(url=f"/r/{rid}", status_code=303)


# ---------------- STREAM MESSAGGI (EVENTI) ----------------

@app.get("/r/{rid}/stream")
async def stream(rid: int):
    if rid not in STREAMS:
        return RedirectResponse("/", 303)

    queue = STREAMS[rid]

    async def eventgen():
        # invia messaggi già presenti
        for m in MESSAGES[rid]:
            yield f"data: {m['ts']} — {m['who']}: {m['text']}\n\n"
        # poi rimane in ascolto
        while True:
            m = await queue.get()
            yield f"data: {m['ts']} — {m['who']}: {m['text']}\n\n"

    return StreamingResponse(eventgen(), media_type="text/event-stream")

