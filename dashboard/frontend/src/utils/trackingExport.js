// Export helpers for the Superadmin Tracking tab (PDF / Excel).
// Kept out of AdminPage.jsx so the heavy xlsx/jspdf libs stay lazy-loaded.

const stamp = (d = new Date()) => d.toLocaleDateString('en-CA')

export async function exportTrackingExcel(trackData, when = new Date()) {
  const XLSX = await import('xlsx')
  const wb = XLSX.utils.book_new()

  // Sheet 1 — Platform Summary
  const ws1 = XLSX.utils.aoa_to_sheet([
    ['📊 COGNIMAIL PLATFORM SUMMARY'],
    [],
    ['Metrik', 'Nilai'],
    ['Total Email', trackData?.total_emails ?? 0],
    ['✅ Clean', trackData?.total_clean ?? 0],
    ['⚠️ Spam / Warn', trackData?.total_warn ?? 0],
    ['🛡️ Karantina', trackData?.total_quarantine ?? 0],
  ])
  ws1['!cols'] = [{ wch: 25 }, { wch: 18 }]
  XLSX.utils.book_append_sheet(wb, ws1, '📊 Ringkasan')

  // Sheet 2 — Organization Traffic
  const ws2 = XLSX.utils.aoa_to_sheet([
    ['🏢 TRAFFIC PER ORGANISASI'],
    [],
    ['Organisasi', 'Users', 'Total Email', 'Clean', 'Warn', 'Karantina'],
    ...(trackData?.organizations || []).map((o) => [
      o.organization_name || 'Unknown', 
      o.users, 
      o.total_emails, 
      o.clean, 
      o.warn, 
      o.quarantine,
    ]),
  ])
  ws2['!cols'] = [{ wch: 32 }, { wch: 10 }, { wch: 14 }, { wch: 10 }, { wch: 10 }, { wch: 12 }]
  XLSX.utils.book_append_sheet(wb, ws2, '🏢 Traffic Organisasi')

  // Sheet 3 — Admin Monitoring
  const ws3 = XLSX.utils.aoa_to_sheet([
    ['👥 ADMIN MONITORING & ACTIVITY'],
    [],
    ['Admin', 'Role', 'Organisasi', 'Aksi Terbaru', 'Aktivitas Mencurigakan'],
    ...(trackData?.admins || []).map((a) => [
      a.username,
      a.role.toUpperCase(),
      a.organization_name || 'Global',
      (a.recent_actions || []).slice(0, 3).map((x) => x.action).join('; '),
      (a.suspicious_actions || []).length,
    ]),
  ])
  ws3['!cols'] = [{ wch: 22 }, { wch: 14 }, { wch: 24 }, { wch: 45 }, { wch: 22 }]
  XLSX.utils.book_append_sheet(wb, ws3, '👥 Admin Monitoring')

  // Sheet 4 — Suspicious Activity
  const ws4 = XLSX.utils.aoa_to_sheet([
    ['⚠️ AKTIVITAS MENCURIGAKAN - ALERT LOG'],
    [],
    ['User', 'Action', 'IP Address', 'Detail', 'Waktu'],
    ...(trackData?.suspicious_activities || []).map((s) => [
      s.user, 
      s.action, 
      s.ip_address || '—', 
      s.details || '—', 
      (s.created_at || '').split('.')[0],
    ]),
  ])
  ws4['!cols'] = [{ wch: 22 }, { wch: 24 }, { wch: 18 }, { wch: 42 }, { wch: 22 }]
  XLSX.utils.book_append_sheet(wb, ws4, '⚠️ Aktivitas Mencurigakan')

  XLSX.writeFile(wb, `CogniMail_Tracking_Report_${stamp(when)}.xlsx`)
}

