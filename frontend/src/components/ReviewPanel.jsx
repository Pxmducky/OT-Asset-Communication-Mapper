import { useCallback, useEffect, useState } from "react";

import { getErrorMessage } from "../services/api";
import { findingApi } from "../services/scanApi";

function confidenceClass(c) {
  if (c >= 70) return "high";
  if (c >= 40) return "mid";
  return "low";
}

export default function ReviewPanel({ onDataChanged }) {
  const [findings, setFindings] = useState([]);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try {
      setFindings(await findingApi.list("review"));
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function approve(id) {
    setBusyId(id);
    setError(null);
    try {
      await findingApi.apply(id);
      await load();
      onDataChanged?.();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  }

  async function discard(id) {
    setBusyId(id);
    setError(null);
    try {
      await findingApi.discard(id);
      await load();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="review-panel">
      {error && <div className="scan-msg error">{error}</div>}

      <p className="scan-hint">
        Estos equipos se detectaron con confianza media: no se guardaron solos. Revisa y
        decide si los agregas al inventario.
      </p>

      {findings.length === 0 && <p className="empty">No hay nada por revisar. 🎉</p>}

      <div className="review-list">
        {findings.map((f) => (
          <div key={f.id} className="review-card">
            <div className="review-head">
              <div>
                <strong>{f.hostname || f.ip}</strong>
                <small>
                  {f.ip} {f.detected_os ? `· ${f.detected_os}` : ""} {f.vendor ? `· ${f.vendor}` : ""}
                </small>
              </div>
              <span className={`confidence-badge ${confidenceClass(f.confidence)}`}>
                {f.confidence}%
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

            <div className="review-actions">
              <button
                type="button"
                className="button primary small"
                disabled={busyId === f.id}
                onClick={() => approve(f.id)}
              >
                ✓ Aprobar
              </button>
              <button
                type="button"
                className="button danger small"
                disabled={busyId === f.id}
                onClick={() => discard(f.id)}
              >
                ✗ Descartar
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}