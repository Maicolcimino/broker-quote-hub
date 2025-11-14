from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import pathlib, asyncio

TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"  # solo per test

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

REQUESTS = {}
MESSAGES = {}
STREAMS = {}
RID = 1

@app.get("/", response_class=HTMLResponse)
def home(req: Request):
    return templates.TemplateResponse("index.html", {"request": req, "items": list(REQUESTS.values())})

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

@app.post("/r/{rid}/upload")
async def upload_file(rid: int, file: UploadFile = File(...)):
    if rid not in REQUESTS: return RedirectResponse("/", 303)
    folder = pathlib.Path("uploads") / f"req-{rid}"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / file.filename
    dest.write_bytes(await file.read())
    msg = {"who": "system", "text": f"📎 File caricato: {file.filename}", "ts": datetime.utcnow().isoformat()}
    MESSAGES[rid].append(msg); await STREAMS[rid].put(msg)
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
