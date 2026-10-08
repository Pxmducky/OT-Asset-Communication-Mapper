import { useState } from "react";

import { getErrorMessage } from "../services/api";
import { networkApi } from "../services/scanApi";

const EMPTY = { cidr: "", description: "", plant: "", building: "", production_line: "", vlan: "" };

function payloadFrom(f) {
  return {
    cidr: f.cidr.trim(),
    description: f.description.trim() || null,
    plant: f.plant.trim() || null,
    building: f.building.trim() || null,
    production_line: f.production_line.trim() || null,
    vlan: f.vlan === "" ? null : Number(f.vlan),
  };
}

function locationChips(n) {
  const chips = [];
  if (n.plant) chips.push(`🏭 ${n.plant}`);
  if (n.building) chips.push(`🏚 ${n.building}`);
  if (n.production_line) chips.push(`🔧 ${n.production_line}`);
  if (n.vlan) chips.push(`VLAN ${n.vlan}`);
  return chips;
}

export default function NetworkManager({ networks, onChanged, onInfo, onError }) {
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(EMPTY);

  const setField = (setter) => (key) => (e) => setter((f) => ({ ...f, [key]: e.target.value }));
  const addField = setField(setForm);
  const editField = setField(setEditForm);

  async function add(event) {
    event.preventDefault();
    try {
      await networkApi.add(payloadFrom(form));
      setForm(EMPTY);
      onInfo?.("Red agregada.");
      onChanged?.();
    } catch (e) {
      onError?.(getErrorMessage(e));
    }
  }

  function startEdit(n) {
    setEditingId(n.id);
    setEditForm({
      cidr: n.cidr, description: n.description || "", plant: n.plant || "",
      building: n.building || "", production_line: n.production_line || "", vlan: n.vlan ?? "",
    });
  }

  async function saveEdit(id) {
    try {
      const payload = payloadFrom(editForm);
      delete payload.cidr; // el CIDR no se edita
      await networkApi.update(id, payload);
      setEditingId(null);
      onInfo?.("Red actualizada.");
      onChanged?.();
    } catch (e) {
      onError?.(getErrorMessage(e));
    }
  }

  async function remove(id) {
    if (!window.confirm("¿Quitar esta red de las autorizadas?")) return;
    try {
      await networkApi.remove(id);
      onChanged?.();
    } catch (e) {
      onError?.(getErrorMessage(e));
    }
  }

  return (
    <div className="scan-nets">
      <form className="net-form" onSubmit={add}>
        <div className="net-form-row">
          <input type="text" placeholder="192.168.10.0/24" value={form.cidr} onChange={addField("cidr")} required />
          <input type="text" placeholder="Descripción (opcional)" value={form.description} onChange={addField("description")} />
        </div>
        <div className="net-form-row">
          <input type="text" placeholder="Planta" value={form.plant} onChange={addField("plant")} />
          <input type="text" placeholder="Nave" value={form.building} onChange={addField("building")} />
          <input type="text" placeholder="Línea" value={form.production_line} onChange={addField("production_line")} />
          <input type="number" placeholder="VLAN" min="1" max="4094" value={form.vlan} onChange={addField("vlan")} />
        </div>
        <button type="submit" className="button primary">
          + Agregar red
        </button>
      </form>

      <p className="scan-hint">
        La ubicación (planta/nave/línea/VLAN) es opcional. Los equipos nuevos que se descubran
        en esta red la heredan automáticamente.
      </p>

      <ul className="scan-net-list">
        {networks.map((n) => (
          <li key={n.id} className="net-item">
            {editingId === n.id ? (
              <div className="net-edit">
                <strong>{n.cidr}</strong>
                <div className="net-form-row">
                  <input type="text" placeholder="Descripción" value={editForm.description} onChange={editField("description")} />
                  <input type="text" placeholder="Planta" value={editForm.plant} onChange={editField("plant")} />
                  <input type="text" placeholder="Nave" value={editForm.building} onChange={editField("building")} />
                  <input type="text" placeholder="Línea" value={editForm.production_line} onChange={editField("production_line")} />
                  <input type="number" placeholder="VLAN" min="1" max="4094" value={editForm.vlan} onChange={editField("vlan")} />
                </div>
                <div className="net-edit-actions">
                  <button type="button" className="button primary small" onClick={() => saveEdit(n.id)}>
                    Guardar
                  </button>
                  <button type="button" className="button secondary small" onClick={() => setEditingId(null)}>
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="net-info">
                  <strong>{n.cidr}</strong>
                  {n.description && <span> — {n.description}</span>}
                  <div className="net-chips">
                    {locationChips(n).map((c) => (
                      <span key={c} className="port-chip">
                        {c}
                      </span>
                    ))}
                    {locationChips(n).length === 0 && <span className="muted">sin ubicación</span>}
                  </div>
                </div>
                <div className="net-actions">
                  <button type="button" className="button secondary small" onClick={() => startEdit(n)}>
                    Editar
                  </button>
                  <button type="button" className="button danger small" onClick={() => remove(n.id)}>
                    Quitar
                  </button>
                </div>
              </>
            )}
          </li>
        ))}
        {networks.length === 0 && <li className="scan-empty">No hay redes autorizadas. Agrega una para poder escanear.</li>}
      </ul>
    </div>
  );
}