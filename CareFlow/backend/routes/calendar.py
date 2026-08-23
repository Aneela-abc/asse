"""
Calendar OAuth and .ics export routes.
"""
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from backend import services

router = APIRouter(prefix="/api/calendar", tags=["Calendar"])


@router.get("/google/configured")
def is_google_configured():
    return {"configured": services.google_configured()}


@router.get("/google/auth-url")
def get_auth_url(user_id: str = Query(...), redirect_uri: str = Query(...)):
    url = services.google_auth_url(user_id, redirect_uri)
    return {"auth_url": url}


@router.post("/google/token")
def exchange_token(user_id: str = Query(...), code: str = Query(...), redirect_uri: str = Query(...)):
    try:
        tok = services.google_token_exchange(code, redirect_uri)
        services.save_google_token(user_id, tok)
        return {"status": "SUCCESS", "message": "Google Calendar connected successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {str(e)}")


@router.get("/ics/{appointment_id}", response_class=PlainTextResponse)
def get_ics(appointment_id: str, doctor_name: str = Query("Doctor"), patient_name: str = Query("Patient")):
    conn = services.get_db()
    try:
        a = conn.execute("SELECT * FROM appointments WHERE id=?", (appointment_id,)).fetchone()
        if not a:
            raise HTTPException(status_code=404, detail="Appointment not found.")
        ics_data = services.ics_for_appointment(dict(a), doctor_name, patient_name)
        return Response(
            content=ics_data,
            media_type="text/calendar",
            headers={"Content-Disposition": f'attachment; filename="appointment_{appointment_id}.ics"'}
        )
    finally:
        conn.close()
