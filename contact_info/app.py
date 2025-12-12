from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Dict, Tuple

import streamlit as st
import streamlit_authenticator as stauth


# Keep this page self-contained so it can be dropped in as a module.
st.set_page_config(page_title="Knitec IQ | Contact Info", layout="wide")

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
CSS_PATH = ASSETS_DIR / "css" / "style.css"
HERO_IMAGE = ASSETS_DIR / "images" / "home_background.png"
LOGO_IMAGE = ASSETS_DIR / "images" / "logo.png"

FIELD_META: Tuple[Tuple[str, str, str], ...] = (
    ("name", "Name", "Jane Doe"),
    ("address", "Address", "123 Main St"),
    ("city", "City", "Seattle"),
    ("state", "State", "WA"),
    ("zip", "Zip", "98101"),
    ("contact", "Contact", "Primary phone or email"),
    ("contact2", "Contact 2", "Secondary phone or email"),
)


def _to_plain(obj):
    """Convert secrets mappings to plain dicts/lists to avoid mutation issues."""
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    try:
        return {k: _to_plain(v) for k, v in obj.items()}
    except Exception:
        return obj


def require_auth() -> None:
    """Authenticate the user; stop rendering if unauthenticated."""
    auth_config = st.secrets.get("auth")
    if not auth_config:
        st.error("Auth configuration missing in secrets.")
        st.stop()

    auth_config = _to_plain(auth_config)
    authenticator = stauth.Authenticate(
        auth_config["credentials"],
        auth_config["cookie"]["name"],
        auth_config["cookie"]["key"],
        auth_config["cookie"]["expiry_days"],
        auth_config.get("preauthorized", {}),
    )

    name, auth_status, username = authenticator.login(
        fields={"Form name": "Login"},
        location="main",
    )

    if auth_status is False:
        st.error("Invalid username or password.")
        st.stop()
    elif auth_status is None:
        st.warning("Please enter your credentials.")
        st.stop()
    else:
        authenticator.logout("Logout", "sidebar")


def _as_data_uri(path: Path) -> str:
    """Return a data URI for the given asset."""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


def inject_branding() -> Dict[str, str]:
    """Inject CSS with inlined images; return data URIs for reuse."""
    logo_uri = _as_data_uri(LOGO_IMAGE)
    hero_uri = _as_data_uri(HERO_IMAGE)

    css = CSS_PATH.read_text()
    css = css.replace("../images/home_background.png", hero_uri)
    css = css.replace("../images/logo.png", logo_uri)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    # Provide a small helper style for the logo in the header.
    st.markdown(
        f"""
        <style>
          .brand-mark img {{
            content: url("{logo_uri}");
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return {"logo": logo_uri, "hero": hero_uri}


def render_header(logo_uri: str) -> None:
    st.markdown(
        f"""
        <header class="header-bar">
          <div class="brand-mark">
            <img src="{logo_uri}" alt="Knitec logo">
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero-section">
          <div class="hero-overlay"></div>
          <div class="hero-content">
            <h1>Property &amp; Contact Information</h1>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_form() -> None:
    def _clear_form() -> None:
        for key, _, _ in FIELD_META:
            st.session_state[f"contact_{key}"] = ""

    st.markdown('<div class="form-wrapper">', unsafe_allow_html=True)
    with st.form("knitec_contact_form"):
        col_a, col_b = st.columns(2, gap="medium")
        values = {}

        # Collect inputs in a grid-like layout.
        for idx, (key, label, placeholder) in enumerate(FIELD_META):
            target_col = col_a if idx % 2 == 0 else col_b
            values[key] = target_col.text_input(
                label,
                key=f"contact_{key}",
                placeholder=placeholder,
            )

        action_a, action_b = st.columns(2, gap="small")
        submitted = action_a.form_submit_button(
            "Submit",
            type="primary",
        )
        cleared = action_b.form_submit_button(
            "Clear",
            type="secondary",
            on_click=_clear_form,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        sanitized = {k: (v or "").strip() for k, v in values.items()}
        errors = validate_inputs(sanitized)
        if errors:
            st.error("Please fix the following:\n- " + "\n- ".join(errors))
            return

        st.session_state["contact_info"] = sanitized
        st.session_state["contact_info_submitted"] = True
        st.success("Contact info captured. Redirecting to chatbot...")
        navigate_to_chat()


def validate_inputs(values: Dict[str, str]) -> list[str]:
    """Return a list of validation error messages."""
    errors = []

    required_keys = ("name", "address", "city", "state", "zip", "contact")
    for key in required_keys:
        if not values.get(key):
            errors.append(f"{key.title()} is required.")

    state_val = values.get("state", "")
    if state_val and not re.fullmatch(r"[A-Za-z]{2}", state_val):
        errors.append("State must be a 2-letter code (e.g., WA).")

    zip_val = values.get("zip", "")
    if zip_val and not re.fullmatch(r"\d{5}(?:-\d{4})?$", zip_val):
        errors.append("Zip must be 5 digits or ZIP+4 (e.g., 98101 or 98101-1234).")

    contact_val = values.get("contact", "")
    if contact_val and not (_looks_like_email(contact_val) or _looks_like_phone(contact_val)):
        errors.append("Contact must be an email or phone number.")

    contact2_val = values.get("contact2", "")
    if contact2_val and not (_looks_like_email(contact2_val) or _looks_like_phone(contact2_val)):
        errors.append("Contact 2 must be an email or phone number.")

    return errors


def _looks_like_email(text: str) -> bool:
    return bool(re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", text))


def _looks_like_phone(text: str) -> bool:
    digits = re.sub(r"\\D", "", text)
    return 7 <= len(digits) <= 15


def navigate_to_chat() -> None:
    """
    Try to jump to the chatbot page automatically. Falls back to a JS redirect.
    Works when both pages run in the same Streamlit instance.
    """
    target_slug = "Chat_with_KnitecIQ"
    target_path = "pages/02_Chat_With_KnitecIQ.py"

    if hasattr(st, "switch_page"):
        for target in (
            target_path,
            target_slug,
            "02_Chat_With_KnitecIQ.py",
            "02_Chat_With_KnitecIQ",
            "pages/02_chat.py",
            "pages/chat.py",
            "app_chat.py",
            "app_chat",
            "../app_chat.py",
            "../app_chat",
        ):
            try:
                st.switch_page(target)
                return
            except Exception:
                continue

    # Try queryparam navigation in multipage mode.
    try:
        st.experimental_set_query_params(page=target_slug)
        st.experimental_rerun()
        return
    except Exception:
        pass

    # Fallback: client-side redirect to a likely chatbot route.
    chat_url = "https://kniteciq-demo.streamlit.app/Chat_with_KnitecIQ"
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="0; url={chat_url}">
        <p>Redirecting to chat...</p>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "If you are not redirected, open the Chat page (02_Chat_With_KnitecIQ) in this instance."
    )
    st.markdown(
        f'💬 [Open chat now]({chat_url}) &nbsp;|&nbsp; '
        '[Contact page](https://kniteciq-demo.streamlit.app)',
        unsafe_allow_html=True,
    )


def main() -> None:
    require_auth()
    brand_uris = inject_branding()
    render_header(brand_uris["logo"])
    render_hero()
    render_form()


if __name__ == "__main__":
    main()
