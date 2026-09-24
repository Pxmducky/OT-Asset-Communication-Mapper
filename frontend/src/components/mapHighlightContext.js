import { createContext } from "react";

// Permite resaltar nodos sin recalcular posiciones del mapa
export const MapHighlightContext = createContext({
  selectedId: null,
  neighborIds: new Set(),
  matchIds: new Set(),
});