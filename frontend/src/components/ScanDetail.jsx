import { useCallback, useEffect, useState } from "react";

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

const LEVEL_LABEL = { strong: "fuerte", medium: "protocolo", weak: "servicio", os: "SO" };

export default function ScanDetail({ scan, assets, onLaunch, onBack, onDataChanged }) {
  const [findings, setFindings] = useState([]);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const summary = parseSummary(scan.summary);
  const advice = summary?.advice;
  const recommendations = summary?.recommendations ?? [];
  const assetsById = new Map((assets ?? []).map((a) => [a.id, a]));

  const load = useCallback(() => {
    findingApi
      .forScan(scan.id)
      .then(setFindings)
      .catch((e) => setError(getErrorMessage(e)));
  }, [scan.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function reclassify(f) {
    setBusyId(f.id);
    setError(null);
    try {
      await findingApi.reclassify(f.id);
      load();
      onDataChanged?.();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="scan-detail">
      <button type="button" className="link-back" onClick={onBack}>
        ← Volver a la cola
      </button>

      <div className="scan-detail-head">
        <h3>Escaneo #{scan.id} · {scan.scan_profile}</h3>
        <small>{scan.target} · {new Date(scan.finished_at ?? scan.queued_at).toLocaleString()}</small>
      </div>

      {error && <div className="scan-msg error">{error}</div>}
      {advice && <div className="scan-msg info">⚠ {advice}</div>}

      {recommendations.length > 0 && (
        <div className="reco-block">
          <h4>Recomendaciones</h4>
          <ul className="reco-list">
            {recommendations.map((r) => (
              <li key={r.ip}>
                <div>
                  <strong>{r.ip}</strong> — probablemente <b>{r.suggested_label}</b>{" "}
                  <span className={`confidence-badge ${confClass(r.score)}`}>{r.score}%</span>
                </div>
                <button type="button" className="button primary small" onClick={() => onLaunch(r.ip, r.suggested_profile)}>
                  Escanear como {r.suggested_label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <h4>Equipos encontrados ({findings.length})</h4>
      <div className="host-cards">
        {findings.map((f) => {
          const current = f.matched_asset_id ? assetsById.get(f.matched_asset_id) : null;
          const canReclassify =
            f.confidence >= 70 && current && f.winner_type && current.asset_type !== f.winner_type;
          const identity = (f.fingerprints ?? []).filter((g) => g.kind === "identity");
          const services = (f.fingerprints ?? []).filter((g) => g.kind !== "identity");

          return (
            <div key={f.id} className="host-card">
              <div className="host-head">
                <div>
                  <strong>{f.hostname || f.ip}</strong>
                  <small>{f.ip} {f.detected_os ? `· ${f.detected_os}` : ""} {f.vendor ? `· ${f.vendor}` : ""}</small>
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
                {canReclassify && (
                  <button
                    type="button"
                    className="button restore small reclassify-btn"
                    disabled={busyId === f.id}
                    onClick={() => reclassify(f)}
                  >
                    ↻ Actualizar tipo a {f.winner_label}
                  </button>
                )}
              </div>

              {identity.length > 0 && (
                <div className="fp-block">
                  <span className="fp-title">Identidad</span>
                  {identity.map((g) => (
                    <div key={g.label} className="fp-identity">
                      {g.label}
                      {g.detail && <small>{g.detail}</small>}
                    </div>
                  ))}
                </div>
              )}

              {f.evidences?.length > 0 && (
                <div className="fp-block">
                  <span className="fp-title">Evidencias</span>
                  <div className="ev-list">
                    {f.evidences.map((e, i) => (
                      <div key={i} className={`ev-row ev-${e.level}`}>
                        <span className="ev-level">{LEVEL_LABEL[e.level] ?? e.level}</span>
                        <span className="ev-label">{e.label}</span>
                        <span className="ev-points">+{e.points}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {services.length > 0 && (
                <div className="fp-block">
                  <span className="fp-title">Otros servicios detectados</span>
                  <div className="review-ports">
                    {services.map((g) => (
                      <span key={g.label} className="port-chip">{g.label}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {findings.length === 0 && <p className="empty">Sin equipos detectados.</p>}
      </div>
    </div>
  );
}