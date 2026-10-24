$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$tempDir = "C:\Users\mraye\repogen_shots"
$finalDir = "C:\repo gen\ux-audit-after"

if (!(Test-Path $tempDir)) { New-Item -ItemType Directory -Path $tempDir -Force }
if (!(Test-Path $finalDir)) { New-Item -ItemType Directory -Path $finalDir -Force }

$screens = @(
    @{ File = "01-connection-after.png"; Url = "http://127.0.0.1:8085/index.html"; Size = "1024,768" },
    @{ File = "02-tags-after.png"; Url = "http://127.0.0.1:8085/index.html#tags"; Size = "1024,768" },
    @{ File = "03-add-tag-after.png"; Url = "http://127.0.0.1:8085/index.html#add-tag"; Size = "1024,768" },
    @{ File = "04-write-after.png"; Url = "http://127.0.0.1:8085/index.html#write"; Size = "1024,768" },
    @{ File = "01-connection-800x600.png"; Url = "http://127.0.0.1:8085/index.html"; Size = "800,600" },
    @{ File = "02-tags-800x600.png"; Url = "http://127.0.0.1:8085/index.html#tags"; Size = "800,600" },
    @{ File = "01-connection-1440x900.png"; Url = "http://127.0.0.1:8085/index.html"; Size = "1440,900" },
    @{ File = "02-tags-1440x900.png"; Url = "http://127.0.0.1:8085/index.html#tags"; Size = "1440,900" }
)

foreach ($s in $screens) {
    $outPath = Join-Path $tempDir $s.File
    $args = @(
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--screenshot=$outPath",
        "--window-size=$($s.Size)",
        "--virtual-time-budget=1500",
        $s.Url
    )
    Write-Host "Capturing $($s.File) at $($s.Size)..."
    Start-Process -FilePath $chrome -ArgumentList $args -Wait
    Copy-Item $outPath (Join-Path $finalDir $s.File) -Force
}

Get-ChildItem $finalDir | Select-Object Name, Length
