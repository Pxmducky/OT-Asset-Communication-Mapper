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

const LEVEL_LABEL = {
  control: "control", product: "producto", signal: "señal", os: "SO",
  // compatibilidad con hallazgos anteriores a V2
  strong: "fuerte", medium: "protocolo", weak: "servicio",
};

// Claves conocidas de la evidencia, en el orden en que se muestran
const DETAIL_KEYS = [
  ["module type", "Tipo de módulo"],
  ["device type", "Tipo de dispositivo"],
  ["product", "Producto"],
  ["module", "Módulo (n.º de pedido)"],
  ["basic hardware", "Hardware base"],
  ["vendor", "Fabricante"],
  ["o", "Organización (certificado)"],
  ["llave", "Llave del certificado"],
  ["firma", "Firma del certificado"],
  ["vence", "Vigencia del certificado"],
  ["debilidades", "Debilidades"],
  ["version", "Versión / firmware"],
  ["basic firmware", "Firmware"],
  ["revision", "Revisión"],
  ["system name", "Nombre del sistema"],
  ["plant identification", "Identificación de planta"],
  ["serial number", "Número de serie"],
  ["copyright", "Copyright"],
];
const KEY_LABEL = Object.fromEntries(DETAIL_KEYS);
const KEY_ORDER = Object.fromEntries(DETAIL_KEYS.map(([k], i) => [k, i]));

/** "Clave: valor; Clave=valor; texto" → filas ordenadas [{label, value}] */
function parseDetail(detail) {
  if (!detail) return [];
  return detail
    .split(/;\s*/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part, i) => {
      const m = part.match(/^([^:=]{1,40})\s*[:=]\s*(.+)$/);
      if (!m) return { key: "", label: "", value: part, order: 100 + i };
      const key = m[1].trim().toLowerCase();
      return { key, label: KEY_LABEL[key] ?? m[1].trim(), value: m[2].trim(), order: KEY_ORDER[key] ?? 50 + i };
    })
    .sort((a, b) => a.order - b.order);
}

function attr(f, field) {
  return (f.attributes ?? []).find((a) => a.field === field)?.value;
}

