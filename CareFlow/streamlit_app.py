import os
import json
from datetime import datetime, timedelta, date, time as dtime

import streamlit as st
import api_client as core

def env(k, default=''):
    return os.getenv(k, default)

def to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}

def get_val(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj[key]
    except Exception:
        return default

def safe_json_loads(val, default=None):
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return default

st.set_page_config(page_title="CareFlow — Healthcare Appointment Manager", page_icon="🩺", layout="wide")
core.run_background_jobs_if_due()

DAY_OPTIONS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
STATUS_COLOR = {'CONFIRMED': '🟢', 'COMPLETED': '✅', 'CANCELLED': '🔴', 'HELD': '🟡', 'NO_SHOW': '⚪'}
STATUS_HEX = {'CONFIRMED': '#16a34a', 'COMPLETED': '#2563eb', 'CANCELLED': '#dc2626', 'HELD': '#ca8a04', 'NO_SHOW': '#6b7280'}
URGENCY_HEX = {'High': '#dc2626', 'Medium': '#f59e0b', 'Low': '#16a34a'}
SPECIALTY_COLORS = ['#7c3aed', '#0ea5e9', '#f97316', '#059669', '#db2777', '#4f46e5', '#0d9488']


def spec_color(spec):
    return SPECIALTY_COLORS[abs(hash(spec)) % len(SPECIALTY_COLORS)]


def pill(text, bg, fg='#ffffff'):
    return f'<span style="background:{bg};color:{fg};padding:3px 12px;border-radius:999px;font-size:0.78rem;font-weight:700;letter-spacing:.02em;white-space:nowrap;">{text}</span>'


def chip(text, bg='#ede9fe', fg='#5b21b6'):
    return f'<span style="background:{bg};color:{fg};padding:2px 9px;border-radius:8px;font-size:0.75rem;font-weight:600;margin-right:4px;display:inline-block;margin-bottom:3px;">{text}</span>'


def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Poppins', sans-serif !important; }

    .stApp {
        background: radial-gradient(circle at 0% 0%, #ede9fe 0%, #f8fafc 35%, #eff6ff 100%);
    }

    /* Hero banner */
    .cf-hero {
        background: linear-gradient(120deg, #7c3aed 0%, #6366f1 45%, #0ea5e9 100%);
        padding: 26px 32px; border-radius: 20px; margin-bottom: 22px;
        box-shadow: 0 12px 30px -10px rgba(99,102,241,0.55);
    }
    .cf-hero h1 { color: #fff !important; margin: 0; font-size: 2rem; letter-spacing: -0.02em; }
    .cf-hero p { color: #ede9fe; margin: 6px 0 0 0; font-size: 1.02rem; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #4c1d95 0%, #5b21b6 55%, #1e3a8a 100%);
    }
    section[data-testid="stSidebar"] * { color: #f3e8ff !important; }
    section[data-testid="stSidebar"] .stButton>button {
        background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.35);
        color: #fff !important; border-radius: 10px; font-weight: 600;
    }
    section[data-testid="stSidebar"] .stButton>button:hover { background: rgba(255,255,255,0.28); }

    /* Buttons */
    .stButton>button, .stFormSubmitButton>button {
        background: linear-gradient(90deg, #7c3aed, #4f46e5);
        color: #fff; border: none; border-radius: 10px; font-weight: 600;
        padding: 0.5rem 1.1rem; transition: transform .12s ease, box-shadow .12s ease;
        box-shadow: 0 4px 14px -4px rgba(79,70,229,0.55);
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        transform: translateY(-1px); box-shadow: 0 8px 18px -4px rgba(79,70,229,0.65); color:#fff;
    }
    .stLinkButton a {
        background: linear-gradient(90deg, #0ea5e9, #2563eb) !important; color: #fff !important;
        border-radius: 10px !important; border: none !important; font-weight: 600 !important;
    }
    div[data-testid="stDownloadButton"]>button {
        background: linear-gradient(90deg, #059669, #10b981); color: #fff; border: none;
        border-radius: 10px; font-weight: 600;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 2px solid #e9d5ff; }
    .stTabs [data-baseweb="tab"] {
        background: #f5f3ff; border-radius: 10px 10px 0 0; padding: 8px 18px;
        font-weight: 600; color: #6d28d9;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #7c3aed, #4f46e5) !important; color: #fff !important;
    }

    /* Expanders as cards */
    div[data-testid="stExpander"] {
        border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden;
        box-shadow: 0 2px 10px -4px rgba(30,41,59,0.12); margin-bottom: 12px; background: #fff;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600; font-family: 'Poppins', sans-serif; padding: 10px 6px;
    }

    /* Metric-style stat cards */
    .cf-stat {
        border-radius: 16px; padding: 18px 16px; color: #fff; text-align: left;
        box-shadow: 0 8px 20px -8px rgba(0,0,0,0.25);
    }
    .cf-stat .cf-stat-label { font-size: 0.82rem; opacity: 0.9; font-weight: 600; }
    .cf-stat .cf-stat-value { font-size: 1.9rem; font-weight: 800; font-family: 'Poppins', sans-serif; }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"], .stDateInput input {
        border-radius: 10px !important;
    }

    div[data-testid="stForm"] {
        background: #fff; border-radius: 16px; padding: 18px 20px; border: 1px solid #ede9fe;
        box-shadow: 0 4px 16px -8px rgba(99,102,241,0.25);
    }
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f'<div class="cf-hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def stat_card(label, value, color_from, color_to):
    st.markdown(
        f'<div class="cf-stat" style="background:linear-gradient(135deg,{color_from},{color_to});">'
        f'<div class="cf-stat-label">{label}</div><div class="cf-stat-value">{value}</div></div>',
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------ session --
if 'user' not in st.session_state:
    st.session_state.user = None

# ------------------------------------------------------------- google oauth --
qp = st.query_params
if qp.get('code') and qp.get('state') and not st.session_state.get('_google_done'):
    try:
        redirect_uri = qp.get('redirect_uri_hint') or st.session_state.get('_redirect_uri', '')
        tok = core.google_token_exchange(qp.get('code'), redirect_uri)
        core.save_google_token(qp.get('state'), tok)
        st.session_state._google_done = True
        st.toast('Google Calendar connected ✅')
    except Exception as e:
        st.warning(f"Google Calendar connection failed: {e}")
    st.query_params.clear()


def require_login():
    hero("🩺 CareFlow", "Book appointments, get AI pre-visit &amp; post-visit summaries, and stay notified by email and calendar.")
    st.info("🔓 **Open access demo:** enter any email and any password — an account is created automatically the first time. Existing emails just log straight in with their existing role.", icon="ℹ️")

    with st.form("login_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Your name (used only when creating a new account)")
            email = st.text_input("Email", placeholder="you@example.com")
        with c2:
            password = st.text_input("Password", type="password", placeholder="anything works")
            role = st.selectbox("I am a…", ["patient", "doctor", "admin"], format_func=lambda r: r.capitalize())
        submitted = st.form_submit_button("Continue →", use_container_width=True)

    if submitted:
        try:
            user, created, overridden = core.login_or_register(email, password, role, name)
            st.session_state.user = user
            if created:
                st.toast(f"Account created — welcome, {user['name']}! 🎉")
            elif overridden:
                st.toast(f"This email is already registered as **{user['role']}** — logging you in with that role.")
            st.rerun()
        except core.AppError as e:
            st.error(str(e))

    st.caption("Tip: pick **doctor** with a brand-new email to instantly get your own bookable profile (editable afterwards under My Profile). Pick **admin** to manage all doctors and appointments.")


def doctor_detail_expander(d, key_prefix=""):
    """A doctor card with a down-arrow expander for full details — this is the
    'down arrow for doctor details' control."""
    d = to_dict(d)
    leaves = safe_json_loads(get_val(d, 'leave_days'), default=[])
    color = spec_color(get_val(d, 'specialization', 'General Medicine'))
    header = f"👨‍⚕️ {get_val(d, 'name')} — {get_val(d, 'specialization')}"
    with st.expander(header, expanded=False):
        st.markdown(pill(get_val(d, 'specialization'), color), unsafe_allow_html=True)
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Working days**")
            st.markdown(''.join(chip(day) for day in get_val(d, 'working_days', '').split(',') if day), unsafe_allow_html=True)
            st.markdown(f"**Hours:** {get_val(d, 'start_time')} – {get_val(d, 'end_time')}")
        with c2:
            st.markdown(f"**Slot length:** {get_val(d, 'slot_minutes')} minutes")
            st.markdown(f"**Email:** {get_val(d, 'email', '—')}")
            if leaves:
                st.markdown("**Upcoming leave:** " + ''.join(chip(x, '#fee2e2', '#b91c1c') for x in leaves), unsafe_allow_html=True)
            else:
                st.markdown("**Upcoming leave:** " + chip('None scheduled', '#dcfce7', '#166534'), unsafe_allow_html=True)
    return leaves


def notifications_panel(user_id):
    notifs = core.list_notifications(user_id)
    if not notifs:
        st.info("No notifications yet.")
        return
    for n in notifs[:30]:
        n = to_dict(n)
        payload = safe_json_loads(get_val(n, 'payload'), default={})
        n_status = get_val(n, 'status', 'QUEUED')
        icon = {"SENT": "✅", "QUEUED": "⏳", "FAILED": "⚠️"}.get(n_status, "•")
        badge_color = {"SENT": "#16a34a", "QUEUED": "#ca8a04", "FAILED": "#dc2626"}.get(n_status, "#6b7280")
        with st.expander(f"{icon} {get_val(payload, 'subject', 'Notification')} — {str(get_val(n, 'created_at', ''))[:16].replace('T',' ')}"):
            st.markdown(pill(n_status, badge_color) + '&nbsp;&nbsp;' + chip(get_val(n, 'type', 'EMAIL')), unsafe_allow_html=True)
            st.write("")
            st.write(get_val(payload, 'body', ''))
            last_err = get_val(n, 'last_error')
            st.caption(f"Attempts: {get_val(n, 'attempts', 0)}" + (f" · Last error: {last_err}" if last_err and last_err != 'DEMO_MODE' else ""))


# ------------------------------------------------------------------ patient --
def patient_portal(user):
    tab_book, tab_appts, tab_notifs = st.tabs(["🔎 Find & Book", "📅 My Appointments", "🔔 Notifications"])

    with tab_book:
        query = st.text_input("Search doctors by specialization", placeholder="e.g. Cardiology, General Medicine")
        doctors = core.list_doctors(query)
        if not doctors:
            st.warning("No doctors match that specialization.")
        for d in doctors:
            leaves = doctor_detail_expander(d)
            c1, c2 = st.columns([1, 2])
            with c1:
                chosen_date = st.date_input("Date", min_value=date.today(), key=f"date_{d['user_id']}")
            slots, on_leave = core.get_slots(d['user_id'], chosen_date.isoformat())
            if on_leave:
                st.warning("Doctor is on leave this day.")
            if not slots:
                st.caption("No open slots for this date.")
                st.divider()
                continue
            slot_labels = [datetime.fromisoformat(s).strftime('%H:%M') for s in slots]
            with c2:
                chosen_label = st.selectbox("Available slot", slot_labels, key=f"slot_{d['user_id']}")
            chosen_slot = slots[slot_labels.index(chosen_label)]
            symptoms = st.text_area("Describe your symptoms (required before booking)", key=f"sym_{d['user_id']}", placeholder="e.g. Fever for 2 days, mild headache, sore throat")
            if st.button(f"✨ Get AI summary & book with {d['name']} at {chosen_label}", key=f"book_{d['user_id']}"):
                if not symptoms.strip():
                    st.error("Please describe your symptoms first.")
                else:
                    try:
                        result = core.book_appointment(user['id'], d['user_id'], chosen_slot, symptoms)
                        st.success(f"Appointment confirmed for {chosen_label} on {chosen_date.isoformat()}!")
                        s = result['previsit_summary']
                        st.markdown(f"**🤖 AI pre-visit summary** &nbsp;" + pill(s['urgency_level'], URGENCY_HEX.get(s['urgency_level'], '#6b7280')), unsafe_allow_html=True)
                        st.write(s['chief_complaint'])
                        st.write("Suggested questions for the doctor:")
                        for q in s['suggested_questions']:
                            st.write(f"- {q}")
                        st.caption(s.get('disclaimer', ''))
                        st.caption(f"Calendar sync status: {result['calendar']}")
                    except core.BookingConflict as e:
                        st.error(str(e))
                    except core.AppError as e:
                        st.error(str(e))
            st.divider()

    with tab_appts:
        appts = core.list_appointments(user)
        if not appts:
            st.info("You have no appointments yet.")
        for a in appts:
            label = f"{STATUS_COLOR.get(a['status'],'')} {a['start_at'][:16].replace('T',' ')} — Dr. {a['doctor_name']} ({a['specialization']}) — {a['status']}"
            with st.expander(label):
                st.markdown(pill(a['status'], STATUS_HEX.get(a['status'], '#6b7280')), unsafe_allow_html=True)
                st.write("")
                st.write(f"**Symptoms reported:** {a['symptoms']}")
                if a.get('previsit_summary'):
                    s = safe_json_loads(a['previsit_summary'])
                    if s:
                        st.markdown(f"**🤖 Pre-visit AI summary** &nbsp;" + pill(s.get('urgency_level', 'Medium'), URGENCY_HEX.get(s.get('urgency_level'), '#6b7280')), unsafe_allow_html=True)
                        st.write(s.get('chief_complaint', ''))
                if a['status'] == 'COMPLETED' and a.get('postvisit_summary'):
                    s = safe_json_loads(a['postvisit_summary'])
                    if s:
                        st.markdown("**📝 Post-visit summary**")
                        st.write(s.get('summary', ''))
                        if s.get('medication_schedule'):
                            st.write("Medication schedule:")
                            for m in s['medication_schedule']:
                                st.write(f"- {m}")
                        if s.get('follow_up_steps'):
                            st.write("Follow-up steps:")
                            for f in s['follow_up_steps']:
                                st.write(f"- {f}")
                cal = st.session_state.get('_ics_' + a['id'])
                doctor_name = a.get('doctor_name', 'your doctor')
                st.download_button("Download calendar invite (.ics)", core.ics_for_appointment(a, doctor_name, user['name']),
                                    file_name=f"appointment_{a['id'][:8]}.ics", key=f"ics_{a['id']}")
                if a['status'] == 'CONFIRMED':
                    if st.button("Cancel appointment", key=f"cancel_{a['id']}"):
                        core.cancel_appointment(a['id'], user)
                        st.rerun()

    with tab_notifs:
        notifications_panel(user['id'])


# ------------------------------------------------------------------- doctor --
def doctor_portal(user):
    tab_appts, tab_profile, tab_notifs = st.tabs(["📅 My Appointments", "🧑‍⚕️ My Profile & Leave", "🔔 Notifications"])

    with tab_appts:
        appts = core.list_appointments(user)
        upcoming = [a for a in appts if a['status'] == 'CONFIRMED']
        others = [a for a in appts if a['status'] != 'CONFIRMED']
        st.subheader(f"Upcoming ({len(upcoming)})")
        for a in upcoming:
            s_peek = safe_json_loads(a.get('previsit_summary')) if a.get('previsit_summary') else None
            urgency_tag = f" [{s_peek['urgency_level']}]" if s_peek and 'urgency_level' in s_peek else ""
            with st.expander(f"{a['start_at'][:16].replace('T',' ')} — {a['patient_name']}{urgency_tag}"):
                st.write(f"**Patient symptoms:** {a['symptoms']}")
                if a.get('previsit_summary'):
                    s = safe_json_loads(a['previsit_summary'])
                    if s:
                        st.markdown(f"**🤖 AI pre-visit summary** &nbsp;" + pill(s.get('urgency_level', 'Medium'), URGENCY_HEX.get(s.get('urgency_level'), '#6b7280')), unsafe_allow_html=True)
                        st.write(s.get('chief_complaint', ''))
                        st.write("Suggested questions:")
                        for q in s.get('suggested_questions', []):
                            st.write(f"- {q}")
                with st.form(f"complete_{a['id']}"):
                    notes = st.text_area("Doctor notes")
                    rx = st.text_input("Prescription (include frequency, e.g. 'twice a day')")
                    done = st.form_submit_button("Complete visit & generate patient summary")
                if done:
                    summary = core.complete_appointment(a['id'], user['id'], notes, rx)
                    st.success("Visit completed. Patient-friendly summary generated and sent.")
                    st.write(summary['summary'])
                    st.rerun()
                if st.button("Cancel appointment", key=f"doccancel_{a['id']}"):
                    core.cancel_appointment(a['id'], user)
                    st.rerun()
        st.subheader("History")
        for a in others:
            with st.expander(f"{STATUS_COLOR.get(a['status'],'')} {a['start_at'][:16].replace('T',' ')} — {a['patient_name']} — {a['status']}"):
                st.markdown(pill(a['status'], STATUS_HEX.get(a['status'], '#6b7280')), unsafe_allow_html=True)
                st.write("")
                st.write(f"**Symptoms:** {a['symptoms']}")
                if a['doctor_notes']:
                    st.write(f"**Notes:** {a['doctor_notes']}")
                if a['prescription']:
                    st.write(f"**Prescription:** {a['prescription']}")

    with tab_profile:
        c = core.db()
        p = to_dict(core.doctor_profile(c, user['id']))
        c.close()
        st.markdown(f"**{get_val(p, 'name', 'Doctor')}** · {get_val(p, 'specialization', 'General Medicine')}")
        with st.form("profile_form"):
            spec = st.text_input("Specialization", value=get_val(p, 'specialization', 'General Medicine'))
            working_days_str = get_val(p, 'working_days', 'Mon,Tue,Wed,Thu,Fri')
            days = st.multiselect("Working days", DAY_OPTIONS, default=working_days_str.split(',') if working_days_str else [])
            c1, c2, c3 = st.columns(3)
            with c1:
                start_t = st.time_input("Start time", value=dtime.fromisoformat(get_val(p, 'start_time', '09:00')))
            with c2:
                end_t = st.time_input("End time", value=dtime.fromisoformat(get_val(p, 'end_time', '17:00')))
            with c3:
                slot_len = st.number_input("Slot minutes", min_value=10, max_value=120, step=5, value=int(get_val(p, 'slot_minutes', 30)))
            leaves_data = safe_json_loads(get_val(p, 'leave_days'), default=[])
            leave_dates = st.date_input("Leave days (existing bookings on these days will be cancelled & patients notified)",
                                         value=[date.fromisoformat(d) for d in leaves_data] or [], format="YYYY-MM-DD")
            saved = st.form_submit_button("Save profile")
        if saved:
            if isinstance(leave_dates, (list, tuple)):
                leave_list = [d.isoformat() for d in leave_dates]
            elif leave_dates:
                leave_list = [leave_dates.isoformat()]
            else:
                leave_list = []
            affected = core.admin_update_doctor(user['id'], specialization=spec, working_days=','.join(days),
                                                 start_time=start_t.strftime('%H:%M'), end_time=end_t.strftime('%H:%M'),
                                                 slot_minutes=slot_len, leave_days=leave_list)
            st.success("Profile updated.")
            if affected:
                st.warning(f"{len(affected)} confirmed appointment(s) were cancelled due to new leave days and patients were notified.")
            st.rerun()

        st.divider()
        st.markdown("**Google Calendar**")
        google_calendar_widget(user)

    with tab_notifs:
        notifications_panel(user['id'])


def google_calendar_widget(user):
    if not core.google_configured():
        st.caption("Not configured. Set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in your environment to enable real Google Calendar sync. Until then, every appointment still gets a downloadable .ics invite.")
        return
    redirect_uri = core.env('GOOGLE_REDIRECT_URI') or st.session_state.get('_app_url', '')
    st.session_state._redirect_uri = redirect_uri
    c = core.db()
    connected = bool(c.execute('SELECT 1 FROM google_tokens WHERE user_id=?', (user['id'],)).fetchone())
    c.close()
    if connected:
        st.success("Google Calendar connected.")
    else:
        url = core.google_auth_url(user['id'], redirect_uri)
        st.link_button("Connect Google Calendar", url)


# -------------------------------------------------------------------- admin --
def admin_portal(user):
    tab_doctors, tab_appts, tab_notifs, tab_dash = st.tabs(["🧑‍⚕️ Doctors", "📅 Appointments", "🔔 Notification queue", "📊 Dashboard"])

    with tab_doctors:
        st.subheader("Create doctor profile")
        with st.form("create_doctor"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name")
                email = st.text_input("Email")
                pw = st.text_input("Temporary password", value="doctor123")
                spec = st.text_input("Specialization")
            with c2:
                days = st.multiselect("Working days", DAY_OPTIONS, default=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
                start_t = st.time_input("Start time", value=dtime(9, 0))
                end_t = st.time_input("End time", value=dtime(17, 0))
                slot_len = st.number_input("Slot minutes", min_value=10, max_value=120, step=5, value=30)
            created = st.form_submit_button("Create doctor")
        if created:
            try:
                core.admin_create_doctor(name, email, pw, spec, ','.join(days), start_t.strftime('%H:%M'), end_t.strftime('%H:%M'), slot_len)
                st.success(f"Doctor {name} created.")
                st.rerun()
            except core.AppError as e:
                st.error(str(e))

        st.subheader("All doctors")
        doctors = core.list_doctors('')
        for d in doctors:
            leaves = doctor_detail_expander(d)
            with st.expander(f"Manage leave — {d['name']}", expanded=False):
                new_leaves = st.date_input(f"Leave days for {d['name']}", value=[date.fromisoformat(x) for x in leaves] or [],
                                            format="YYYY-MM-DD", key=f"leave_{d['user_id']}")
                if st.button("Update leave days", key=f"updleave_{d['user_id']}"):
                    if isinstance(new_leaves, (list, tuple)):
                        ll = [x.isoformat() for x in new_leaves]
                    elif new_leaves:
                        ll = [new_leaves.isoformat()]
                    else:
                        ll = []
                    affected = core.admin_update_doctor(d['user_id'], leave_days=ll)
                    st.success("Leave days updated.")
                    if affected:
                        st.warning(f"{len(affected)} appointment(s) cancelled and patients notified.")
                    st.rerun()

    with tab_appts:
        appts = core.list_appointments(user)
        for a in appts:
            with st.expander(f"{STATUS_COLOR.get(a['status'],'')} {a['start_at'][:16].replace('T',' ')} — {a['patient_name']} → {a['doctor_name']} — {a['status']}"):
                st.markdown(pill(a['status'], STATUS_HEX.get(a['status'], '#6b7280')), unsafe_allow_html=True)
                st.write("")
                st.write(f"**Symptoms:** {a['symptoms']}")
                if a['doctor_notes']:
                    st.write(f"**Notes:** {a['doctor_notes']}")
                if a['prescription']:
                    st.write(f"**Prescription:** {a['prescription']}")
                if a['status'] == 'CONFIRMED' and st.button("Cancel", key=f"admincancel_{a['id']}"):
                    core.cancel_appointment(a['id'], user)
                    st.rerun()

    with tab_notifs:
        st.subheader("Notification queue")
        if st.button("Process queue now"):
            n = core.process_notifications()
            m = core.process_medication_reminders()
            st.success(f"Processed {n} notification(s) and {m} medication reminder(s).")
        c = core.db()
        rows = c.execute("SELECT n.*, u.name, u.email FROM notifications n JOIN users u ON u.id=n.user_id ORDER BY n.created_at DESC LIMIT 100").fetchall()
        c.close()
        for r in rows:
            r = to_dict(r)
            payload = safe_json_loads(get_val(r, 'payload'), default={})
            r_status = get_val(r, 'status', 'QUEUED')
            icon = {"SENT": "✅", "QUEUED": "⏳", "FAILED": "⚠️"}.get(r_status, "•")
            badge_color = {"SENT": "#16a34a", "QUEUED": "#ca8a04", "FAILED": "#dc2626"}.get(r_status, "#6b7280")
            with st.expander(f"{icon} {r_status} · {get_val(payload, 'subject', 'Notification')} → {get_val(r, 'name', '')} ({get_val(r, 'email', '')})"):
                st.markdown(pill(r_status, badge_color) + '&nbsp;&nbsp;' + chip(get_val(r, 'type', 'EMAIL')), unsafe_allow_html=True)
                st.write("")
                st.write(get_val(payload, 'body', ''))
                st.caption(f"Attempts: {get_val(r, 'attempts', 0)} · Created: {get_val(r, 'created_at', '')}")
                last_err = get_val(r, 'last_error')
                if last_err and last_err != 'DEMO_MODE':
                    st.caption(f"Last error: {last_err}")

    with tab_dash:
        stats = core.dashboard_stats()
        cols = st.columns(4)
        with cols[0]:
            stat_card("Confirmed", stats['confirmed'], '#16a34a', '#059669')
        with cols[1]:
            stat_card("Completed", stats['completed'], '#2563eb', '#1d4ed8')
        with cols[2]:
            stat_card("Cancelled", stats['cancelled'], '#dc2626', '#b91c1c')
        with cols[3]:
            stat_card("Doctors", stats['doctors'], '#7c3aed', '#6d28d9')
        st.write("")
        cols2 = st.columns(3)
        with cols2[0]:
            stat_card("Patients", stats['patients'], '#0ea5e9', '#0284c7')
        with cols2[1]:
            stat_card("Notifications queued", stats['notifications_queued'], '#f59e0b', '#d97706')
        with cols2[2]:
            stat_card("Notifications sent", stats['notifications_sent'], '#10b981', '#059669')
        st.write("")
        c1, c2, c3 = st.columns(3)
        c1.markdown(("✅ " if env('LLM_API_KEY') else "⚪ ") + "**LLM summaries** " + ("live" if env('LLM_API_KEY') else "fallback mode"))
        c2.markdown(("✅ " if env('SMTP_HOST') else "⚪ ") + "**Email (SMTP)** " + ("live" if env('SMTP_HOST') else "demo mode"))
        c3.markdown(("✅ " if core.google_configured() else "⚪ ") + "**Google Calendar** " + ("configured" if core.google_configured() else ".ics fallback"))


# -------------------------------------------------------------------- main --
ROLE_EMOJI = {'patient': '🧑‍🦱', 'doctor': '🩺', 'admin': '🛠️'}
ROLE_TAGLINE = {
    'patient': 'Find doctors, book slots, and track your visits.',
    'doctor': 'Review AI-summarized symptoms and manage your schedule.',
    'admin': 'Manage doctors, appointments, and system-wide notifications.',
}


def main():
    inject_css()

    if not st.session_state.user:
        require_login()
        return

    user = st.session_state.user
    with st.sidebar:
        st.markdown(
            f'<div style="text-align:center;padding:14px 0;">'
            f'<div style="font-size:2.4rem;">{ROLE_EMOJI.get(user["role"],"👤")}</div>'
            f'<div style="font-size:1.15rem;font-weight:700;">{user["name"]}</div>'
            f'<div style="opacity:.85;font-size:.85rem;">{user["email"]}</div>'
            f'{pill(user["role"].capitalize(), "rgba(255,255,255,0.18)")}'
            f'</div>', unsafe_allow_html=True,
        )
        st.write("")
        if st.button("🚪 Log out", use_container_width=True):
            st.session_state.user = None
            st.rerun()
        st.divider()
        if core.is_backend_online():
            st.caption("🟢 **Backend REST API**: Connected")
        else:
            st.caption("🟡 **Backend**: Local Service Mode")
        st.caption("🩺 CareFlow · Healthcare Manager")

    hero(f"🩺 CareFlow", ROLE_TAGLINE.get(user['role'], ''))

    if user['role'] == 'patient':
        patient_portal(user)
    elif user['role'] == 'doctor':
        doctor_portal(user)
    else:
        admin_portal(user)


if __name__ == '__main__':
    main()
