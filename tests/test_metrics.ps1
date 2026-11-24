$ErrorActionPreference = "Stop"

$baseUrl = "http://localhost:8090"

function Get-RequestCount {
    $content = (
        Invoke-WebRequest `
            -Uri "$baseUrl/metrics" `
            -UseBasicParsing
    ).Content

    $pattern = 'http_requests_total\{endpoint="/health",method="GET",status="200"\}\s+([0-9.eE+-]+)'

    $match = [regex]::Match($content, $pattern)

    if (-not $match.Success) {
        return 0
    }

    return [double]::Parse(
        $match.Groups[1].Value,
        [Globalization.CultureInfo]::InvariantCulture
    )
}

$before = Get-RequestCount

Write-Host "Before: $before"

1..5 | ForEach-Object {
    Invoke-RestMethod `
        -Uri "$baseUrl/health" | Out-Null
}

$after = Get-RequestCount
$difference = $after - $before

Write-Host "After: $after"
Write-Host "Difference: $difference"

if ($difference -ne 5) {
    throw "FAILED: expected 5 requests, got $difference"
}

Write-Host "PASSED: HTTP request counter" -ForegroundColor Green