export default function ScanDetail({ scan, assets, onLaunch, onBack, onDataChanged }) {
  const [findings, setFindings] = useState([]);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const summary = parseSummary(scan.summary);
  const advice = summary?.advice;
  const recommendations = summary?.recommendations ?? [];
  const assetsById = new Map((assets ?? []).map((a) => [a.id, a]));
  const pending = findings.filter((f) => !f.applied);

  const load = useCallback(() => {
    findingApi
      .forScan(scan.id)
      .then(setFindings)
      .catch((e) => setError(getErrorMessage(e)));
  }, [scan.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function run(id, action) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      load();
      onDataChanged?.();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  }

  const approve = (f) => run(f.id, () => findingApi.apply(f.id));
  const reject = (f) => run(f.id, () => findingApi.discard(f.id));
  const reclassify = (f) => run(f.id, () => findingApi.reclassify(f.id));

  async function bulk(kind) {
    if (pending.length === 0) return;
    const msg =
      kind === "approve"
        ? `¿Aprobar los ${pending.length} equipos pendientes? Los nuevos se agregan al inventario y los existentes solo se complementan.`
        : `¿Rechazar los ${pending.length} equipos pendientes? Se eliminarán estos resultados.`;
    if (!window.confirm(msg)) return;
    setBulkBusy(true);
    setError(null);
    try {
      for (const f of pending) {
        if (kind === "approve") await findingApi.apply(f.id);
        else await findingApi.discard(f.id);
      }
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBulkBusy(false);
      load();
      onDataChanged?.();
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
                  <span className={`confidence-badge ${confClass(r.score)}`}>{r.score} pts</span>
                </div>
                <button type="button" className="button primary small" onClick={() => onLaunch(r.ip, r.suggested_profile)}>
                  Escanear como {r.suggested_label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="approve-bar">
        <h4>Equipos encontrados ({findings.length})</h4>
        <span className="spacer" />
        {pending.length > 0 && (
          <>
            <span className="match-note">{pending.length} pendientes de aprobación</span>
            <button type="button" className="button primary small" disabled={bulkBusy} onClick={() => bulk("approve")}>
              ✓ Aprobar todos
            </button>
            <button type="button" className="button danger small" disabled={bulkBusy} onClick={() => bulk("reject")}>
              ✕ Rechazar todos
            </button>
          </>
        )}
      </div>

      <div className="host-cards">
        {findings.map((f) => {
          const current = f.matched_asset_id ? assetsById.get(f.matched_asset_id) : null;
          const canReclassify =
            f.applied && f.confidence >= 70 && current && f.winner_type && current.asset_type !== f.winner_type;
          const identity = (f.fingerprints ?? []).filter((g) => g.kind === "identity");
          const services = (f.fingerprints ?? []).filter((g) => g.kind !== "identity");
          const busy = busyId === f.id || bulkBusy;

          return (
            <div key={f.id} className="host-card">
              <div className="host-head">
                <div>
                  <strong>{attr(f, "hostname") || f.hostname || f.ip}</strong>
                  <small>
                    {[
                      f.ip,
                      attr(f, "mac") || f.mac ? `MAC ${attr(f, "mac") || f.mac}` : null,
                      attr(f, "vendor") || f.vendor,
                      attr(f, "os") || f.detected_os,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                </div>
                <div className="host-type">
                  <span className="type-name">{f.winner_label ?? "Desconocido"}</span>
                  <span className={`confidence-badge ${confClass(f.confidence)}`}>{f.confidence} pts</span>
                  {f.needs_review && (
                    <span className="status-badge pending review-flag" title={f.review_reason ?? ""}>
                      Requiere revisión
                    </span>
                  )}
                </div>
              </div>

              {f.needs_review && f.review_reason && <div className="match-note">{f.review_reason}</div>}

              <div className="host-status">
                <span className={`status-badge ${f.applied ? "completed" : "pending"}`}>
                  {f.applied ? "✓ En inventario" : "Pendiente de aprobación"}
                </span>
                {!f.applied && (
                  <span className="match-note">
                    {current
                      ? `Complementará a ${current.asset_code ?? ""} ${current.asset_name ?? ""} (solo campos vacíos)`
                      : "Se agregará como activo nuevo"}
                  </span>
                )}
                {!f.applied && (
                  <div className="host-actions">
                    <button type="button" className="button primary small" disabled={busy} onClick={() => approve(f)}>
                      ✓ Aprobar
                    </button>
                    <button type="button" className="button danger small" disabled={busy} onClick={() => reject(f)}>
                      ✕ Rechazar
                    </button>
                  </div>
                )}
                {canReclassify && (
                  <button type="button" className="button restore small reclassify-btn" disabled={busy} onClick={() => reclassify(f)}>
                    ↻ Actualizar tipo a {f.winner_label}
                  </button>
                )}
              </div>

              {f.attributes?.length > 0 && (
                <div className="fp-block">
                  <span className="fp-title">
                    Datos detectados {f.applied ? "" : "(se guardan al aprobar, solo en campos vacíos)"}
                  </span>
                  <dl className="kv-grid">
                    {f.attributes.map((a) => {
                      const saved = ["serial", "platform"].includes(a.field) ? null : current?.[a.field];
                      const keeps = saved && saved !== a.value && saved !== current?.ip;
                      return (
                        <div key={a.field} className="kv-row">
                          <dt>{a.label}</dt>
                          <dd>
                            <b>{a.value}</b> <small>· {a.source}</small>
                            {keeps && <small className="kv-note"> · se conserva el actual: {saved}</small>}
                            {a.alternatives?.length > 0 && (
                              <small> · otras: {a.alternatives.map((x) => x.value).join(", ")}</small>
                            )}
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                </div>
              )}

              {identity.length > 0 && (
                <div className="fp-block">
                  <span className="fp-title">Identidad</span>
                  {identity.map((g) => {
                    const rows = parseDetail(g.detail);
                    return (
                      <div key={g.label} className="fp-identity">
                        <div className="fp-identity-title">{g.label}</div>
                        {rows.length > 0 && (
                          <dl className="kv-grid">
                            {rows.map((r, i) => (
                              <div key={i} className="kv-row">
                                <dt>{r.label}</dt>
                                <dd>{r.value}</dd>
                              </div>
                            ))}
                          </dl>
                        )}
                      </div>
                    );
                  })}
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
        {findings.length === 0 && <p className="empty">Sin equipos pendientes ni aprobados en este escaneo.</p>}
      </div>
    </div>
  );
}