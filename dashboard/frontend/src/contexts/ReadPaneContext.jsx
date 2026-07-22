import { createContext, useContext } from 'react'

// When GmailShell renders EmailDetailPage inside the right read-pane of the
// split layout, it wraps the content in this provider with value=true.
// EmailDetailPage's own GmailShell call then detects it and skips rendering
// the shell chrome (topbar, sidebar) — avoiding a double shell.
const ReadPaneContext = createContext(false)

export const ReadPaneProvider = ({ children }) => (
  <ReadPaneContext.Provider value={true}>{children}</ReadPaneContext.Provider>
)

export const useReadPane = () => useContext(ReadPaneContext)
