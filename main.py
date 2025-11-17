from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
from typing import Optional
import pathlib, asyncio, smtplib
from email.mime.text import MIMEText

# --- CREDENZIALI DI TEST LOGIN ---
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"

# --- CONFIGURAZIONE EMAIL (DA PERSONALIZZARE QUANDO SARAI PRONTO) ---
SMTP_HOST = "smtp.example.com"          # es: smtp.gmail.com o smtp.ionos.it
SMTP_PORT = 587
SMTP_USER = "info@ciminobroker.it"      # mittente
SMTP_PASS = "INSERISCI_PASSWORD_SMTP"   # password/app password SMTP
NOTIFY_TO = "info@ciminobroker.it"      # destinatario avvisi


app = FastAPI()

# Static (CSS, ecc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Storage in memoria
REQUESTS = {}
MESSAGES = {}
STREAMS = {}
RID = 1


# ---------- FUNZIONI DI SUPPORTO ----------

def practice_link(req: Request, rid: int) -> str:
    try:
        return str(req.url_for("request_page", rid=rid))
    except Exception:
        return f"{req.base_url}r/{rid}"


def _send_email(subject: str, body: str):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = NOTIFY_TO

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        print(f"[EMAIL] Inviata a {NOTIFY_TO}: {subject}")
    except Exception as e:
        print(f"[EMAIL] Errore nell'invio: {e}")


def send_email_async(subject: str, body: str):
    # lancia l'invio email in background, senza bloccare la webapp
    asyncio.create_task(asyncio.to_thread(_send_email, subject, body))


def require_user(req: Request) -> Optional[str]:
    return req.cookies.get("user")


# ---------- LOGIN / LOGOUT / DASHBOARD ----------

@app.get("/", response_class=HTMLResponse)
def login_form(req: Request):
    """Pagina di login (senza menu laterale)."""
    user = require_user(req)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": req, "error": None})


@app.post("/login")
def login(req: Request, username: str = Form(...), password: str = Form(...)):
    if username == TEST_USERNAME and password == TEST_PASSWORD:
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie("user", username, httponly=True)
        return resp
    return templates.TemplateResponse(
        "login.html",
        {"request": req, "error": "Credenziali non valide."},
        status_code=401
    )


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("user")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(req: Request):
    user = require_user(req)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": req,
            "items": list(REQUESTS.values()),
            "user": user,
        }
    )


# ---------- FORM RC PROFESSIONALE ----------

@app.get("/rc-professionale", response_class=HTMLResponse)
def rc_professionale(req: Request):
    user = require_user(req)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("rc_professionale.html", {"request": req})


# ---------- CREAZIONE NUOVA RICHIESTA (STANDARD + RC PRO) ----------

