import NetworkManager from "./NetworkManager";
import { useCallback, useEffect, useRef, useState } from "react";

import { getErrorMessage } from "../services/api";
import { networkApi, scanApi, scanProfileApi } from "../services/scanApi";
import ScanDetail from "./ScanDetail";

const TYPE_ICONS = {
  plc: "🧠", hmi: "🖥️", mes: "🏭", server: "🗄️", scada: "📊", printers: "🖨️",
  cnc: "⚙️", switch: "🔀", drive: "🔧", camera: "📷", robot: "🤖", io_remote: "🔌",
  instrument: "⚖️", ups: "🔋", wap: "📶", ewon: "🌐", mguard: "🛡️", general: "🔍",
};

const STATUS_LABEL = {
  pending: "En cola", running: "Escaneando…", completed: "Finalizado",
  failed: "Falló", canceled: "Cancelado",
};

function parseSummary(value) {
  try {
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

export default function ScanPanel({ onDataChanged }) {
  const [tab, setTab] = useState("scan");
  const [profiles, setProfiles] = useState([]);
  const [networks, setNetworks] = useState([]);
  const [target, setTarget] = useState("");
  const [scans, setScans] = useState([]);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [launching, setLaunching] = useState(false);
  const [selectedScan, setSelectedScan] = useState(null);

  const [newCidr, setNewCidr] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const prevStatus = useRef(new Map());

  const refreshNetworks = useCallback(async () => {
    try {
      setNetworks(await networkApi.list());
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }, []);

  useEffect(() => {
    scanProfileApi.list().then(setProfiles).catch((e) => setError(getErrorMessage(e)));
    refreshNetworks();
  }, [refreshNetworks]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const data = await scanApi.list();
        if (!alive) return;
        let completedSomething = false;
        for (const s of data) {
          const prev = prevStatus.current.get(s.id);
          if (prev && prev !== s.status && (s.status === "completed" || s.status === "failed")) {
            if (s.status === "completed") {
              const sum = parseSummary(s.summary);
              const extra = sum ? ` · nuevos ${sum.created}, actualizados ${sum.updated}, por revisar ${sum.review}` : "";
              const advice = sum?.advice ? `  ⚠ ${sum.advice}` : "";
              setInfo(`✓ Finalizado: ${s.scan_profile} ${s.target}${extra}${advice}`);
              completedSomething = true;
            } else {
              setInfo(`⚠ Falló: ${s.scan_profile} ${s.target} — ${s.error ?? ""}`);
            }
          }
          prevStatus.current.set(s.id, s.status);
        }
        setScans(data);
        if (completedSomething) onDataChanged?.();
      } catch {
        /* silencio durante el poll */
      }
    };
    tick();
    const id = setInterval(tick, 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [onDataChanged]);

  const running = scans.filter((s) => s.status === "running").length;
  const pending = scans.filter((s) => s.status === "pending").length;
  const general = profiles.find((p) => p.value === "general");

  async function launch(profileValue, explicitTarget) {
    const t = (explicitTarget ?? target).trim();
    if (!t) {
      setError("Escribe una IP o subred, o elige una red de la lista.");
      return;
    }
    setLaunching(true);
    setError(null);
    setInfo(null);
    try {
      const res = await scanApi.request({ target: t, scan_profile: profileValue });
      setInfo(
        res.coalesced
          ? "Ya había un escaneo igual en curso: te enganchamos a ese."
          : `Escaneo encolado: ${res.scan.scan_profile} → ${res.scan.target}.`
      );
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLaunching(false);
    }
  }

  function launchRecommended(ip, profileValue) {
    setSelectedScan(null);
    setTarget(ip);
    launch(profileValue, ip);
  }

  async function addNetwork(event) {
    event.preventDefault();
    setError(null);
    try {
      await networkApi.add({ cidr: newCidr.trim(), description: newDesc.trim() || null });
      setNewCidr("");
      setNewDesc("");
      await refreshNetworks();
      setInfo("Red agregada.");
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }

  async function removeNetwork(id) {
    if (!window.confirm("¿Quitar esta red de las autorizadas?")) return;
    try {
      await networkApi.remove(id);
      await refreshNetworks();
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }

  // ----- Vista de detalle de un escaneo -----
  if (selectedScan) {
    const fresh = scans.find((s) => s.id === selectedScan.id) ?? selectedScan;
    return <ScanDetail scan={fresh} onLaunch={launchRecommended} onBack={() => setSelectedScan(null)} />;
  }

  return (
    <div className="scan-panel">
      <div className="scan-tabs">
        <button type="button" className={tab === "scan" ? "scan-tab active" : "scan-tab"} onClick={() => setTab("scan")}>
          Escanear
        </button>
        <button type="button" className={tab === "nets" ? "scan-tab active" : "scan-tab"} onClick={() => setTab("nets")}>
          Redes autorizadas ({networks.length})
        </button>
      </div>

      {error && <div className="scan-msg error">{error}</div>}
      {info && <div className="scan-msg info">{info}</div>}

      {tab === "scan" && (
        <>
          <div className="scan-target">
            <label className="toolbar-field">
              Red autorizada
              <select value="" onChange={(e) => e.target.value && setTarget(e.target.value)}>
                <option value="">— elige una red para rellenar —</option>
                {networks.map((n) => (
                  <option key={n.id} value={n.cidr}>
                    {n.cidr} {n.description ? `(${n.description})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="toolbar-field grow">
              IP o subred a escanear
              <input
                type="text"
                value={target}
                placeholder="172.16.99.7  o  172.16.99.0/24"
                onChange={(e) => setTarget(e.target.value)}
              />
            </label>
          </div>

          {general && (
            <button
              type="button"
              className="button primary discover-btn"
              disabled={launching || !target.trim()}
              onClick={() => launch("general")}
            >
              🔍 {general.label} — ¿no sabes qué hay? Empieza aquí
            </button>
          )}

          <p className="scan-hint">
            O elige el <strong>tipo de equipo</strong> que esperas y presiona su botón.
            Corren hasta 2 escaneos a la vez — el resto hace fila.
          </p>

          <div className="scan-grid">
            {profiles
              .filter((p) => p.value !== "discovery" && p.value !== "general")
              .map((p) => (
                <button
                  key={p.value}
                  type="button"
                  className="scan-type"
                  disabled={launching || !target.trim()}
                  onClick={() => launch(p.value)}
                >
                  <span className="scan-type-icon">{TYPE_ICONS[p.value] ?? "📟"}</span>
                  <span>{p.label}</span>
                </button>
              ))}
          </div>

          <div className="scan-queue">
            <h4>
              Cola de escaneos — <span className="pill running">{running} en curso</span>{" "}
              <span className="pill pending">{pending} en fila</span>
            </h4>
            <p className="scan-hint">Haz click en un escaneo finalizado para ver su detalle y recomendaciones.</p>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Tipo</th>
                  <th>Objetivo</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {scans.slice(0, 12).map((s) => (
                  <tr
                    key={s.id}
                    className={s.status === "completed" ? "clickable-row" : ""}
                    onClick={() => s.status === "completed" && setSelectedScan(s)}
                  >
                    <td>{s.id}</td>
                    <td>{s.scan_profile}</td>
                    <td>{s.target}</td>
                    <td>
                      <span className={`status-badge ${s.status}`}>{STATUS_LABEL[s.status] ?? s.status}</span>
                      {s.status === "completed" && <span className="row-arrow"> ›</span>}
                    </td>
                  </tr>
                ))}
                {scans.length === 0 && (
                  <tr>
                    <td colSpan={4} className="scan-empty">
                      Aún no hay escaneos.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "nets" && (
        <NetworkManager networks={networks} onChanged={refreshNetworks} onInfo={setInfo} onError={setError} />
      )}
    </div>
  );
}