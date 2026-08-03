const API_BASE = "/api";

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = `${url} -> ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (e) {
      // ignore, use default detail
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

// TODO: build the real frontend here, using fetchJSON(`${API_BASE}/...`)
// to talk to the backend once routers exist.
