function ImportResult({ result, onClose }) {
    const stats = [
      ["Activos nuevos", result.assets_created],
      ["Activos completados", result.assets_updated],
      ["Comunicaciones nuevas", result.communications_created],
      ["Comunicaciones que ya existían (omitidas)", result.communications_skipped],
      ["Filas con error (omitidas)", result.rows_skipped],
    ];
  
    return (
      <div className="import-result">
        <div className="import-stats">
          {stats.map(([label, value]) => (
            <div key={label}>
              <strong>{value}</strong>
              <span>{label}</span>
            </div>
          ))}
        </div>
  
        {result.errors.length > 0 && (
          <>
            <h4>Detalle de errores</h4>
            <ul className="import-errors">
              {result.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </>
        )}
  
        <footer className="form-actions">
          <button type="button" className="button primary" onClick={onClose}>
            Aceptar
          </button>
        </footer>
      </div>
    );
  }
  
  export default ImportResult;