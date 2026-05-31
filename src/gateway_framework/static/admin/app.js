const state = {
  adminKey: "",
};

function setStatus(id, message, isError = false) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = message;
  el.style.color = isError ? "#a33838" : "#607567";
}

function adminHeaders() {
  const headers = {};
  if (state.adminKey) {
    headers["x-admin-key"] = state.adminKey;
  }
  return headers;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...adminHeaders(),
      ...(options.headers || {}),
    },
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  if (!response.ok) {
    throw new Error(payload.detail || payload.error || `request_failed_${response.status}`);
  }

  return payload;
}

async function refreshDashboard() {
  const data = await requestJson("/admin/dashboard");
  document.getElementById("metricRoutes").textContent = String(data.routes_count);
  document.getElementById("metricUpstreams").textContent = String(data.upstreams.length);
  document.getElementById("metricKeyGuard").textContent = data.require_api_key ? "Enabled" : "Disabled";
  document.getElementById("metricAdminAuth").textContent = data.admin_api_key_required ? "Required" : "Open";

  await refreshRoutes();
  await refreshKeys();
}

async function refreshRoutes() {
  const items = await requestJson("/admin/routes");
  const list = document.getElementById("routesList");
  list.innerHTML = "";
  for (const route of items) {
    const li = document.createElement("li");
    const methods = Array.isArray(route.methods) ? route.methods.join(",") : "";
    li.innerHTML = `<span>${route.path}</span><span class="pill">${methods}</span>`;
    list.appendChild(li);
  }
}

async function loadConfig() {
  const data = await requestJson("/admin/config");
  document.getElementById("configText").value = data.yaml || "";
  setStatus("configStatus", "Configuration loaded.");
}

async function saveConfig() {
  const yaml = document.getElementById("configText").value;
  await requestJson("/admin/config", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ yaml }),
  });
  setStatus("configStatus", "Configuration saved and reloaded.");
  await refreshDashboard();
}

function renderKeyItem(item) {
  const li = document.createElement("li");
  const left = document.createElement("span");
  left.textContent = `${item.name} (${item.prefix})`;

  const right = document.createElement("div");
  right.className = "actions";

  const statePill = document.createElement("span");
  statePill.className = "pill";
  statePill.textContent = item.revoked ? "revoked" : "active";
  right.appendChild(statePill);

  if (!item.revoked) {
    const revoke = document.createElement("button");
    revoke.className = "btn danger";
    revoke.textContent = "Revoke";
    revoke.addEventListener("click", async () => {
      await requestJson(`/admin/api-keys/${item.id}`, { method: "DELETE" });
      await refreshKeys();
    });
    right.appendChild(revoke);
  }

  li.appendChild(left);
  li.appendChild(right);
  return li;
}

async function refreshKeys() {
  const data = await requestJson("/admin/api-keys");
  const list = document.getElementById("keysList");
  list.innerHTML = "";

  for (const item of data.keys || []) {
    list.appendChild(renderKeyItem(item));
  }
}

async function createKey() {
  const input = document.getElementById("apiKeyName");
  const name = input.value.trim() || "unnamed";
  const data = await requestJson("/admin/api-keys", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });

  setStatus("newKeyValue", `New API key (shown once): ${data.api_key}`);
  input.value = "";
  await refreshKeys();
}

function bindEvents() {
  document.getElementById("saveAdminKeyBtn").addEventListener("click", async () => {
    state.adminKey = document.getElementById("adminKey").value.trim();
    try {
      await refreshDashboard();
      setStatus("newKeyValue", "Admin key accepted.");
    } catch (err) {
      setStatus("newKeyValue", `Admin key check failed: ${err.message}`, true);
    }
  });

  document.getElementById("loadConfigBtn").addEventListener("click", async () => {
    try {
      await loadConfig();
    } catch (err) {
      setStatus("configStatus", `Load failed: ${err.message}`, true);
    }
  });

  document.getElementById("saveConfigBtn").addEventListener("click", async () => {
    try {
      await saveConfig();
    } catch (err) {
      setStatus("configStatus", `Save failed: ${err.message}`, true);
    }
  });

  document.getElementById("createKeyBtn").addEventListener("click", async () => {
    try {
      await createKey();
    } catch (err) {
      setStatus("newKeyValue", `Create failed: ${err.message}`, true);
    }
  });

  document.getElementById("refreshKeysBtn").addEventListener("click", async () => {
    try {
      await refreshKeys();
    } catch (err) {
      setStatus("newKeyValue", `Refresh failed: ${err.message}`, true);
    }
  });

  document.getElementById("refreshRoutesBtn").addEventListener("click", async () => {
    try {
      await refreshRoutes();
    } catch (err) {
      setStatus("newKeyValue", `Routes failed: ${err.message}`, true);
    }
  });
}

async function bootstrap() {
  bindEvents();
  try {
    await Promise.all([loadConfig(), refreshDashboard()]);
  } catch (err) {
    setStatus("configStatus", `Initial load failed: ${err.message}`, true);
  }
}

bootstrap();