@app.post("/new")
async def new_request(
    req: Request,
    customer_name: str = Form(...),
    customer_tax_id: str = Form(...),
    lob: str = Form(...),
    notes: str = Form(""),
    rc_settore: Optional[str] = Form(None),
    rc_professione: Optional[str] = Form(None),
    rc_attivita: Optional[str] = Form(None),
    rc_fatturato: Optional[str] = Form(None),
    rc_massimale: Optional[str] = Form(None),
    rc_retroattivita: Optional[str] = Form(None),
    rc_postuma: Optional[str] = Form(None),
    rc_addetti: Optional[str] = Form(None),
    rc_estero: Optional[str] = Form(None),
    rc_sinistri: Optional[str] = Form(None),
    rc_attivita_particolari: Optional[str] = Form(None),
    files: Optional[UploadFile] = File(None)
):
    global RID

    data = {
        "id": RID,
        "customer_name": customer_name.strip(),
        "customer_tax_id": customer_tax_id.strip(),
        "lob": lob.strip(),
        "notes": notes.strip(),
        "created_at": datetime.utcnow().isoformat()
    }

    # Se è RC Professionale, salvo anche i campi extra
    if lob.strip() == "RC Professionale":
        data.update({
            "rc_settore": rc_settore,
            "rc_professione": rc_professione,
            "rc_attivita": rc_attivita,
            "rc_fatturato": rc_fatturato,
            "rc_massimale": rc_massimale,
            "rc_retroattivita": rc_retroattivita,
            "rc_postuma": rc_postuma,
            "rc_addetti": rc_addetti,
            "rc_estero": rc_estero,
            "rc_sinistri": rc_sinistri,
            "rc_attivita_particolari": rc_attivita_particolari,
        })

    REQUESTS[RID] = data
    MESSAGES[RID] = []
    STREAMS[RID] = asyncio.Queue()
    rid = RID
    RID += 1

    # eventuale file caricato direttamente dal form (singolo)
    if files:
        folder = pathlib.Path("uploads") / f"req-{rid}"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / files.filename
        dest.write_bytes(await files.read())
        msg = {
            "who": "system",
            "text": f"📎 File caricato dal form: {files.filename}",
            "ts": datetime.utcnow().isoformat()
        }
        MESSAGES[rid].append(msg)
        await STREAMS[rid].put(msg)

    # invia EMAIL di nuova richiesta
    link = practice_link(req, rid)
    subject = f"Nuova richiesta di quotazione — {lob} — {customer_name}"
    body = (
        f"Ciao,\n\n"
        f"È stata caricata una nuova richiesta di quotazione sul portale.\n\n"
        f"Cliente: {customer_name}\n"
        f"Ramo: {lob}\n"
        f"ID pratica: {rid}\n\n"
        f"Apri la pratica da questo link:\n{link}\n\n"
        f"-- CIMINO BROKER — Broker Quote Hub"
    )
    send_email_async(subject, body)

    return RedirectResponse(url=f"/r/{rid}", status_code=303)


# ---------- DETTAGLIO RICHIESTA ----------

@app.get("/r/{rid}", response_class=HTMLResponse, name="request_page")
def request_page(req: Request, rid: int):
    user = require_user(req)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    if rid not in REQUESTS:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        "request.html",
        {
            "request": req,
            "item": REQUESTS[rid],
            "messages": MESSAGES[rid],
        }
    )


# ---------- UPLOAD FILE SU PRATICA ----------

@app.post("/r/{rid}/upload")
async def upload_file(rid: int, file: UploadFile = File(...)):
    if rid not in REQUESTS:
        return RedirectResponse(url="/dashboard", status_code=303)

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


# ---------- CHAT INTERNA / MESSAGGI ----------

@app.post("/r/{rid}/msg")
async def add_msg(req: Request, rid: int, text: str = Form(...)):
    if rid not in REQUESTS:
        return RedirectResponse(url="/dashboard", status_code=303)

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

    # Email di aggiornamento pratica
    link = practice_link(req, rid)
    subject = f"Aggiornamento richiesta #{rid} — {REQUESTS[rid]['lob']} — {REQUESTS[rid]['customer_name']}"
    body = (
        f"C'è un nuovo aggiornamento sulla pratica #{rid}.\n\n"
        f"Messaggio inserito:\n{txt}\n\n"
        f"Puoi aprire la pratica qui:\n{link}\n\n"
        f"-- CIMINO BROKER — Broker Quote Hub"
    )
    send_email_async(subject, body)

    return RedirectResponse(url=f"/r/{rid}", status_code=303)


# ---------- STREAM MESSAGGI (EVENTI) ----------

@app.get("/r/{rid}/stream")
async def stream(rid: int):
    if rid not in STREAMS:
        return RedirectResponse(url="/dashboard", status_code=303)

    queue = STREAMS[rid]

    async def eventgen():
        for m in MESSAGES[rid]:
            yield f"data: {m['ts']} — {m['who']}: {m['text']}\n\n"
        while True:
            m = await queue.get()
            yield f"data: {m['ts']} — {m['who']}: {m['text']}\n\n"

    return StreamingResponse(eventgen(), media_type="text/event-stream")
