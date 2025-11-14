from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import pathlib, asyncio
import smtplib
from email.mime.text import MIMEText

TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"  # solo per test

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

REQUESTS = {}
MESSAGES = {}
STREAMS = {}
RID = 1

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
# ... tuoi import ...

# <-- QUI hai app = FastAPI() ecc.

TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"  # SOLO TEST, non usare così in produzione!


@app.get("/login", response_class=HTMLResponse)
def login_form(req: Request):
    return templates.TemplateResponse("login.html", {"request": req, "error": None})


@app.post("/login")
def login(req: Request, username: str = Form(...), password: str = Form(...)):
    if username == TEST_USERNAME and password == TEST_PASSWORD:
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie("user", username, httponly=True)
        return resp
    # credenziali errate
    return templates.TemplateResponse(
        "login.html",
        {"request": req, "error": "Credenziali non valide."},
        status_code=401
    )
SMTP_HOST = "smtp.example.com"      # es: smtp.gmail.com
SMTP_PORT = 587
SMTP_USER = "tuoindirizzo@example.com"
SMTP_PASS = "tua_password_o_app_password"
NOTIFY_TO = "info@ciminobroker.it"  # dove vuoi ricevere le notifiche
BASE_URL = "http://localhost:8000"      # oppure l'URL del tuo Codespace o server

def send_new_request_email(request_data: dict):
    """
    Invia una email di notifica per una nuova richiesta.
    """
    rid = request_data["id"]
    customer_name = request_data["customer_name"]
    lob = request_data.get("lob", "N/D")

    link_pratica = f"{BASE_URL}/r/{rid}"

    subject = f"Nuova richiesta di quotazione — {lob} — {customer_name}"
    body = (
        f"Ciao,\n\n"
        f"È stata caricata una nuova richiesta di quotazione sul portale.\n\n"
        f"Cliente: {customer_name}\n"
        f"Ramo: {lob}\n"
        f"ID pratica: {rid}\n\n"
        f"Puoi visualizzarla cliccando qui:\n{link_pratica}\n\n"
        f"— Broker Quote Hub"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_TO

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            print(f"Email di notifica inviata a {NOTIFY_TO}")
    except Exception as e:
        print(f"Errore nell'invio email: {e}")

@app.get("/", response_class=HTMLResponse)
def home(req: Request):
    user = req.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {
        "request": req,
        "items": list(REQUESTS.values()),
        "user": user
    })
@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("user")
    return resp


@app.post("/new")
async def new_request(customer_name: str = Form(...), customer_tax_id: str = Form(...), lob: str = Form(...), notes: str = Form("")):
    global RID
    REQUESTS[RID] = {
        "id": RID, "customer_name": customer_name, "customer_tax_id": customer_tax_id,
        "lob": lob, "notes": notes, "created_at": datetime.utcnow().isoformat()
    }
    MESSAGES[RID] = []
    STREAMS[RID] = asyncio.Queue()
    rid = RID
    RID += 1
    return RedirectResponse(url=f"/r/{rid}", status_code=303)

@app.get("/r/{rid}", response_class=HTMLResponse)
def request_page(req: Request, rid: int):
    if rid not in REQUESTS: return RedirectResponse("/", 303)
    return templates.TemplateResponse("request.html", {"request": req, "item": REQUESTS[rid], "messages": MESSAGES[rid]})

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

    # invio email di notifica (in un thread separato per non bloccare)
    try:
        asyncio.create_task(asyncio.to_thread(send_new_request_email, REQUESTS[rid]))
    except Exception as e:
        print(f"Errore nell'avviare il task di email: {e}")

    return RedirectResponse(url=f"/r/{rid}", status_code=303)


@app.post("/r/{rid}/msg")
async def add_msg(rid: int, text: str = Form(...)):
    if rid not in REQUESTS: return RedirectResponse("/", 303)
    msg = {"who": "utente", "text": text.strip(), "ts": datetime.utcnow().isoformat()}
    if not msg["text"]: return RedirectResponse(url=f"/r/{rid}", status_code=303)
    MESSAGES[rid].append(msg); await STREAMS[rid].put(msg)
    return RedirectResponse(url=f"/r/{rid}", status_code=303)

