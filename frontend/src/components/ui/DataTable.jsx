import styles from './DataTable.module.css'

export default function DataTable({ columns, rows, onRowClick, emptyMessage = 'No data' }) {
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        {columns && (
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th key={i} style={col.style}>{col.label}</th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns?.length || 1} className={styles.empty}>{emptyMessage}</td>
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr key={row.id ?? ri} onClick={() => onRowClick?.(row)} style={onRowClick ? { cursor: 'pointer' } : undefined}>
                {columns.map((col, ci) => (
                  <td key={ci} style={col.cellStyle}>
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
