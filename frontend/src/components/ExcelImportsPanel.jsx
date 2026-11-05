import { useCallback, useEffect, useState } from "react";

import { excelApi, getErrorMessage } from "../services/api";

/** Historial de importaciones de Excel: cada una se puede borrar completa. */
export default function ExcelImportsPanel({ onDataChanged }) {
  const [imports, setImports] = useState([]);
  const [legacy, setLegacy] = useState(0);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await excelApi.listImports();
      setImports(data.imports);
      setLegacy(data.legacy_assets);
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(confirmText, action) {
    if (!window.confirm(confirmText)) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const r = await action();
      setInfo(`Borrados: ${r.deleted_assets} activos y ${r.deleted_communications} comunicaciones. Se hizo un respaldo antes.`);
      await load();
      onDataChanged?.();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const removeImport = (imp) =>
    run(
      `¿Borrar la importación "${imp.filename}"?\n\nSe eliminan los activos y comunicaciones que agregó ` +
        "(incluidas las conexiones que hayas hecho después hacia esos activos). " +
        "Los datos que completó en activos que ya existían no se revierten; para eso usa Respaldos.",
      () => excelApi.deleteImport(imp.id),
    );

  const removeLegacy = () =>
    run(
      `¿Borrar los ${legacy} activos importados de Excel antes de que existiera este historial? ` +
        "También se eliminan sus comunicaciones.",
      () => excelApi.deleteLegacy(),
    );

  return (
    <div className="backups-panel">
      {error && <div className="scan-msg error">{error}</div>}
      {info && <div className="scan-msg info">{info}</div>}

      <p className="scan-hint">
        Cada importación de Excel queda registrada. Borrarla elimina lo que esa importación agregó al inventario.
      </p>

      <table className="backups-table">
        <thead>
          <tr>
            <th>Archivo</th>
            <th>Fecha</th>
            <th>Agregó</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {imports.map((imp) => (
            <tr key={imp.id}>
              <td>{imp.filename}</td>
              <td>{imp.created_at ? new Date(imp.created_at).toLocaleString() : "—"}</td>
              <td>
                {imp.assets_created} activos · {imp.communications_created} comunicaciones
                {imp.assets_updated ? ` · completó ${imp.assets_updated}` : ""}
              </td>
              <td className="backups-actions">
                <button type="button" className="button danger small" disabled={busy} onClick={() => removeImport(imp)}>
                  🗑 Borrar importación
                </button>
              </td>
            </tr>
          ))}
          {legacy > 0 && (
            <tr>
              <td>Importaciones anteriores</td>
              <td>—</td>
              <td>{legacy} activos sin registro de importación</td>
              <td className="backups-actions">
                <button type="button" className="button danger small" disabled={busy} onClick={removeLegacy}>
                  🗑 Borrar
                </button>
              </td>
            </tr>
          )}
          {imports.length === 0 && legacy === 0 && (
            <tr>
              <td colSpan={4} className="scan-empty">
                No hay importaciones de Excel. Usa “⬆ Importar Excel” para agregar activos.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}