$ErrorActionPreference = "Stop"
$work = "C:\helply\docs\security\_work"
$out  = "C:\helply\docs\security\Helply_Penetration_Test_Report.docx"
$pdf  = "C:\helply\docs\security\_work\Helply_Penetration_Test_Report.pdf"

# Colours (Word wants BGR integers)
function RGBc($r,$g,$b){ return $r + 256*$g + 65536*$b }
$NAVY = RGBc 11 27 43; $TEAL = RGBc 14 116 144; $GRAY = RGBc 71 85 105; $LINECOL = RGBc 208 213 221; $ZEBRA = RGBc 245 248 251; $WHITE = RGBc 255 255 255

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.Options.AutoFormatAsYouTypeApplyBorders = $false
try {
  $doc = $word.Documents.Add()
  $sel = $word.Selection
  $ps = $doc.PageSetup
  $ps.PageWidth = 612; $ps.PageHeight = 792
  $ps.TopMargin = 72; $ps.BottomMargin = 72; $ps.LeftMargin = 72; $ps.RightMargin = 72

  # ---- styles ----
  $n = $doc.Styles.Item(-1); $n.Font.Name = "Calibri"; $n.Font.Size = 11; $n.Font.Color = RGBc 29 36 51
  $n.ParagraphFormat.SpaceAfter = 6; $n.ParagraphFormat.SpaceBefore = 0; $n.ParagraphFormat.LineSpacingRule = 5; $n.ParagraphFormat.LineSpacing = 13.2
  $n.ParagraphFormat.Alignment = 0
  $h1 = $doc.Styles.Item(-2); $h1.Font.Name = "Calibri"; $h1.Font.Size = 22; $h1.Font.Bold = 1; $h1.Font.Color = $NAVY
  $h1.ParagraphFormat.SpaceBefore = 0; $h1.ParagraphFormat.SpaceAfter = 12; $h1.ParagraphFormat.PageBreakBefore = -1; $h1.ParagraphFormat.KeepWithNext = -1
  $h2 = $doc.Styles.Item(-3); $h2.Font.Name = "Calibri"; $h2.Font.Size = 15; $h2.Font.Bold = 1; $h2.Font.Color = $TEAL
  $h2.ParagraphFormat.SpaceBefore = 16; $h2.ParagraphFormat.SpaceAfter = 6; $h2.ParagraphFormat.KeepWithNext = -1
  $h3 = $doc.Styles.Item(-4); $h3.Font.Name = "Calibri"; $h3.Font.Size = 12.5; $h3.Font.Bold = 1; $h3.Font.Color = $NAVY
  $h3.ParagraphFormat.SpaceBefore = 8; $h3.ParagraphFormat.SpaceAfter = 3; $h3.ParagraphFormat.KeepWithNext = -1
  $cap = $doc.Styles.Item(-35); $cap.Font.Name = "Calibri"; $cap.Font.Size = 9.5; $cap.Font.Italic = 1; $cap.Font.Bold = 0; $cap.Font.Color = $GRAY
  $cap.ParagraphFormat.Alignment = 1; $cap.ParagraphFormat.SpaceBefore = 4; $cap.ParagraphFormat.SpaceAfter = 12
  foreach ($id in -49,-55) { $b = $doc.Styles.Item($id); $b.Font.Name = "Calibri"; $b.Font.Size = 11; $b.ParagraphFormat.SpaceAfter = 3; $b.ParagraphFormat.LineSpacingRule = 5; $b.ParagraphFormat.LineSpacing = 13.2 }

  foreach ($id in -1,-2,-3,-4,-35,-49,-55) { $doc.Styles.Item([int]$id).Font.NameFarEast = 'Microsoft YaHei' }
  # ---- helpers ----
  function Parse-Rich([string]$raw) {
    $segs = @(); $pos = 0
    foreach ($m in [regex]::Matches($raw, '\*\*(.+?)\*\*|\{\{(.+?)\}\}')) {
      if ($m.Index -gt $pos) { $segs += ,@($raw.Substring($pos, $m.Index - $pos), 'plain') }
      if ($m.Groups[1].Success) { $segs += ,@($m.Groups[1].Value, 'bold') } else { $segs += ,@($m.Groups[2].Value, 'mark') }
      $pos = $m.Index + $m.Length
    }
    if ($pos -lt $raw.Length) { $segs += ,@($raw.Substring($pos), 'plain') }
    return ,$segs
  }
  function Apply-Marks($startPos, $segs) {
    $off = 0
    foreach ($s in $segs) {
      $len = $s[0].Length
      if ($s[1] -eq 'bold') { $doc.Range($startPos + $off, $startPos + $off + $len).Font.Bold = 1 }
      elseif ($s[1] -eq 'mark') { $r = $doc.Range($startPos + $off, $startPos + $off + $len); $r.Font.Shading.BackgroundPatternColor = 65535 }
      $off += $len
    }
  }
  function Add-Para([string]$raw, [int]$style = -1) {
    $sel.EndKey(6) | Out-Null
    $sel.Style = $doc.Styles.Item($style)
    $sel.Font.Reset()   # a highlighted or bold run must not leak into the next paragraph
    $sel.ParagraphFormat.Alignment = 0
    $segs = Parse-Rich $raw
    $plain = ($segs | ForEach-Object { $_[0] }) -join ''
    $start = $sel.Start
    $sel.TypeText($plain)
    Apply-Marks $start $segs
    $sel.TypeParagraph()
  }
  function Fill-Cell($cell, [string]$raw) {
    $segs = Parse-Rich $raw
    $plain = ($segs | ForEach-Object { $_[0] }) -join ''
    $cell.Range.Text = $plain
    Apply-Marks $cell.Range.Start $segs
  }
  function Add-Table([string]$caption, $ratios, $rows) {
    $sel.EndKey(6) | Out-Null
    $sel.Style = $doc.Styles.Item(-1)
    $nc = $rows[0].Count; $nr = $rows.Count
    if ($nr -le 9 -and $doc.Paragraphs.Count -gt 1) { $doc.Paragraphs.Item($doc.Paragraphs.Count - 1).KeepWithNext = -1 }  # the lead-in stays with a short table
    $t = $doc.Tables.Add($sel.Range, $nr, $nc)
    $t.AllowAutoFit = $false
    $t.PreferredWidthType = 2; $t.PreferredWidth = 100
    $sum = ($ratios | Measure-Object -Sum).Sum
    for ($c = 1; $c -le $nc; $c++) { $col = $t.Columns.Item($c); $col.PreferredWidthType = 2; $col.PreferredWidth = [math]::Round(100.0 * $ratios[$c-1] / $sum, 1) }
    $t.Range.Font.Size = 9.5
    $t.Range.ParagraphFormat.SpaceAfter = 0; $t.Range.ParagraphFormat.SpaceBefore = 0; $t.Range.ParagraphFormat.LineSpacingRule = 0
    $t.TopPadding = 3; $t.BottomPadding = 3; $t.LeftPadding = 5; $t.RightPadding = 5
    $t.Borders.InsideLineStyle = 1; $t.Borders.OutsideLineStyle = 1; $t.Borders.InsideColor = $LINECOL; $t.Borders.OutsideColor = $LINECOL
    for ($r = 1; $r -le $nr; $r++) { for ($c = 1; $c -le $nc; $c++) { Fill-Cell $t.Cell($r, $c) $rows[$r-1][$c-1] } }
    $hdr = $t.Rows.Item(1); $hdr.HeadingFormat = -1; $hdr.Shading.BackgroundPatternColor = $NAVY; $hdr.Range.Font.Color = $WHITE; $hdr.Range.Font.Bold = 1
    for ($r = 3; $r -le $nr; $r += 2) { $t.Rows.Item($r).Shading.BackgroundPatternColor = $ZEBRA }
    $t.Rows.AllowBreakAcrossPages = 0
    # keep small tables on one page; in long ones never leave the header or a single last row on its own
    if ($nr -le 9) { for ($r = 1; $r -le $nr; $r++) { $t.Rows.Item($r).Range.ParagraphFormat.KeepWithNext = -1 } }
    else {
      foreach ($r in 1, 2, ($nr - 1), $nr) { $t.Rows.Item($r).Range.ParagraphFormat.KeepWithNext = -1 }
    }
    $t.Range.InsertCaption(-2, ": " + $caption, "", 1, 0)
    $sel.EndKey(6) | Out-Null
    if ($doc.Paragraphs.Last.Range.Text.Trim() -ne "") { $sel.TypeParagraph() }
  }
  function Add-Signature($labels) {
    $sel.EndKey(6) | Out-Null
    $sel.Style = $doc.Styles.Item(-1)
    $t = $doc.Tables.Add($sel.Range, $labels.Count, 2)
    $t.AllowAutoFit = $false; $t.PreferredWidthType = 2; $t.PreferredWidth = 100
    $t.Columns.Item(1).PreferredWidthType = 2; $t.Columns.Item(1).PreferredWidth = 32
    $t.Columns.Item(2).PreferredWidthType = 2; $t.Columns.Item(2).PreferredWidth = 68
    $t.Borders.Enable = $false
    for ($r = 1; $r -le $labels.Count; $r++) {
      $t.Cell($r, 1).Range.Text = $labels[$r - 1]; $t.Cell($r, 1).Range.Font.Bold = 1
      $t.Rows.Item($r).HeightRule = 1; $t.Rows.Item($r).Height = 36
      $t.Cell($r, 1).VerticalAlignment = 3; $t.Cell($r, 2).VerticalAlignment = 3
      $bb = $t.Cell($r, 2).Borders.Item(-3); $bb.LineStyle = 1; $bb.Color = $NAVY
    }
    $sel.EndKey(6) | Out-Null; $sel.TypeParagraph()
  }  function Add-Figure([string]$rel, [string]$caption, [double]$inches) {
    $sel.EndKey(6) | Out-Null
    $sel.Style = $doc.Styles.Item(-1)
    $sel.ParagraphFormat.Alignment = 1
    $sel.ParagraphFormat.KeepWithNext = -1
    $pic = $doc.InlineShapes.AddPicture((Join-Path $work $rel), $false, $true, $sel.Range)
    $pic.LockAspectRatio = -1; $pic.Width = $inches * 72
    $pic.Range.InsertCaption(-1, ": " + $caption, "", 1, 0)
    $sel.EndKey(6) | Out-Null
    if ($doc.Paragraphs.Last.Range.Text.Trim() -ne "") { $sel.TypeParagraph() }
    $sel.Style = $doc.Styles.Item(-1)
    $sel.ParagraphFormat.Alignment = 0
    $sel.ParagraphFormat.KeepWithNext = 0
  }

  # ================= COVER =================
  $sel.Style = $doc.Styles.Item(-1)
  $sel.ParagraphFormat.Alignment = 1
  $sel.ParagraphFormat.SpaceBefore = 6
  $logo = $doc.InlineShapes.AddPicture("C:\helply\static\img\brand\app-icon-256.png", $false, $true, $sel.Range)
  $logo.LockAspectRatio = -1; $logo.Width = 84
  $sel.EndKey(6) | Out-Null; $sel.TypeParagraph()
  function Cover-Line([string]$text, [double]$size, [bool]$bold, $color, [double]$before = 0, [double]$after = 6) {
    $sel.EndKey(6) | Out-Null
    $sel.Style = $doc.Styles.Item(-1)
    $sel.ParagraphFormat.Alignment = 1; $sel.ParagraphFormat.SpaceBefore = $before; $sel.ParagraphFormat.SpaceAfter = $after
    $sel.Font.Size = $size; $sel.Font.Bold = [int]$bold; $sel.Font.Color = $color
    $sel.TypeText($text); $sel.TypeParagraph()
  }
  Cover-Line "Helply" 44 $true $NAVY 12 2
  Cover-Line "面向中小企业的 AI 辅助 IT 服务台" 17 $false $TEAL 0 30
  Cover-Line "渗透测试与安全评估报告" 28 $true $NAVY 18 2
  Cover-Line "Penetration Test and Security Assessment" 17 $false $NAVY 0 6
  Cover-Line "目标：https://helply.work 及 Helply 代码库  |  机密，仅限项目团队" 12 $false $GRAY 0 36
  Cover-Line "MGMT6134 Capstone Project" 14 $true $NAVY 0 2
  Cover-Line "Fanshawe College" 12 $false $GRAY 0 12
  Cover-Line "测试授权人：XIEKAIXIN（项目负责人）" 12 $false $NAVY 0 6; Cover-Line "测试执行：Claude（AI 辅助安全测试）" 12 $false $NAVY 0 18
  Cover-Line "项目团队" 12 $true $TEAL 6 6
  $team = @("XIEKAIXIN (Team Leader)", "Chinazor Tochukwu Okehie", "Daniel Wasike", "Ugochukwu Christopher Nwozor")
  foreach ($m in $team) { Cover-Line $m 13 $false $NAVY 0 2 }
  Cover-Line "" 6 $false $NAVY 0 4
  $sel.EndKey(6) | Out-Null
  $sel.Style = $doc.Styles.Item(-1); $sel.ParagraphFormat.Alignment = 1; $sel.Font.Size = 11
  $vt = $doc.Tables.Add($sel.Range, 1, 2)
  $vt.Cell(1,1).Range.Text = "Version 1.0"; $vt.Cell(1,2).Range.Text = "October 5, 2026"
  $vt.Range.Font.Size = 11; $vt.Range.Font.Bold = 1; $vt.Range.Font.Color = $NAVY; $vt.Range.ParagraphFormat.Alignment = 1
  $vt.Borders.Enable = $true; $vt.Borders.InsideColor = $LINECOL; $vt.Borders.OutsideColor = $LINECOL
  $vt.AllowAutoFit = $false; $vt.PreferredWidthType = 3; $vt.PreferredWidth = 270; $vt.Rows.Alignment = 1
  $vt.TopPadding = 5; $vt.BottomPadding = 5
  $sel.EndKey(6) | Out-Null
  $sel.InsertBreak(2)   # next-page section break: the cover has no footer

  # ================= FRONT MATTER =================
  $sel.Style = $doc.Styles.Item(-1); $sel.ParagraphFormat.Alignment = 0; $sel.Font.Size = 11; $sel.Font.Bold = 0; $sel.Font.Color = RGBc 29 36 51
  $sel.ParagraphFormat.SpaceBefore = 0
  function Front-Title([string]$text) {
    $sel.EndKey(6) | Out-Null
    $sel.Style = $doc.Styles.Item(-1); $sel.ParagraphFormat.Alignment = 0
    $sel.Font.Size = 22; $sel.Font.Bold = 1; $sel.Font.Color = $NAVY; $sel.ParagraphFormat.SpaceAfter = 12
    $sel.TypeText($text); $sel.TypeParagraph()
    $sel.Style = $doc.Styles.Item(-1)
  }
  Front-Title "目录"
  $sel.EndKey(6) | Out-Null
  $toc = $doc.TablesOfContents.Add($sel.Range, $true, 1, 2)
  $sel.EndKey(6) | Out-Null; $sel.InsertBreak(7)
  Front-Title "表格目录"
  $sel.EndKey(6) | Out-Null
  $tot = $doc.TablesOfFigures.Add($sel.Range, "Table", $true)
  $sel.EndKey(6) | Out-Null; $sel.TypeParagraph()

  # ================= BODY FROM MARKUP =================
  $lines = @()
  foreach ($f in "report.txt") { $lines += [IO.File]::ReadAllLines((Join-Path $work $f), [Text.Encoding]::UTF8) }
  $i = 0
  while ($i -lt $lines.Count) {
    $line = $lines[$i]
    if ($line.Trim() -eq "") { $i++; continue }
    if ($line -match '^\[table:\s*(.+?)\s*\|\s*widths=([\d,\.]+)\]$') {
      $caption = $matches[1]; $ratios = $matches[2].Split(',') | ForEach-Object { [double]$_ }
      $rows = @(); $i++
      while ($lines[$i] -ne '[/table]') { $rows += ,($lines[$i].Split('|') | ForEach-Object { $_.Trim() }); $i++ }
      $i++
      Add-Table $caption $ratios $rows
      continue
    }
    if ($line -match '^\[signature:\s*(.+?)\]$') { Add-Signature ($matches[1].Split('|') | ForEach-Object { $_.Trim() }); $i++; continue }
    if ($line -eq '[/landscape]') {
      # two landscape blocks back to back: stay in landscape instead of adding an empty portrait page
      $k = $i + 1; while ($k -lt $lines.Count -and $lines[$k].Trim() -eq "") { $k++ }
      if ($k -lt $lines.Count -and $lines[$k] -eq '[landscape]') {
        $sel.EndKey(6) | Out-Null; $sel.InsertBreak(2); $i = $k + 1; continue
      }
    }
    if ($line -eq '[landscape]') {
      $sel.EndKey(6) | Out-Null; $sel.InsertBreak(2)
      $s = $doc.Sections.Item($doc.Sections.Count)
      $s.PageSetup.Orientation = 1
      $s.PageSetup.TopMargin = 50; $s.PageSetup.BottomMargin = 50; $s.PageSetup.LeftMargin = 46; $s.PageSetup.RightMargin = 46
      $i++; continue
    }
    if ($line -eq '[/landscape]') {
      $sel.EndKey(6) | Out-Null; $sel.InsertBreak(2)
      $s = $doc.Sections.Item($doc.Sections.Count)
      $s.PageSetup.Orientation = 0
      $s.PageSetup.TopMargin = 72; $s.PageSetup.BottomMargin = 72; $s.PageSetup.LeftMargin = 72; $s.PageSetup.RightMargin = 72
      $i++; continue
    }
    if ($line -match '^\[figure:\s*(.+?)\s*\|\s*(.+?)\s*\|\s*([\d\.]+)\]$') {
      Add-Figure $matches[1] $matches[2] ([double]$matches[3]); $i++; continue
    }
    if ($line.StartsWith('### ')) { Add-Para $line.Substring(4) -4 }
    elseif ($line.StartsWith('## ')) { Add-Para $line.Substring(3) -3 }
    elseif ($line.StartsWith('# ')) { Add-Para $line.Substring(2) -2 }
    elseif ($line.StartsWith('- ')) { Add-Para $line.Substring(2) -49 }
    else { Add-Para $line -1 }
    $i++
  }

  # ================= FOOTER / PAGE NUMBERS =================
  $sec2 = $doc.Sections.Item(2)
  $ft = $sec2.Footers.Item(1)
  $ft.LinkToPrevious = $false
  $ft.PageNumbers.RestartNumberingAtSection = $true; $ft.PageNumbers.StartingNumber = 1
  $fr = $ft.Range
  $fr.Text = "Helply  |  渗透测试与安全评估报告  |  机密"
  $fr.Font.Size = 9; $fr.Font.Color = $GRAY
  $end0 = $ft.Range; $end0.Collapse(0); $end0.InsertAlignmentTab(2, 0)   # right-aligned to the margin, in portrait and landscape alike
  $end = $ft.Range; $end.Collapse(0)
  [void]$doc.Fields.Add($end, 33)
  $ft.Range.Font.Size = 9; $ft.Range.Font.Color = $GRAY
  $doc.Sections.Item(1).Footers.Item(1).Range.Text = ""

  # ================= UPDATE + SAVE =================
  # tighter list-of-figures/tables entries so the two lists share one page
  $tofStyle = $doc.Styles.Item([int]-36)
  $tofStyle.ParagraphFormat.SpaceAfter = 0; $tofStyle.ParagraphFormat.SpaceBefore = 0
  $tofStyle.ParagraphFormat.LineSpacingRule = 0; $tofStyle.Font.Size = 9
  $doc.Repaginate()
  foreach ($t in $doc.TablesOfContents) { $t.Update() }
  foreach ($t in $doc.TablesOfFigures) { $t.Update() }
  $doc.Fields.Update() | Out-Null
  foreach ($t in $doc.TablesOfContents) { $t.Update() }
  foreach ($t in $doc.TablesOfFigures) { $t.Update() }
  $doc.SaveAs2($out, 16)
  $doc.ExportAsFixedFormat($pdf, 17)
  "pages: " + $doc.ComputeStatistics(2) + " | words: " + $doc.ComputeStatistics(0) + " | tables: " + $doc.Tables.Count + " | pictures: " + $doc.InlineShapes.Count
  $doc.Close($false)
} catch {
  "ERROR: " + $_.Exception.Message + " @ line " + $_.InvocationInfo.ScriptLineNumber
  try { $doc.Close($false) } catch {}
} finally {
  $word.Quit()
}
