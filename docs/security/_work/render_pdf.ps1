param([string]$Pdf, [string]$OutDir, [int]$Width = 850)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
Add-Type -AssemblyName System.Drawing
[void][Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
[void][Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
[void][Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$ext = [System.WindowsRuntimeSystemExtensions].GetMethods()
$asTaskOp = ($ext | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asTaskAct = ($ext | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function Await-Op($op, $type) { $t = $asTaskOp.MakeGenericMethod($type).Invoke($null, @($op)); [void]$t.Wait(-1); return $t.Result }
function Await-Act($act) { $t = $asTaskAct.Invoke($null, @($act)); [void]$t.Wait(-1) }
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter "p-*.png" -ErrorAction SilentlyContinue | Remove-Item -Force
$file = Await-Op ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Pdf)) ([Windows.Storage.StorageFile])
$doc = Await-Op ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
for ($i = 0; $i -lt $doc.PageCount; $i++) {
  $page = $doc.GetPage($i)
  $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
  $opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
  $opts.DestinationWidth = $Width
  Await-Act ($page.RenderToStreamAsync($stream, $opts))
  $stream.Seek(0)
  $bytes = New-Object byte[] ([int]$stream.Size)
  $reader = New-Object Windows.Storage.Streams.DataReader($stream)
  Await-Op ($reader.LoadAsync([uint32]$stream.Size)) ([uint32]) | Out-Null
  $reader.ReadBytes($bytes)
  [IO.File]::WriteAllBytes((Join-Path $OutDir ("p-{0:D2}.png" -f ($i + 1))), $bytes)
  $page.Dispose()
}
"rendered $($doc.PageCount) pages to $OutDir"
