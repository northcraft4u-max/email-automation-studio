import os
import time
import hmac
import smtplib
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import pandas as pd
import streamlit as st
from dotenv import load_dotenv, set_key

ENV_PATH = Path(".env")
CSS_PATH = Path("style.css")

load_dotenv(dotenv_path=ENV_PATH, override=True)


def get_setting(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val is not None and val != "":
        return val
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


def update_env_settings(updates: dict) -> bool:
    try:
        if not ENV_PATH.exists():
            ENV_PATH.touch()
        for k, v in updates.items():
            set_key(str(ENV_PATH), k, str(v))
            os.environ[k] = str(v)
        return True
    except Exception:
        # Fallback for read-only cloud containers (updates active session)
        for k, v in updates.items():
            os.environ[k] = str(v)
        return False


def inject_white_label_css(accent_color: str):
    css_content = ""
    if CSS_PATH.exists():
        css_content = CSS_PATH.read_text(encoding="utf-8")
    dynamic_vars = f":root {{ --brand-accent: {accent_color}; }}\n"
    st.markdown(f"<style>{dynamic_vars}\n{css_content}</style>", unsafe_allow_html=True)


brand_name = get_setting("APP_BRAND_NAME", "Outbound Mail Studio")
brand_tagline = get_setting("APP_TAGLINE", "Private Campaign & Automated Dispatch Engine")
accent_color = get_setting("APP_ACCENT_COLOR", "#2563EB")

st.set_page_config(
    page_title=brand_name,
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_white_label_css(accent_color)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "dispatch_logs" not in st.session_state:
    st.session_state["dispatch_logs"] = []


# ==========================================
# 1. PRIVATE ACCESS GATE (ONLY YOU)
# ==========================================
def render_login_screen():
    _, center_col, _ = st.columns([1.2, 1.3, 1.2])
    with center_col:
        st.markdown(
            f"""
            <div class="login-banner">
                <h2>🔐 {brand_name}</h2>
                <p>Restricted Workspace — Authorized Access Only</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            entered_pwd = st.text_input(
                "Workspace Access Password",
                type="password",
                placeholder="Enter your private access password..."
            )
            if st.button("Unlock Workspace", type="primary", use_container_width=True):
                expected_pwd = get_setting("DASHBOARD_ACCESS_PASSWORD", "AsifAdmin@2026")
                if hmac.compare_digest(entered_pwd, expected_pwd):
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Invalid access password.")


if not st.session_state["authenticated"]:
    render_login_screen()
    st.stop()


# ==========================================
# 2. UNIFIED SMTP / MIME EMAIL ENGINE
# ==========================================
def send_single_dispatched_email(
    smtp_server,
    sender: str,
    recipient: str,
    subject: str,
    body_content: str,
    is_html: bool,
    uploaded_files: list,
    dynamic_attachment: tuple | None = None
):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.attach(MIMEText(body_content, "html" if is_html else "plain", "utf-8"))

    # Attach static uploaded files
    for up_file in uploaded_files:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(up_file.getvalue())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{up_file.name}"')
        msg.attach(part)

    # Attach dynamically generated per-contact file (filename, bytes_data)
    if dynamic_attachment is not None:
        dyn_name, dyn_bytes = dynamic_attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(dyn_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{dyn_name}"')
        msg.attach(part)

    smtp_server.sendmail(sender, recipient, msg.as_string())


# ==========================================
# 3. SIDEBAR: CONTROLS, .ENV & WHITE-LABEL
# ==========================================
with st.sidebar:
    st.markdown(f"### ⚙️ {brand_name}")
    st.caption(f"Active Sender: `{get_setting('SENDER_EMAIL', 'Not set')}`")

    if st.button("🔒 Lock Workspace", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

    st.divider()

    with st.expander("🔑 .env Passwords & Sender", expanded=False):
        st.caption("Update your `.env` credentials directly from here.")
        new_sender = st.text_input(
            "Sender Gmail Address",
            value=get_setting("SENDER_EMAIL", "academy24.official@gmail.com")
        )
        new_gmail_pwd = st.text_input(
            "Gmail App Password (.env)",
            value=get_setting("GMAIL_APP_PASSWORD", ""),
            type="password"
        )
        new_access_pwd = st.text_input(
            "Dashboard Access Password (.env)",
            value=get_setting("DASHBOARD_ACCESS_PASSWORD", "AsifAdmin@2026"),
            type="password"
        )
        if st.button("Save Credentials to .env", type="primary", use_container_width=True):
            saved_to_disk = update_env_settings({
                "SENDER_EMAIL": new_sender.strip(),
                "GMAIL_APP_PASSWORD": new_gmail_pwd.strip(),
                "DASHBOARD_ACCESS_PASSWORD": new_access_pwd.strip()
            })
            if saved_to_disk:
                st.success("Updated .env file and active session!")
            else:
                st.info("Updated active session credentials.")

    with st.expander("🎨 White-Label Branding", expanded=False):
        wl_name = st.text_input("Tool Name", value=brand_name)
        wl_tagline = st.text_input("Subtitle / Tagline", value=brand_tagline)
        wl_color = st.color_picker("Primary Brand Accent", value=accent_color)
        if st.button("Apply White-Label Theme", use_container_width=True):
            update_env_settings({
                "APP_BRAND_NAME": wl_name.strip(),
                "APP_TAGLINE": wl_tagline.strip(),
                "APP_ACCENT_COLOR": wl_color
            })
            st.rerun()


# ==========================================
# 4. MAIN WORKSPACE HEADER
# ==========================================
st.markdown(
    f"""
    <div class="wl-topbar">
        <div>
            <div class="wl-brand-title">{brand_name}</div>
            <div class="wl-brand-sub">{brand_tagline}</div>
        </div>
        <div class="wl-status-pill">● SMTP TLS Ready</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_compose, tab_logs = st.tabs(["📤 Campaign & Dispatch Composer", "📊 Delivery Logs"])

with tab_compose:
    # Step A: Audience Selection (Single vs CSV Bulk)
    with st.container(border=True):
        st.subheader("1. Audience & Recipient Mode")
        mode = st.radio(
            "Select Dispatch Mode",
            ["Single Recipient", "CSV Contact List (Bulk Personalization)"],
            horizontal=True
        )

        recipients_df = pd.DataFrame()

        if mode == "Single Recipient":
            c1, c2, c3 = st.columns([1.2, 1.5, 1])
            with c1:
                single_name = st.text_input("Recipient Name", value="Asif")
            with c2:
                single_email = st.text_input("Recipient Email", value="asifmustafa2024@gmail.com")
            with c3:
                single_amount = st.text_input("Custom Value / Amount", value="250.00")

            if single_email.strip():
                recipients_df = pd.DataFrame([{
                    "name": single_name.strip() or "Client",
                    "email": single_email.strip(),
                    "amount": single_amount.strip()
                }])
        else:
            st.caption("Upload a CSV with columns like `name`, `email`, `amount` (or edit the sample table below).")
            uploaded_csv = st.file_uploader("Upload contacts.csv", type=["csv"])

            if uploaded_csv is not None:
                raw_df = pd.read_csv(uploaded_csv)
            else:
                raw_df = pd.DataFrame([
                    {"name": "Asif Client 1", "email": "asifmustafa2024+client1@gmail.com", "amount": "250.00"},
                    {"name": "Asif Client 2", "email": "asifmustafa2024+client2@gmail.com", "amount": "480.00"},
                ])

            recipients_df = st.data_editor(raw_df, num_rows="dynamic", use_container_width=True)

    # Step B: Content Composer & Live Side-by-Side Preview
    with st.container(border=True):
        st.subheader("2. Message & HTML Composer")
        fmt_col, subj_col = st.columns([1, 2.5])
        with fmt_col:
            format_choice = st.selectbox("Message Format", ["Rich HTML", "Plain Text"])
        with subj_col:
            subject_tpl = st.text_input(
                "Subject Line (supports {name}, {amount})",
                value="Update & Statement for {name}"
            )

        editor_col, preview_col = st.columns(2)

        default_html = """<div style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6;">
  <h2 style="color: #2563eb; margin-bottom: 8px;">Hello {name},</h2>
  <p>Thank you for working with us. Your current statement balance is <b>${amount}</b>.</p>
  <ul>
    <li>Status: <b>Confirmed</b></li>
    <li>Reference Account: <b>{email}</b></li>
  </ul>
  <p>Best regards,<br><b>Operations Team</b></p>
</div>"""

        default_plain = """Hello {name},

Thank you for working with us. Your current statement balance is ${amount}.
Reference Account: {email}

Best regards,
Operations Team"""

        with editor_col:
            body_tpl = st.text_area(
                "Message Body (use {name}, {email}, {amount} placeholders)",
                value=default_html if format_choice == "Rich HTML" else default_plain,
                height=260
            )

        with preview_col:
            st.caption("Live Rendered Preview (Row 1 Contact)")
            sample_row = (
                recipients_df.iloc[0].to_dict()
                if not recipients_df.empty
                else {"name": "Asif", "email": "asifmustafa2024@gmail.com", "amount": "250.00"}
            )
            safe_vars = {str(k): str(v) for k, v in sample_row.items()}

            class SafeDict(dict):
                def __missing__(self, key):
                    return "{" + key + "}"

            preview_subj = subject_tpl.format_map(SafeDict(safe_vars))
            preview_body = body_tpl.format_map(SafeDict(safe_vars))

            rendered_inner = (
                preview_body
                if format_choice == "Rich HTML"
                else f"<pre style='white-space: pre-wrap; font-family: inherit;'>{preview_body}</pre>"
            )
            st.markdown(
                f"""
                <div class="email-preview-box">
                    <div class="email-preview-meta">
                        <strong>To:</strong> {safe_vars.get('email', '')}<br>
                        <strong>Subject:</strong> {preview_subj}
                    </div>
                    {rendered_inner}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Step C: Static Attachments + Dynamic Per-Contact File Generator
    with st.container(border=True):
        st.subheader("3. Attachments & Personalized File Generator")
        att_col1, att_col2 = st.columns(2)

        with att_col1:
            static_files = st.file_uploader(
                "Static Attachments (sent to all recipients)",
                accept_multiple_files=True
            )

        with att_col2:
            enable_dyn_file = st.checkbox("Generate Unique Personalized File per Contact")
            dyn_filename_tpl = st.text_input(
                "Generated Filename Pattern",
                value="Statement_{name}.txt",
                disabled=not enable_dyn_file
            )
            dyn_content_tpl = st.text_area(
                "Generated File Content Template",
                value="STATEMENT FOR: {name}\nEMAIL: {email}\nAMOUNT DUE: ${amount}\nDATE: " + datetime.now().strftime("%Y-%m-%d"),
                height=105,
                disabled=not enable_dyn_file
            )

    # Step D: Timing, Scheduling & Execution
    with st.container(border=True):
        st.subheader("4. Timing & Dispatch Execution")
        t1, t2, t3 = st.columns([1, 1, 1.4])

        with t1:
            delay_seconds = st.number_input(
                "Delay Between Emails (seconds)",
                min_value=0,
                max_value=3600,
                value=2,
                step=1
            )
        with t2:
            schedule_mode = st.selectbox("Send Timing", ["Send Immediately", "Wait Until Specific Time Today"])
        with t3:
            target_time = st.time_input(
                "Scheduled Time (24h)",
                value=datetime.now().time(),
                disabled=(schedule_mode == "Send Immediately")
            )

        if st.button("🚀 Launch Email Dispatch", type="primary", use_container_width=True):
            sender_addr = get_setting("SENDER_EMAIL", "").strip()
            app_pwd = get_setting("GMAIL_APP_PASSWORD", "").strip()

            if not sender_addr or not app_pwd or app_pwd == "your_16_char_gmail_app_password":
                st.error("Please configure your Sender Gmail and 16-character App Password in the sidebar (.env Passwords & Sender).")
            elif recipients_df.empty or "email" not in recipients_df.columns:
                st.error("Please provide at least one valid recipient with an `email` column.")
            else:
                if schedule_mode == "Wait Until Specific Time Today":
                    status_box = st.empty()
                    while True:
                        now = datetime.now()
                        if now.hour == target_time.hour and now.minute == target_time.minute:
                            break
                        status_box.info(
                            f"⏳ Scheduled standby: Current time {now.strftime('%H:%M:%S')} — waiting for {target_time.strftime('%H:%M')}..."
                        )
                        time.sleep(5)
                    status_box.empty()

                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(recipients_df)

                class SafeDict(dict):
                    def __missing__(self, key):
                        return "{" + key + "}"

                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
                    server.starttls()
                    server.login(sender_addr, app_pwd)

                    for idx, row in recipients_df.iterrows():
                        row_vars = SafeDict({str(k): str(v) for k, v in row.to_dict().items()})
                        rec_email = str(row["email"]).strip()
                        if not rec_email or rec_email.lower() == "nan":
                            continue

                        final_subj = subject_tpl.format_map(row_vars)
                        final_body = body_tpl.format_map(row_vars)

                        dyn_payload = None
                        if enable_dyn_file:
                            safe_name = dyn_filename_tpl.format_map(row_vars).replace("/", "_").replace("\\", "_")
                            file_body = dyn_content_tpl.format_map(row_vars).encode("utf-8")
                            dyn_payload = (safe_name, file_body)

                        status_text.info(f"Sending ({idx + 1}/{total}) to {rec_email}...")
                        send_single_dispatched_email(
                            smtp_server=server,
                            sender=sender_addr,
                            recipient=rec_email,
                            subject=final_subj,
                            body_content=final_body,
                            is_html=(format_choice == "Rich HTML"),
                            uploaded_files=static_files or [],
                            dynamic_attachment=dyn_payload,
                        )

                        st.session_state["dispatch_logs"].append({
                            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Recipient": rec_email,
                            "Subject": final_subj,
                            "Format": format_choice,
                            "Personalized File": dyn_payload[0] if dyn_payload else "None",
                            "Status": "Sent"
                        })

                        progress_bar.progress(int(((idx + 1) / total) * 100))
                        if idx < total - 1 and delay_seconds > 0:
                            time.sleep(delay_seconds)

                    server.quit()
                    status_text.success(f"✅ Completed! Dispatched {total} email(s) successfully.")
                except Exception as exc:
                    st.error(f"SMTP Dispatch Error: {exc}")

with tab_logs:
    st.subheader("📊 Session Dispatch History")
    if st.session_state["dispatch_logs"]:
        logs_df = pd.DataFrame(st.session_state["dispatch_logs"])
        st.dataframe(logs_df, use_container_width=True, hide_index=True)
        st.download_button(
            label="📥 Export Delivery Log (.csv)",
            data=logs_df.to_csv(index=False).encode("utf-8"),
            file_name=f"dispatch_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No emails dispatched yet in this session.")

st.markdown(
    f'<div class="wl-footer">{brand_name} • Private Automated Communications Workspace</div>',
    unsafe_allow_html=True,
)