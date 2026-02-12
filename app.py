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

from shiny import App, Inputs, Outputs, Session, render, ui

app_ui = ui.page_fluid(
    ui.h2("OAuth Credentials Test"),
    ui.hr(),
    ui.h3("Environment"),
    ui.output_text_verbatim("env_info"),
    ui.hr(),
    ui.h3("Credentials Response"),
    ui.output_text_verbatim("credentials_result"),
    ui.hr(),
    ui.h3("Raw HTTP Test"),
    ui.output_text_verbatim("raw_http_result"),
    ui.hr(),
    ui.input_action_button("refresh", "Refresh"),
)


def server(i: Inputs, o: Outputs, session: Session):
    @render.text
    @i.refresh
    def env_info():
        connect_server = os.environ.get("CONNECT_SERVER", "<not set>")
        posit_product = os.environ.get("POSIT_PRODUCT", "<not set>")
        # Show all CONNECT_* env vars (values redacted for safety)
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
    @i.refresh
    def credentials_result():
        try:
            from posit import connect

            client = connect.Client()
            session_token = session.http_conn.headers.get(
                "Posit-Connect-User-Session-Token"
            )

            lines = [f"User session token present: {session_token is not None}"]

            if session_token:
                lines.append(
                    f"User session token (first 20 chars): {session_token[:20]}..."
                )

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

            return "\n".join(lines)
        except Exception as e:
            return f"Failed to initialize posit-sdk client:\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}"

    @render.text
    @i.refresh
    def raw_http_result():
        """Make a raw HTTP request to the credentials endpoint to see exactly what happens."""
        import urllib.request
        import urllib.error

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
