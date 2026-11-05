import { Children, useCallback, useEffect, useRef, useState } from "react";

/**
 * Reemplaza <main className="workspace">. Recibe 3 hijos: panel izquierdo,
 * centro (mapa) y panel derecho. Los paneles laterales se ajustan arrastrando
 * el divisor, se colapsan con su botón y el tamaño se recuerda.
 * Doble clic en un divisor = tamaño por defecto.
 */
const DEFAULTS = { left: 300, right: 380, leftOpen: true, rightOpen: true };
const MIN = 200;
const MAX = 640;
const STORE = "layout:workspace";

function load() {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(STORE) || "{}") };
  } catch {
    return DEFAULTS;
  }
}

export default function ResizableWorkspace({ children }) {
  const [left, center, right] = Children.toArray(children);
  const [layout, setLayout] = useState(load);
  const drag = useRef(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORE, JSON.stringify(layout));
    } catch {
      /* ignorar */
    }
  }, [layout]);

  const startDrag = useCallback(
    (side) => (event) => {
      if (event.button !== 0) return;
      drag.current = { side, sx: event.clientX, start: layout[side] };
      event.currentTarget.setPointerCapture(event.pointerId);
      document.body.classList.add("is-resizing");
    },
    [layout],
  );

  const onMove = useCallback((event) => {
    const d = drag.current;
    if (!d) return;
    const delta = event.clientX - d.sx;
    const next = d.side === "left" ? d.start + delta : d.start - delta;
    setLayout((l) => ({ ...l, [d.side]: Math.min(MAX, Math.max(MIN, next)) }));
  }, []);

  const endDrag = useCallback(() => {
    drag.current = null;
    document.body.classList.remove("is-resizing");
  }, []);

  const toggle = (side) => setLayout((l) => ({ ...l, [`${side}Open`]: !l[`${side}Open`] }));
  const reset = (side) => setLayout((l) => ({ ...l, [side]: DEFAULTS[side] }));

  const cols = [
    layout.leftOpen ? `${layout.left}px` : "0px",
    "8px",
    "minmax(0, 1fr)",
    "8px",
    layout.rightOpen ? `${layout.right}px` : "0px",
  ].join(" ");

  function splitter(side) {
    const open = layout[`${side}Open`];
    const arrow = side === "left" ? (open ? "‹" : "›") : open ? "›" : "‹";
    return (
      <div
        className={`ws-splitter${open ? "" : " is-collapsed"}`}
        role="separator"
        aria-orientation="vertical"
        title={open ? "Arrastra para ajustar · doble clic para restablecer" : "Panel oculto"}
        onPointerDown={open ? startDrag(side) : undefined}
        onPointerMove={onMove}
        onPointerUp={endDrag}
        onDoubleClick={() => open && reset(side)}
      >
        <button
          type="button"
          className="ws-toggle"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => toggle(side)}
          aria-label={open ? "Ocultar panel" : "Mostrar panel"}
          title={open ? "Ocultar panel" : "Mostrar panel"}
        >
          {arrow}
        </button>
      </div>
    );
  }

  return (
    <main className="workspace ws-resizable" style={{ gridTemplateColumns: cols }}>
      <div className="ws-pane">{layout.leftOpen && left}</div>
      {splitter("left")}
      {center}
      {splitter("right")}
      <div className="ws-pane">{layout.rightOpen && right}</div>
    </main>
  );
}