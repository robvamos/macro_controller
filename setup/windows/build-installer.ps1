param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

Write-Host "Windows setup scaffold for DDGameAss"
Write-Host "Project root: $ProjectRoot"
Write-Host "Questo script e' uno stub iniziale per il futuro processo di packaging."
Write-Host "Passi previsti:"
Write-Host "  1. Creare ambiente build"
Write-Host "  2. Raccogliere runtime Python e dipendenze"
Write-Host "  3. Assemblare asset applicativi"
Write-Host "  4. Generare installer Windows"