export async function exportTrackingPDF(trackData, when = new Date()) {
  const { default: jsPDF } = await import('jspdf')
  const { default: autoTable } = await import('jspdf-autotable')

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  let y = 20

  // Professional Header with Color Bar
  doc.setFillColor(26, 115, 232) // Gmail Blue
  doc.rect(0, 0, 210, 38, 'F')
  
  doc.setTextColor(255, 255, 255)
  doc.setFontSize(22)
  doc.setFont('helvetica', 'bold')
  doc.text('CogniMail', 14, 16)
  
  doc.setFontSize(11)
  doc.setFont('helvetica', 'normal')
  doc.text('ML-Powered Anti-Phishing & Spam Filtering Platform', 14, 23)
  
  doc.setFontSize(9)
  doc.text(`Report Generated: ${when.toLocaleDateString('id-ID', { dateStyle: 'full' })} • ${when.toLocaleTimeString('id-ID')}`, 14, 30)
  
  // Report Title
  y = 48
  doc.setTextColor(32, 33, 36)
  doc.setFontSize(16)
  doc.setFont('helvetica', 'bold')
  doc.text('Tracking & Analytics Report', 14, y)
  
  y += 10

  // Platform Summary Section
  doc.setFontSize(13)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(26, 115, 232)
  doc.text('📊 Platform Summary', 14, y)
  y += 2

  autoTable(doc, {
    startY: y,
    head: [['Metrik', 'Nilai']],
    body: [
      ['Total Email', (trackData?.total_emails ?? 0).toLocaleString()],
      ['✅ Clean', (trackData?.total_clean ?? 0).toLocaleString()],
      ['⚠️ Peringatan', (trackData?.total_warn ?? 0).toLocaleString()],
      ['🛡️ Karantina', (trackData?.total_quarantine ?? 0).toLocaleString()],
    ],
    styles: {
      fontSize: 10,
      cellPadding: 4,
    },
    headStyles: {
      fillColor: [26, 115, 232],
      textColor: [255, 255, 255],
      fontSize: 11,
      fontStyle: 'bold',
      halign: 'center',
    },
    columnStyles: {
      0: { fontStyle: 'bold', cellWidth: 80 },
      1: { halign: 'right', cellWidth: 102 },
    },
    alternateRowStyles: {
      fillColor: [248, 249, 250],
    },
    margin: { left: 14, right: 14 },
  })
  y = doc.lastAutoTable.finalY + 12

  // Organization Traffic Section
  if (y > 210) { doc.addPage(); y = 20 }
  
  doc.setFontSize(13)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(52, 168, 83)
  doc.text('🏢 Traffic per Organisasi', 14, y)
  y += 2

  autoTable(doc, {
    startY: y,
    head: [['Organisasi', 'Users', 'Total', 'Clean', 'Warn', 'Karantina']],
    body: (trackData?.organizations || []).map((o) => [
      o.organization_name || 'Unknown',
      o.users,
      o.total_emails,
      o.clean,
      o.warn,
      o.quarantine,
    ]),
    styles: {
      fontSize: 9,
      cellPadding: 4,
    },
    headStyles: {
      fillColor: [52, 168, 83],
      textColor: [255, 255, 255],
      fontSize: 10,
      fontStyle: 'bold',
      halign: 'center',
    },
    alternateRowStyles: {
      fillColor: [248, 249, 250],
    },
    columnStyles: {
      0: { cellWidth: 52 },
      1: { halign: 'center', cellWidth: 20 },
      2: { halign: 'center', cellWidth: 26 },
      3: { halign: 'center', cellWidth: 24 },
      4: { halign: 'center', cellWidth: 24 },
      5: { halign: 'center', cellWidth: 26 },
    },
    margin: { left: 14, right: 14 },
  })
  y = doc.lastAutoTable.finalY + 12

  // Admin Monitoring Section
  if (y > 210) { doc.addPage(); y = 20 }
  
  doc.setFontSize(13)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(251, 188, 5)
  doc.text('👥 Admin Monitoring', 14, y)
  y += 2

  autoTable(doc, {
    startY: y,
    head: [['Admin', 'Role', 'Organisasi', 'Aksi Terbaru']],
    body: (trackData?.admins || []).map((a) => [
      a.username,
      a.role.toUpperCase(),
      a.organization_name || 'Global',
      (a.recent_actions || [])
        .slice(0, 2)
        .map((x) => x.action)
        .join(', ') || '—',
    ]),
    styles: {
      fontSize: 9,
      cellPadding: 4,
    },
    headStyles: {
      fillColor: [251, 188, 5],
      textColor: [255, 255, 255],
      fontSize: 10,
      fontStyle: 'bold',
      halign: 'center',
    },
    alternateRowStyles: {
      fillColor: [254, 252, 242],
    },
    columnStyles: {
      0: { cellWidth: 36 },
      1: { halign: 'center', cellWidth: 26, fontStyle: 'bold' },
      2: { cellWidth: 42 },
      3: { cellWidth: 88, fontSize: 8 },
    },
    margin: { left: 14, right: 14 },
  })
  y = doc.lastAutoTable.finalY + 12

  // Suspicious Activity Section
  if (y > 210) { doc.addPage(); y = 20 }
  
  doc.setFontSize(13)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(234, 67, 53)
  doc.text('⚠️ Aktivitas Mencurigakan', 14, y)
  y += 2

  autoTable(doc, {
    startY: y,
    head: [['User', 'Action', 'IP Address', 'Waktu']],
    body: (trackData?.suspicious_activities || []).map((s) => [
      s.user,
      s.action,
      s.ip_address || '—',
      new Date(s.created_at).toLocaleString('id-ID', { 
        dateStyle: 'short', 
        timeStyle: 'short' 
      }),
    ]),
    styles: {
      fontSize: 9,
      cellPadding: 4,
    },
    headStyles: {
      fillColor: [234, 67, 53],
      textColor: [255, 255, 255],
      fontSize: 10,
      fontStyle: 'bold',
      halign: 'center',
    },
    alternateRowStyles: {
      fillColor: [254, 242, 242],
    },
    columnStyles: {
      0: { cellWidth: 42 },
      1: { cellWidth: 62 },
      2: { halign: 'center', cellWidth: 36 },
      3: { halign: 'center', cellWidth: 42 },
    },
    margin: { left: 14, right: 14 },
  })

  // Professional Footer on all pages
  const pageCount = doc.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    
    // Footer line
    doc.setDrawColor(224, 224, 224)
    doc.setLineWidth(0.5)
    doc.line(14, 285, 196, 285)
    
    // Footer text
    doc.setFontSize(8)
    doc.setTextColor(158, 160, 166)
    doc.setFont('helvetica', 'normal')
    doc.text('CogniMail - ML-Powered Email Security Platform', 14, 290)
    doc.text(`Page ${i} of ${pageCount}`, 196, 290, { align: 'right' })
    
    // Confidential notice
    doc.setFontSize(7)
    doc.setTextColor(200, 200, 200)
    doc.text('CONFIDENTIAL - For Internal Use Only', 105, 293, { align: 'center' })
  }

  doc.save(`CogniMail_Tracking_Report_${stamp(when)}.pdf`)
}
