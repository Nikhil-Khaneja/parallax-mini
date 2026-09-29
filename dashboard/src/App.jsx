import React, { useEffect, useState } from "react";

const POLL_MS = 2000;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) return null;
  return r.json();
}

function health(score) {
  if (score >= 0.8) return { label: "anomalous", color: "#c0392b" };
  if (score >= 0.4) return { label: "watch", color: "#e67e22" };
  return { label: "healthy", color: "#27ae60" };
}

export default function App() {
  const [vehicles, setVehicles] = useState([]);
  const [campaigns, setCampaigns] = useState([]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const v = await getJSON("/vehicles");
      const c = await getJSON("/ota/campaigns");
      if (alive) {
        if (v) setVehicles(v);
        if (c) setCampaigns(c);
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h1>Parallax Mini — Fleet Dashboard</h1>

      <h2>Vehicles ({vehicles.length})</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {["VIN", "Firmware", "Health", "Score", "Last seen"].map((h) => (
              <th key={h} style={{ textAlign: "left", borderBottom: "2px solid #ccc", padding: 6 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {vehicles.map((v) => {
            const h = health(v.health_score || 0);
            return (
              <tr key={v.vin}>
                <td style={{ padding: 6 }}>{v.vin}</td>
                <td style={{ padding: 6 }}>{v.fw_version}</td>
                <td style={{ padding: 6, color: h.color, fontWeight: 600 }}>{h.label}</td>
                <td style={{ padding: 6 }}>{(v.health_score || 0).toFixed(2)}</td>
                <td style={{ padding: 6 }}>{v.last_seen ? new Date(v.last_seen).toLocaleTimeString() : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <h2 style={{ marginTop: 32 }}>OTA Campaigns ({campaigns.length})</h2>
      {campaigns.length === 0 && <p>No campaigns yet.</p>}
      {campaigns.map((c) => (
        <div key={c.campaign_id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <strong>{c.campaign_id}</strong> → fw {c.fw_version} — state:{" "}
          <span style={{ fontWeight: 600 }}>{c.state}</span>
          <ul>
            {c.vehicles.map((cv) => (
              <li key={cv.vin}>
                {cv.vin}: {cv.status}{cv.reason ? ` (${cv.reason})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
