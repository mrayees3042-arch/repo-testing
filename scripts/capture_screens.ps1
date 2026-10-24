$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$outDir = "C:\repo gen\ux-audit-after"
$userDataDir = "C:\temp\chrome-shot-profile"

if (!(Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force }
if (!(Test-Path $userDataDir)) { New-Item -ItemType Directory -Path $userDataDir -Force }

$screens = @(
    @{ Name = "01-connection-after.png"; Hash = ""; Size = "1024,768" },
    @{ Name = "02-tags-after.png"; Hash = "#tags"; Size = "1024,768" },
    @{ Name = "03-add-tag-after.png"; Hash = "#add-tag"; Size = "1024,768" },
    @{ Name = "04-write-after.png"; Hash = "#write"; Size = "1024,768" },
    @{ Name = "01-connection-800x600.png"; Hash = ""; Size = "800,600" },
    @{ Name = "02-tags-800x600.png"; Hash = "#tags"; Size = "800,600" },
    @{ Name = "01-connection-1440x900.png"; Hash = ""; Size = "1440,900" },
    @{ Name = "02-tags-1440x900.png"; Hash = "#tags"; Size = "1440,900" }
)

foreach ($s in $screens) {
    $outFile = Join-Path $outDir $s.Name
    $url = "file:///C:/repo%20gen/frontend/index.html" + $s.Hash
    $args = @(
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--user-data-dir=$userDataDir",
        "--window-size=$($s.Size)",
        "--virtual-time-budget=2000",
        "--screenshot=$outFile",
        $url
    )
    Write-Host "Capturing $($s.Name) at $($s.Size)..."
    Start-Process -FilePath $chrome -ArgumentList $args -Wait
}

Get-ChildItem $outDir | Select-Object Name, Length
