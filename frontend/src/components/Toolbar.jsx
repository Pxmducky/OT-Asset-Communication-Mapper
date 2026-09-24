import { useRef } from "react";

import { GROUP_MODES } from "../utils/constants";

function Toolbar({
  groupMode,
  onGroupModeChange,
  focusMode,
  onFocusModeChange,
  showLabels,
  onShowLabelsChange,
  canFocus,
  onImport,
  onExport,
  onNewCommunication,
  busy,
}) {
  const fileInput = useRef(null);

  function handleFile(event) {
    const file = event.target.files?.[0];
    event.target.value = ""; // permite volver a elegir el mismo archivo
    if (file) onImport(file);
  }

  return (
    <div className="toolbar">
      <label className="toolbar-field">
        Agrupar por
        <select value={groupMode} onChange={(event) => onGroupModeChange(event.target.value)}>
          {GROUP_MODES.map((mode) => (
            <option key={mode.value} value={mode.value}>
              {mode.label}
            </option>
          ))}
        </select>
      </label>

      <label className="checkbox" title={canFocus ? "" : "Selecciona un activo primero"}>
        <input
          type="checkbox"
          checked={focusMode}
          disabled={!canFocus}
          onChange={(event) => onFocusModeChange(event.target.checked)}
        />
        Solo el activo seleccionado y sus conexiones
      </label>

      <label className="checkbox">
        <input type="checkbox" checked={showLabels} onChange={(event) => onShowLabelsChange(event.target.checked)} />
        Mostrar todos los protocolos
      </label>

      <div className="toolbar-spacer" />

      <button type="button" className="button secondary" onClick={onNewCommunication}>
        + Comunicación
      </button>
      <button type="button" className="button secondary" disabled={busy} onClick={() => fileInput.current?.click()}>
        {busy ? "Procesando…" : "⬆ Importar Excel"}
      </button>
      <button type="button" className="button secondary" disabled={busy} onClick={onExport}>
        ⬇ Descargar Excel
      </button>
      <input ref={fileInput} type="file" accept=".xlsx,.xlsm" hidden onChange={handleFile} />
    </div>
  );
}

export default Toolbar;