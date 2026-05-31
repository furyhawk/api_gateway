from __future__ import annotations

from fastapi import HTTPException, Request


def require_admin_access(request: Request) -> None:
    expected_key = request.app.state.admin_api_key
    if not expected_key:
        return

    presented = request.headers.get("x-admin-key")
    if presented != expected_key:
        raise HTTPException(status_code=401, detail="invalid_admin_api_key")


def render_admin_portal() -> str:
    return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Gateway Admin Portal</title>
    <style>
      :root {
        --bg: #f5f7f2;
        --panel: #ffffff;
        --text: #1f2d24;
        --muted: #5d6f63;
        --accent: #0d7f5f;
        --warn: #a23b3b;
        --border: #d9e2d9;
      }
      body {
        margin: 0;
        font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
        background: radial-gradient(circle at 0 0, #dceadf, var(--bg));
        color: var(--text);
      }
      .wrap {
        max-width: 1100px;
        margin: 0 auto;
        padding: 24px;
      }
      .card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
      }
      h1, h2 { margin: 0 0 10px; }
      textarea, input {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px;
        font-family: "IBM Plex Mono", monospace;
      }
      textarea { min-height: 220px; }
      button {
        background: var(--accent);
        color: #fff;
        border: 0;
        border-radius: 8px;
        padding: 10px 14px;
        cursor: pointer;
        margin-right: 8px;
      }
      button.warn { background: var(--warn); }
      .row { display: flex; gap: 8px; align-items: center; }
      .hint { color: var(--muted); font-size: 0.92rem; }
      code { background: #f0f5ef; padding: 2px 6px; border-radius: 4px; }
      ul { padding-left: 18px; }
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <h1>Gateway Admin Portal</h1>
      <p class=\"hint\">Use header <code>x-admin-key</code> for protected actions when ADMIN_API_KEY is configured.</p>

      <div class=\"card\">
        <h2>Access</h2>
        <input id=\"adminKey\" type=\"password\" placeholder=\"Admin API key (optional if server does not require it)\" />
      </div>

      <div class=\"card\">
        <h2>Dashboard</h2>
        <button onclick=\"refreshDashboard()\">Refresh</button>
        <pre id=\"dashboard\" class=\"hint\">Loading...</pre>
      </div>

      <div class=\"card\">
        <h2>Configuration Editor</h2>
        <p class=\"hint\">Edits are validated and written to disk. Structural route changes may require app restart.</p>
        <button onclick=\"loadConfig()\">Load</button>
        <button onclick=\"saveConfig()\">Save</button>
        <textarea id=\"configText\"></textarea>
      </div>

      <div class=\"card\">
        <h2>API Key Management</h2>
        <div class=\"row\">
          <input id=\"apiKeyName\" placeholder=\"New key name (for example dashboard-client)\" />
          <button onclick=\"createApiKey()\">Create Key</button>
        </div>
        <p class=\"hint\" id=\"newKey\"></p>
        <ul id=\"apiKeys\"></ul>
      </div>
    </div>

    <script>
      function headers() {
        const k = document.getElementById('adminKey').value.trim();
        return k ? {'x-admin-key': k} : {};
      }

      async function refreshDashboard() {
        const res = await fetch('/admin/dashboard', {headers: headers()});
        const data = await res.json();
        document.getElementById('dashboard').textContent = JSON.stringify(data, null, 2);
        await listApiKeys();
      }

      async function loadConfig() {
        const res = await fetch('/admin/config', {headers: headers()});
        const data = await res.json();
        document.getElementById('configText').value = data.yaml;
      }

      async function saveConfig() {
        const body = {yaml: document.getElementById('configText').value};
        const res = await fetch('/admin/config', {
          method: 'PUT',
          headers: {...headers(), 'content-type': 'application/json'},
          body: JSON.stringify(body),
        });
        const data = await res.json();
        alert(JSON.stringify(data));
        await refreshDashboard();
      }

      async function listApiKeys() {
        const res = await fetch('/admin/api-keys', {headers: headers()});
        const data = await res.json();
        const list = document.getElementById('apiKeys');
        list.innerHTML = '';
        for (const item of data.keys) {
          const li = document.createElement('li');
          li.textContent = `${item.name} (${item.prefix}) revoked=${item.revoked}`;
          const btn = document.createElement('button');
          btn.textContent = 'Revoke';
          btn.className = 'warn';
          btn.onclick = async () => {
            await fetch(`/admin/api-keys/${item.id}`, {method: 'DELETE', headers: headers()});
            await listApiKeys();
          };
          li.appendChild(btn);
          list.appendChild(li);
        }
      }

      async function createApiKey() {
        const name = document.getElementById('apiKeyName').value.trim() || 'unnamed';
        const res = await fetch('/admin/api-keys', {
          method: 'POST',
          headers: {...headers(), 'content-type': 'application/json'},
          body: JSON.stringify({name}),
        });
        const data = await res.json();
        document.getElementById('newKey').textContent = `New API key (shown once): ${data.api_key}`;
        await listApiKeys();
      }

      loadConfig();
      refreshDashboard();
    </script>
  </body>
</html>
"""