@app.get("/r/{rid}/stream")
async def stream(rid: int):
    if rid not in STREAMS: return RedirectResponse("/", 303)
    queue = STREAMS[rid]
    async def eventgen():
        for m in MESSAGES[rid]:
            yield f"data: {m['ts']} — {m['who']}: {m['text']}\n\n"
        while True:
            m = await queue.get()
            yield f"data: {m['ts']} — {m['who']}: {m['text']}\n\n"
    return StreamingResponse(eventgen(), media_type="text/event-stream")
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
RCP_OPTIONS = {
    "Sanitario": {
        "professioni": {
            "Medico": {
                "massimali": ["€250.000", "€500.000", "€1.000.000", "€2.000.000"],
                "retro": ["Nessuna", "2 anni", "5 anni", "Illimitata"],
                "postuma": ["1 anno", "5 anni", "10 anni"]
            },
            "Infermiere": {
                "massimali": ["€250.000", "€500.000", "€1.000.000"],
                "retro": ["Nessuna", "2 anni", "5 anni"],
                "postuma": ["1 anno", "5 anni"]
            }
        }
    },
    "Tecnico": {
        "professioni": {
            "Ingegnere": {
                "massimali": ["€500.000", "€1.000.000", "€2.000.000"],
                "retro": ["2 anni", "5 anni", "Illimitata"],
                "postuma": ["1 anno", "5 anni", "10 anni"]
            },
            "Architetto": {
                "massimali": ["€500.000", "€1.000.000"],
                "retro": ["2 anni", "5 anni"],
                "postuma": ["1 anno", "5 anni"]
            }
        }
    },
    "Legale": {
        "professioni": {
            "Avvocato": {
                "massimali": ["€250.000", "€500.000", "€1.000.000"],
                "retro": ["Nessuna", "5 anni", "Illimitata"],
                "postuma": ["1 anno", "5 anni", "10 anni"]
            }
        }
    },
    "Economico": {
        "professioni": {
            "Commercialista": {
                "massimali": ["€500.000", "€1.000.000"],
                "retro": ["2 anni", "5 anni", "Illimitata"],
                "postuma": ["1 anno", "5 anni"]
            },
            "Consulente del Lavoro": {
                "massimali": ["€250.000", "€500.000", "€1.000.000"],
                "retro": ["2 anni", "5 anni"],
                "postuma": ["1 anno", "5 anni"]
            }
        }
    }
}

@app.get("/rcp", response_class=HTMLResponse)
def rcp_form(request: Request):
    settori = sorted(RCP_OPTIONS.keys())
    return templates.TemplateResponse(
        "rcp.html",
        {"request": request, "settori": settori, "options": RCP_OPTIONS}
    )

@app.post("/rcp/start")
async def rcp_start(
    settore: str = Form(...),
    professione: str = Form(...),
    massimale: str = Form(...),
    retro: str = Form(...),
    postuma: str = Form(...)
):
    global RID
    REQUESTS[RID] = {
        "id": RID,
        "customer_name": "Da compilare",
        "customer_tax_id": "Da compilare",
        "lob": "RC Professionale",
        "product": professione,
        "notes": f"Settore: {settore} | Massimale: {massimale} | Retroattività: {retro} | Postuma: {postuma}",
        "status": "Bozza",
        "created_at": datetime.utcnow().isoformat()
    }
    MESSAGES[RID] = []
    STREAMS[RID] = asyncio.Queue()
    msg = {
        "who": "system",
        "text": f"Nuova richiesta RC Professionale per {professione}. Massimale {massimale}, retro {retro}, postuma {postuma}.",
        "ts": datetime.utcnow().isoformat()
    }
    MESSAGES[RID].append(msg)
    await STREAMS[RID].put(msg)
    save_state()
    rid = RID
    RID += 1
    return RedirectResponse(f"/r/{rid}", status_code=303)
