import { useMemo, useState } from "react";

import { PROTOCOLS } from "../utils/constants";
import { ipToNumber } from "../utils/graphLayout";

const PORTS = /^[A-Za-z0-9/ ,;:-]*$/;

function assetLabel(asset) {
  return `${asset.ip ?? "sin IP"} — ${asset.asset_name} (${asset.asset_code})`;
}

function CommunicationForm({ communication, preset, assets, onSubmit, onCancel, busy, serverError }) {
  const sortedAssets = useMemo(() => [...assets].sort((a, b) => ipToNumber(a.ip) - ipToNumber(b.ip)), [assets]);
  const idByLabel = useMemo(() => new Map(sortedAssets.map((a) => [assetLabel(a), a.id])), [sortedAssets]);
  const labelById = useMemo(() => new Map(sortedAssets.map((a) => [a.id, assetLabel(a)])), [sortedAssets]);

  const initial = communication ?? preset ?? {};
  const [values, setValues] = useState({
    source: labelById.get(initial.source_asset_id) ?? "",
    destination: labelById.get(initial.destination_asset_id) ?? "",
    protocol: communication?.protocol ?? "",
    source_port: communication?.source_port ?? "",
    destination_port: communication?.destination_port ?? "",
    description: communication?.description ?? "",
  });
  const [createReverse, setCreateReverse] = useState(false);
  const [errors, setErrors] = useState({});

  function change(field) {
    return (event) => setValues((current) => ({ ...current, [field]: event.target.value }));
  }

  function swap() {
    setValues((current) => ({
      ...current,
      source: current.destination,
      destination: current.source,
      source_port: current.destination_port,
      destination_port: current.source_port,
    }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const found = {};
    const sourceId = idByLabel.get(values.source);
    const destinationId = idByLabel.get(values.destination);

    if (!sourceId) found.source = "Elige un activo de la lista";
    if (!destinationId) found.destination = "Elige un activo de la lista";
    if (sourceId && sourceId === destinationId) found.destination = "Debe ser distinto al origen";
    if (!values.protocol.trim()) found.protocol = "El protocolo es obligatorio";
    if (!PORTS.test(values.source_port)) found.source_port = "Ej.: 102, tcp/502";
    if (!PORTS.test(values.destination_port)) found.destination_port = "Ej.: 102, tcp/502";

    setErrors(found);
    if (Object.keys(found).length > 0) return;

    onSubmit(
      {
        source_asset_id: sourceId,
        destination_asset_id: destinationId,
        protocol: values.protocol.trim().toLowerCase(),
        source_port: values.source_port.trim(),
        destination_port: values.destination_port.trim(),
        description: values.description.trim() || null,
      },
      createReverse
    );
  }

  function assetField(name, label) {
    return (
      <label className={`form-field ${errors[name] ? "has-error" : ""}`}>
        <span>
          {label}
          <em>*</em>
        </span>
        <input list="asset-options" value={values[name]} onChange={change(name)} placeholder="Escribe IP o nombre…" />
        {errors[name] && <small className="field-error">{errors[name]}</small>}
      </label>
    );
  }

  function textField(name, label, props = {}) {
    return (
      <label className={`form-field ${errors[name] ? "has-error" : ""}`}>
        <span>{label}</span>
        <input value={values[name]} onChange={change(name)} {...props} />
        {errors[name] && <small className="field-error">{errors[name]}</small>}
      </label>
    );
  }

  return (
    <form className="entity-form" onSubmit={handleSubmit} noValidate>
      {assetField("source", "Origen")}

      <button type="button" className="button ghost swap-button" onClick={swap}>
        ⇅ Invertir origen / destino
      </button>

      {assetField("destination", "Destino")}

      <div className="form-grid">
        <label className={`form-field ${errors.protocol ? "has-error" : ""}`}>
          <span>
            Protocolo<em>*</em>
          </span>
          <input list="protocol-options" value={values.protocol} onChange={change("protocol")} placeholder="s7" />
          {errors.protocol && <small className="field-error">{errors.protocol}</small>}
        </label>
        {textField("source_port", "Puerto(s) origen", { placeholder: "tcp/49152" })}
        {textField("destination_port", "Puerto(s) destino", { placeholder: "tcp/102" })}
      </div>

      <label className="form-field">
        <span>Descripción</span>
        <textarea rows={2} value={values.description} onChange={change("description")} placeholder="Lectura de tags, respaldo, acceso remoto…" />
      </label>

      {!communication && (
        <label className="checkbox">
          <input type="checkbox" checked={createReverse} onChange={(event) => setCreateReverse(event.target.checked)} />
          Crear también el sentido inverso (destino → origen)
        </label>
      )}

      <datalist id="asset-options">
        {sortedAssets.map((asset) => (
          <option key={asset.id} value={assetLabel(asset)} />
        ))}
      </datalist>
      <datalist id="protocol-options">
        {PROTOCOLS.map((protocol) => (
          <option key={protocol} value={protocol} />
        ))}
      </datalist>

      {serverError && <div className="form-alert">{serverError}</div>}

      <footer className="form-actions">
        <button type="button" className="button secondary" onClick={onCancel}>
          Cancelar
        </button>
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? "Guardando…" : communication ? "Guardar cambios" : "Crear comunicación"}
        </button>
      </footer>
    </form>
  );
}

export default CommunicationForm;