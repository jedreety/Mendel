# Demarre l'interface du bot evolutif, apres avoir prepare ce qui manque :
#   1. le venv .venv et PyTorch (requirements.txt, roue CUDA 13.0) ;
#   2. l'application web (interface/web), construite par Node.js ;
#   3. le marche par defaut de evolution/config.toml, BTCUSDT horaire de 2018 a 2025 ;
#   4. puis python -m interface.serveur --ouvrir, qui ouvre le navigateur.
# Chaque etape ne se refait que si elle le doit : un nouveau requirements.txt, un nouveau package-lock.json, des
# sources web plus recentes que leur construction, un marche absent. Les arguments passent au serveur :
#   demarrer.cmd --port 8800
# Pas de $ErrorActionPreference = 'Stop' : sous Windows PowerShell 5.1, il fait d'un avertissement ecrit par pip ou
# npm une erreur. Chaque commande externe est verifiee par son code de sortie.

$racine = $PSScriptRoot
$venv = Join-Path $racine '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
$web = Join-Path $racine 'interface\web'
$marche = Join-Path $racine 'data\prepared\BTCUSDT-1h.csv'
Set-Location $racine

function Etape([string] $texte) { Write-Host "== $texte" -ForegroundColor Cyan }

function Echec([string] $texte) {
    Write-Host $texte -ForegroundColor Red
    exit 1
}

function Verifier([string] $quoi) {
    if ($LASTEXITCODE -ne 0) { Echec "$quoi : echec (code $LASTEXITCODE)." }
}

function Differe([string] $fichier, [string] $copie) {
    -not (Test-Path $copie) -or (Get-FileHash $fichier).Hash -ne (Get-FileHash $copie).Hash
}

# --- 1. Python et PyTorch ---
if (-not (Test-Path $python)) {
    # Python 3.11 au moins (tomllib, datetime.UTC) : le lanceur py de python.org d'abord, en 3.13 de preference.
    $base = $null
    foreach ($commande in 'py -3.13', 'py -3', 'python') {
        $mots = $commande -split ' '
        if (-not (Get-Command $mots[0] -ErrorAction SilentlyContinue)) { continue }
        $options = @($mots | Select-Object -Skip 1)
        $recent = & $mots[0] @options -c 'import sys; print(sys.version_info >= (3, 11))' 2>$null
        if ($LASTEXITCODE -eq 0 -and $recent -eq 'True') { $base = $mots; break }
    }
    if (-not $base) {
        Echec 'Python 3.11 ou plus introuvable. Installez-le depuis https://www.python.org (ou : winget install Python.Python.3.13), puis relancez.'
    }
    Etape "Creation du venv .venv ($($base -join ' '))"
    $options = @($base | Select-Object -Skip 1)
    & $base[0] @options -m venv $venv
    Verifier 'Creation du venv'
}

$installe = Join-Path $venv 'requirements.txt'
if (Differe (Join-Path $racine 'requirements.txt') $installe) {
    Etape 'Installation de PyTorch, roue CUDA 13.0 (plus de 2 Go la premiere fois)'
    & $python -m pip install --disable-pip-version-check -r requirements.txt --index-url https://download.pytorch.org/whl/cu130
    Verifier 'Installation de requirements.txt'
    Copy-Item (Join-Path $racine 'requirements.txt') $installe
}

if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    Write-Host "Aucune GPU NVIDIA detectee : l'interface s'ouvre, mais l'entrainement exige une GPU NVIDIA et son pilote." -ForegroundColor Yellow
}

# --- 2. Application web ---
$page = Join-Path $web 'dist\index.html'
$verrou = Join-Path $web 'package-lock.json'
$sources = @(Get-ChildItem (Join-Path $web 'src') -Recurse -File) +
    @(Get-Item (Join-Path $web 'index.html'), (Join-Path $web 'vite.config.js'), (Join-Path $web 'package.json'), $verrou)
$recente = ($sources | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
$aJour = (Test-Path $page) -and (Get-Item $page).LastWriteTime -ge $recente

if (-not $aJour) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        if (-not (Test-Path $page)) {
            Echec "Node.js 20.19 ou plus construit l'application web. Installez-le depuis https://nodejs.org (ou : winget install OpenJS.NodeJS.LTS), puis relancez."
        }
        Write-Host "Node.js absent : l'application web deja construite est gardee, sans les dernieres modifications." -ForegroundColor Yellow
    }
    else {
        $node = [version]((& node --version).TrimStart('v'))
        if ($node -lt [version]'20.19.0') { Echec "Node.js $node est trop ancien : il faut la 20.19 ou plus (https://nodejs.org)." }
        Push-Location $web
        $copie = Join-Path $web 'node_modules\.package-lock.installe.json'
        if (Differe $verrou $copie) {
            Etape "Installation des paquets de l'application web (npm ci)"
            & npm.cmd ci --no-audit --no-fund
            Verifier 'npm ci'
            Copy-Item $verrou $copie
        }
        Etape "Construction de l'application web (npm run build)"
        & npm.cmd run build
        Verifier 'npm run build'
        Pop-Location
    }
}

# --- 3. Marche par defaut ---
if (-not (Test-Path $marche)) {
    Etape 'Telechargement du marche par defaut : BTCUSDT horaire, janvier 2018 a decembre 2025 (data.binance.vision)'
    $fini = $false
    try {
        & $python -m scripts.fetch_binance BTCUSDT 1h 2018-01 2025-12
        $fini = $LASTEXITCODE -eq 0
    }
    finally {
        # Un telechargement interrompu laisserait un fichier tronque, pris ensuite pour un marche complet.
        if (-not $fini) { Remove-Item $marche -ErrorAction SilentlyContinue }
    }
    if (-not $fini) { Echec 'Telechargement du marche : echec. Relancez pour reprendre : les mois deja recus sont gardes.' }
}

# --- 4. Interface ---
Etape 'Interface'
& $python -m interface.serveur --ouvrir @args
exit $LASTEXITCODE
