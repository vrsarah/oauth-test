"""
Test app to verify the CONNECT_SERVER listener and OAuth credentials endpoint.

Deploys as a Shiny for Python app on Posit Connect Cloud.
Displays diagnostic info about:
- Whether CONNECT_SERVER env var is set
- Whether the credentials endpoint is reachable
- What the response looks like
"""

import os
import json
import traceback
import urllib.request
import urllib.error

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

app_ui = ui.page_fluid(
    ui.h2("OAuth Credentials Test"),
    ui.input_action_button("refresh", "Refresh All"),
    ui.hr(),
    ui.h3("Environment"),
    ui.output_text_verbatim("env_info"),
    ui.hr(),
    ui.h3("Credentials Response (posit-sdk)"),
    ui.output_text_verbatim("credentials_result"),
    ui.hr(),
    ui.h3("Raw HTTP Test"),
    ui.output_text_verbatim("raw_http_result"),
)


def server(i: Inputs, o: Outputs, session: Session):
    @render.text
    def env_info():
        # Take dependency on refresh button, but also render on first load
        i.refresh()

        connect_server = os.environ.get("CONNECT_SERVER", "<not set>")
        posit_product = os.environ.get("POSIT_PRODUCT", "<not set>")
        connect_vars = {
            k: (v[:20] + "..." if len(v) > 20 else v)
            for k, v in os.environ.items()
            if k.startswith("CONNECT_") or k.startswith("POSIT_")
        }
        lines = [
            f"CONNECT_SERVER = {connect_server}",
            f"POSIT_PRODUCT  = {posit_product}",
            "",
            "All CONNECT_*/POSIT_* env vars:",
            json.dumps(connect_vars, indent=2),
        ]
        return "\n".join(lines)

    @render.text
    def credentials_result():
        i.refresh()

        lines = []
        try:
            from posit import connect

            session_token = session.http_conn.headers.get(
                "Posit-Connect-User-Session-Token"
            )
            lines.append(f"User session token present: {session_token is not None}")
            if session_token:
                lines.append(
                    f"User session token (first 20 chars): {session_token[:20]}..."
                )

            # Show all headers for debugging
            lines.append("")
            lines.append("All request headers:")
            for k, v in session.http_conn.headers.items():
                val = v[:30] + "..." if len(v) > 30 else v
                lines.append(f"  {k}: {val}")

            # Try initializing the client
            try:
                client = connect.Client()
                lines.append(f"\nClient initialized OK (url={client.cfg.url})")
            except Exception as e:
                lines.append(f"Client() init error: {type(e).__name__}: {e}")
                lines.append(traceback.format_exc())
                return "\n".join(lines)

            # Try get_credentials (viewer OAuth)
            try:
                credentials = client.oauth.get_credentials(session_token)
                lines.append("")
                lines.append("get_credentials() response:")
                lines.append(json.dumps(credentials, indent=2, default=str))
            except Exception as e:
                lines.append("")
                lines.append(f"get_credentials() error: {type(e).__name__}: {e}")

            # Try get_content_credentials (service account OAuth)
            try:
                content_credentials = client.oauth.get_content_credentials()
                lines.append("")
                lines.append("get_content_credentials() response:")
                lines.append(
                    json.dumps(content_credentials, indent=2, default=str)
                )
            except Exception as e:
                lines.append("")
                lines.append(
                    f"get_content_credentials() error: {type(e).__name__}: {e}"
                )

        except Exception as e:
            lines.append(
                f"Unexpected error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
            )

        return "\n".join(lines)

    @render.text
    def raw_http_result():
        i.refresh()

        connect_server = os.environ.get("CONNECT_SERVER")
        if not connect_server:
            return "CONNECT_SERVER not set - cannot make raw HTTP request"

        url = f"{connect_server}/__api__/v1/oauth/integrations/credentials"
        lines = [f"POST {url}", ""]

        try:
            req = urllib.request.Request(url, method="POST", data=b"")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                lines.append(f"Status: {resp.status}")
                lines.append(f"Headers: {dict(resp.headers)}")
                lines.append(f"Body: {body}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else "<no body>"
            lines.append(f"HTTP Error: {e.code}")
            lines.append(f"Body: {body}")
        except Exception as e:
            lines.append(f"Error: {type(e).__name__}: {e}")

        return "\n".join(lines)


app = App(app_ui, server)
