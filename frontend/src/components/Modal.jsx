import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Modal / ventana.
 * - Por defecto: diálogo modal clásico (overlay, Esc cierra).
 * - floating: ventana flotante tipo app. Se mueve arrastrando la barra de título,
 *   se redimensiona desde la esquina, se minimiza o maximiza. No bloquea la app.
 *   Recuerda posición y tamaño (localStorage, clave = storageKey o título).
 */
function loadBox(key) {
  try {
    const raw = localStorage.getItem(`win:${key}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveBox(key, box) {
  try {
    localStorage.setItem(`win:${key}`, JSON.stringify(box));
  } catch {
    /* sin almacenamiento: se ignora */
  }
}

function clampBox(box) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const w = Math.min(Math.max(box.w, 320), vw);
  const h = Math.min(Math.max(box.h, 160), vh);
  return {
    w,
    h,
    x: Math.min(Math.max(box.x, 0), Math.max(0, vw - 120)),
    y: Math.min(Math.max(box.y, 0), Math.max(0, vh - 40)),
  };
}

function FloatingWindow({ title, onClose, children, width, storageKey }) {
  const key = storageKey || title;
  const [box, setBox] = useState(() => {
    const saved = loadBox(key);
    if (saved) return clampBox(saved);
    const w = Math.min(width, window.innerWidth - 40);
    const h = Math.min(640, window.innerHeight - 80);
    return { w, h, x: Math.max(20, (window.innerWidth - w) / 2), y: 60 };
  });
  const [minimized, setMinimized] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const winRef = useRef(null);
  const drag = useRef(null);

  useEffect(() => {
    saveBox(key, box);
  }, [key, box]);

  // Guarda el tamaño cuando el usuario redimensiona desde la esquina
  useEffect(() => {
    const el = winRef.current;
    if (!el || minimized || maximized) return undefined;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      setBox((b) => (Math.abs(b.w - r.width) > 2 || Math.abs(b.h - r.height) > 2 ? { ...b, w: r.width, h: r.height } : b));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [minimized, maximized]);

  const onPointerDown = useCallback(
    (event) => {
      if (maximized || event.button !== 0 || event.target.closest("button")) return;
      drag.current = { sx: event.clientX, sy: event.clientY, x: box.x, y: box.y };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [box.x, box.y, maximized],
  );

  const onPointerMove = useCallback((event) => {
    if (!drag.current) return;
    const { sx, sy, x, y } = drag.current;
    setBox((b) => clampBox({ ...b, x: x + event.clientX - sx, y: y + event.clientY - sy }));
  }, []);

  const onPointerUp = useCallback(() => {
    drag.current = null;
  }, []);

  const style = maximized
    ? { left: 0, top: 0, width: "100vw", height: "100vh" }
    : { left: box.x, top: box.y, width: box.w, height: minimized ? "auto" : box.h };

  return (
    <div
      ref={winRef}
      className={`float-window${minimized ? " is-min" : ""}${maximized ? " is-max" : ""}`}
      style={style}
      role="dialog"
      aria-label={title}
    >
      <header
        className="modal-header float-header"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onDoubleClick={() => !minimized && setMaximized((m) => !m)}
      >
        <h2>{title}</h2>
        <div className="float-actions">
          <button
            type="button"
            className="icon-button"
            onClick={() => {
              setMinimized((m) => !m);
              setMaximized(false);
            }}
            aria-label={minimized ? "Restaurar" : "Minimizar"}
            title={minimized ? "Restaurar" : "Minimizar"}
          >
            {minimized ? "▢" : "–"}
          </button>
          {!minimized && (
            <button
              type="button"
              className="icon-button"
              onClick={() => setMaximized((m) => !m)}
              aria-label={maximized ? "Restaurar tamaño" : "Maximizar"}
              title={maximized ? "Restaurar tamaño" : "Maximizar"}
            >
              {maximized ? "❐" : "□"}
            </button>
          )}
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar" title="Cerrar">
            ×
          </button>
        </div>
      </header>
      {!minimized && <div className="modal-body float-body">{children}</div>}
    </div>
  );
}

function Modal({ title, onClose, children, width = 640, floating = false, storageKey }) {
  useEffect(() => {
    if (floating) return undefined;
    const handleKey = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose, floating]);

  if (floating) {
    return (
      <FloatingWindow title={title} onClose={onClose} width={width} storageKey={storageKey}>
        {children}
      </FloatingWindow>
    );
  }

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" style={{ maxWidth: width }} onMouseDown={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <h2>{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar">
            ×
          </button>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export default Modal;