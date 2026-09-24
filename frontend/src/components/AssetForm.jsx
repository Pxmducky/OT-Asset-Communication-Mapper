import { useMemo, useState } from "react";

import { ASSET_TYPES } from "../utils/constants";

const EMPTY_ASSET = {
  asset_code: "",
  asset_name: "",
  asset_type: "",
  ip: "",
  mac: "",
  hostname: "",
  vlan: "",
  vendor: "",
  product: "",
  plant: "",
  building: "",
  production_line: "",
  description: "",
};

const REQUIRED = {
  asset_name: "Nombre",
  asset_type: "Tipo",
  ip: "IP",
  vlan: "VLAN",
  plant: "Planta",
  building: "Nave",
  production_line: "Línea de producción",
};

const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
const MAC = /^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$/i;

function validate(values) {
  const errors = {};
  for (const [field, label] of Object.entries(REQUIRED)) {
    if (!String(values[field] ?? "").trim()) errors[field] = `${label} es obligatorio`;
  }
  if (values.ip && !IPV4.test(values.ip.trim()) && !values.ip.includes(":")) errors.ip = "IP inválida";
  if (values.mac && !MAC.test(values.mac.trim())) errors.mac = "Formato aa:bb:cc:dd:ee:ff";
  const vlan = Number(values.vlan);
  if (values.vlan !== "" && (!Number.isInteger(vlan) || vlan < 1 || vlan > 4094)) errors.vlan = "Entre 1 y 4094";
  return errors;
}

function toPayload(values) {
  const payload = {};
  for (const [field, value] of Object.entries(values)) {
    const text = String(value ?? "").trim();
    payload[field] = text === "" ? null : text;
  }
  payload.vlan = payload.vlan === null ? null : Number(payload.vlan);
  if (!payload.asset_code) delete payload.asset_code; // se genera automáticamente
  return payload;
}

function AssetForm({ asset, assets, onSubmit, onCancel, busy, serverError }) {
  const [values, setValues] = useState(() => {
    if (!asset) return EMPTY_ASSET;
    const initial = {};
    for (const field of Object.keys(EMPTY_ASSET)) initial[field] = asset[field] ?? "";
    return initial;
  });
  const [errors, setErrors] = useState({});

  // Sugerencias con lo que ya existe en el inventario
  const suggestions = useMemo(() => {
    const collect = (field) => [...new Set(assets.map((a) => a[field]).filter(Boolean))].sort();
    return {
      plant: collect("plant"),
      building: collect("building"),
      production_line: collect("production_line"),
      vendor: collect("vendor"),
    };
  }, [assets]);

  const typeOptions = useMemo(() => {
    const known = new Set(ASSET_TYPES.map((type) => type.value));
    const extra = [...new Set(assets.map((a) => a.asset_type))].filter((type) => type && !known.has(type));
    return [...ASSET_TYPES, ...extra.map((type) => ({ value: type, label: type }))];
  }, [assets]);

  function change(field) {
    return (event) => setValues((current) => ({ ...current, [field]: event.target.value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length === 0) onSubmit(toPayload(values));
  }

  function field(name, label, props = {}) {
    return (
      <label className={`form-field ${errors[name] ? "has-error" : ""}`}>
        <span>
          {label}
          {REQUIRED[name] && <em>*</em>}
        </span>
        <input value={values[name]} onChange={change(name)} {...props} />
        {errors[name] && <small className="field-error">{errors[name]}</small>}
      </label>
    );
  }

  return (
    <form className="entity-form" onSubmit={handleSubmit} noValidate>
      <fieldset>
        <legend>Identificación</legend>
        <div className="form-grid">
          {field("asset_code", "Código", { placeholder: asset ? "" : "Automático (AST-###)" })}
          {field("asset_name", "Nombre", { autoFocus: true, placeholder: "PLC-LINEA3-01" })}
          <label className={`form-field ${errors.asset_type ? "has-error" : ""}`}>
            <span>
              Tipo<em>*</em>
            </span>
            <select value={values.asset_type} onChange={change("asset_type")}>
              <option value="">Selecciona…</option>
              {typeOptions.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
            {errors.asset_type && <small className="field-error">{errors.asset_type}</small>}
          </label>
          {field("vendor", "Fabricante", { list: "vendor-options", placeholder: "Siemens" })}
          {field("product", "Producto / modelo", { placeholder: "S7-1500 CPU 1516-3 PN/DP" })}
        </div>
      </fieldset>

      <fieldset>
        <legend>Red</legend>
        <div className="form-grid">
          {field("ip", "IP", { placeholder: "172.16.97.2" })}
          {field("mac", "MAC", { placeholder: "00:1b:1b:c3:90:b7" })}
          {field("hostname", "Hostname")}
          {field("vlan", "VLAN", { type: "number", min: 1, max: 4094, placeholder: "10" })}
        </div>
      </fieldset>

      <fieldset>
        <legend>Ubicación</legend>
        <div className="form-grid">
          {field("plant", "Planta", { list: "plant-options", placeholder: "Planta Toluca" })}
          {field("building", "Nave", { list: "building-options", placeholder: "Nave 2" })}
          {field("production_line", "Línea de producción", { list: "line-options", placeholder: "Línea 3" })}
        </div>
      </fieldset>

      <label className="form-field">
        <span>Descripción</span>
        <textarea
          rows={3}
          value={values.description}
          onChange={change("description")}
          placeholder="Función del equipo, responsable, notas…"
        />
      </label>

      <datalist id="plant-options">{suggestions.plant.map((v) => <option key={v} value={v} />)}</datalist>
      <datalist id="building-options">{suggestions.building.map((v) => <option key={v} value={v} />)}</datalist>
      <datalist id="line-options">{suggestions.production_line.map((v) => <option key={v} value={v} />)}</datalist>
      <datalist id="vendor-options">{suggestions.vendor.map((v) => <option key={v} value={v} />)}</datalist>

      {serverError && <div className="form-alert">{serverError}</div>}

      <footer className="form-actions">
        <button type="button" className="button secondary" onClick={onCancel}>
          Cancelar
        </button>
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? "Guardando…" : asset ? "Guardar cambios" : "Crear activo"}
        </button>
      </footer>
    </form>
  );
}

export default AssetForm;