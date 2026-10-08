import { useEffect, useState } from "react";

import { getErrorMessage } from "../services/api";
import { findingApi } from "../services/scanApi";

function parseSummary(value) {
  try {
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

function confClass(c) {
  if (c >= 70) return "high";
  if (c >= 40) return "mid";
  return "low";
}

export default function ScanDetail({ scan, onLaunch, onBack }) {
  const [findings, setFindings] = useState([]);
  const [error, setError] = useState(null);

  const summary = parseSummary(scan.summary);
  const advice = summary?.advice;
  const recommendations = summary?.recommendations ?? [];

  useEffect(() => {
    let alive = true;
    findingApi
      .forScan(scan.id)
      .then((d) => alive && setFindings(d))
      .catch((e) => alive && setError(getErrorMessage(e)));
    return () => {
      alive = false;
    };
  }, [scan.id]);

  return (
    <div className="scan-detail">
      <button type="button" className="link-back" onClick={onBack}>
        ← Volver a la cola
      </button>

      <div className="scan-detail-head">
        <h3>
          Escaneo #{scan.id} · {scan.scan_profile}
        </h3>
        <small>
          {scan.target} · {new Date(scan.finished_at ?? scan.queued_at).toLocaleString()}
        </small>
      </div>

      {error && <div className="scan-msg error">{error}</div>}
      {advice && <div className="scan-msg info">⚠ {advice}</div>}

      {recommendations.length > 0 && (
        <div className="reco-block">
          <h4>Recomendaciones</h4>
          <p className="scan-hint">
            Equipos sin confirmar: te sugerimos correr el escaneo específico para confirmarlos.
          </p>
          <ul className="reco-list">
            {recommendations.map((r) => (
              <li key={r.ip}>
                <div>
                  <strong>{r.ip}</strong> — probablemente <b>{r.suggested_label}</b>{" "}
                  <span className={`confidence-badge ${confClass(r.score)}`}>{r.score}%</span>
                </div>
                <button
                  type="button"
                  className="button primary small"
                  onClick={() => onLaunch(r.ip, r.suggested_profile)}
                >
                  Escanear como {r.suggested_label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <h4>Equipos encontrados ({findings.length})</h4>
      <div className="host-cards">
        {findings.map((f) => (
          <div key={f.id} className="host-card">
            <div className="host-head">
              <div>
                <strong>{f.hostname || f.ip}</strong>
                <small>
                  {f.ip} {f.detected_os ? `· ${f.detected_os}` : ""} {f.vendor ? `· ${f.vendor}` : ""}
                </small>
              </div>
              <div className="host-type">
                <span className="type-name">{f.winner_label ?? "Desconocido"}</span>
                <span className={`confidence-badge ${confClass(f.confidence)}`}>{f.confidence}%</span>
              </div>
            </div>

            <div className="host-status">
              <span className={`status-badge ${f.applied ? "completed" : "pending"}`}>
                {f.applied ? "✓ En inventario" : "Por revisar"}
              </span>
            </div>

            {f.open_ports?.length > 0 && (
              <div className="review-ports">
                {f.open_ports.map((p) => (
                  <span key={p} className="port-chip">
                    {p}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {findings.length === 0 && <p className="empty">Sin equipos detectados.</p>}
      </div>
    </div>
  );
}