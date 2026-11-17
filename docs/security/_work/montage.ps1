param([string]$Dir, [string]$Prefix = "sheet", [int]$Cols = 3, [int]$Rows = 2, [int]$ThumbW = 560, [string]$Pattern = "p-*.png")
Add-Type -AssemblyName System.Drawing
$files = Get-ChildItem $Dir -Filter $Pattern | Sort-Object Name
Get-ChildItem $Dir -Filter "$Prefix-*.png" -ErrorAction SilentlyContinue | Remove-Item -Force
$per = $Cols * $Rows; $sheet = 0
for ($start = 0; $start -lt $files.Count; $start += $per) {
  $sheet++
  $first = [System.Drawing.Image]::FromFile($files[$start].FullName)
  $thumbH = [int]($ThumbW * $first.Height / $first.Width); $first.Dispose()
  $bmp = New-Object System.Drawing.Bitmap ($Cols * ($ThumbW + 10) + 10), ($Rows * ($thumbH + 26) + 10)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.Clear([System.Drawing.Color]::FromArgb(70, 80, 95))
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
  for ($k = 0; $k -lt $per -and ($start + $k) -lt $files.Count; $k++) {
    $img = [System.Drawing.Image]::FromFile($files[$start + $k].FullName)
    $cx = 10 + ($k % $Cols) * ($ThumbW + 10); $cy = 10 + [math]::Floor($k / $Cols) * ($thumbH + 26)
    $g.DrawImage($img, $cx, $cy + 20, $ThumbW, $thumbH)
    $g.DrawString($files[$start + $k].BaseName, $font, [System.Drawing.Brushes]::White, $cx, $cy)
    $img.Dispose()
  }
  $bmp.Save((Join-Path $Dir ("{0}-{1:D2}.png" -f $Prefix, $sheet)), [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
}
"sheets: $sheet"
