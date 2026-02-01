$json_path = "c:\Users\dluce\Projects\CleanOCR\ocr_jsonv2"
$md_path = "c:\Users\dluce\Projects\CleanOCR\CleanOCR_Finalv2\pages"

if (-not (Test-Path $json_path)) { Write-Error "Input Path Not Found: $json_path"; exit 1 }
if (-not (Test-Path $md_path)) { Write-Error "Output Path Not Found: $md_path"; exit 1 }

$json_count = (Get-ChildItem -Path $json_path -Filter "*.json").Count
$md_count = (Get-ChildItem -Path $md_path -Filter "*.md").Count

Write-Host "Input JSON Count: $json_count"
Write-Host "Output MD Count:  $md_count"

if ($json_count -ne $md_count) { 
    Write-Error "Mismatch: Input $json_count vs Output $md_count" 
    exit 1
} else { 
    Write-Host "SUCCESS: 1:1 Parity Achieved" -ForegroundColor Green
}
