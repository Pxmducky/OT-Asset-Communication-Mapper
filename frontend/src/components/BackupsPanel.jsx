import { useCallback, useEffect, useState } from "react";

import { getErrorMessage } from "../services/api";
import { backupApi } from "../services/scanApi";

const REASON_LABEL = {
  "pre-scan": "Antes de escaneo",
  "pre-apply": "Antes de aplicar",
  "pre-restore": "Antes de restaurar",
  manual: "Manual",
};

function formatSize(bytes) {
  if (!bytes) return "—";
  const kb = bytes / 1024;
  return kb < 1024 ? `${kb.toFixed(0)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

export default function BackupsPanel({ onDataChanged }) {
  const [backups, setBackups] = useState([]);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setBackups(await backupApi.list());
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createManual() {
    setBusy(true);
    setError(null);
    try {
      await backupApi.create();
      await load();
      setInfo("Respaldo manual creado.");
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function download(backup) {
    try {
      await backupApi.download(backup.id, backup.filename);
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }

  async function remove(backup) {
    if (!window.confirm("¿Eliminar este respaldo del disco?")) return;
    try {
      await backupApi.remove(backup.id);
      await load();
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }

  async function restore(backup) {
    const when = new Date(backup.created_at).toLocaleString();
    const ok = window.confirm(
      "⚠ RESTAURAR RESPALDO\n\n" +
        `Vas a REEMPLAZAR la base actual con el respaldo del ${when}.\n\n` +
        "Se PERDERÁN todos los cambios hechos después de ese respaldo " +
        "(activos, escaneos y comunicaciones más recientes).\n\n" +
        "Esta acción no se puede deshacer. ¿Continuar?"
    );
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      const res = await backupApi.restore(backup.id);
      setInfo(res.note || "Base restaurada. Reinicia el backend para asegurar un estado limpio.");
      onDataChanged?.();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="backups-panel">
      {error && <div className="scan-msg error">{error}</div>}
      {info && <div className="scan-msg info">{info}</div>}

      <div className="backups-head">
        <p className="scan-hint">
          Se crea un respaldo automático antes de cada escaneo y antes de aplicar cambios.
        </p>
        <button type="button" className="button primary" disabled={busy} onClick={createManual}>
          + Respaldo manual
        </button>
      </div>

      <table className="backups-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Motivo</th>
            <th>Tamaño</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {backups.map((b) => (
            <tr key={b.id}>
              <td>{new Date(b.created_at).toLocaleString()}</td>
              <td>{REASON_LABEL[b.reason] ?? b.reason}</td>
              <td>{formatSize(b.size_bytes)}</td>
              <td className="backups-actions">
                <button type="button" className="button secondary small" onClick={() => download(b)}>
                  ⬇ Descargar
                </button>
                <button type="button" className="button small restore" disabled={busy} onClick={() => restore(b)}>
                  ↺ Restaurar
                </button>
                <button type="button" className="button danger small" onClick={() => remove(b)}>
                  🗑
                </button>
              </td>
            </tr>
          ))}
          {backups.length === 0 && (
            <tr>
              <td colSpan={4} className="scan-empty">
                Aún no hay respaldos.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
