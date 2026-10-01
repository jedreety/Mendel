# Demarre l'interface du bot evolutif, apres avoir prepare ce qui manque :
#   1. Python 3.11 a 3.15 (sinon, propose de l'installer par winget), le venv .venv et PyTorch, dans la variante
#      qui convient a la machine : CUDA 13.0, la reference ; CUDA 12.6 pour une GPU anterieure aux RTX 20xx ou un
#      pilote NVIDIA anterieur a la 580 ; processeur seul sans GPU NVIDIA, l'entrainement exigeant alors une GPU ;
#   2. l'application web, livree construite dans interface/web/dist : Node.js ne la reconstruit que si ses sources
#      ne sont plus celles de sa construction (empreinte dans dist/.sources) ;
#   3. le marche par defaut de evolution/config.toml, BTCUSDT horaire de 2018 a 2025 ;
#   4. puis python -m interface.serveur --ouvrir, qui ouvre le navigateur.
# Chaque etape ne se refait que si elle le doit. Les arguments passent au serveur :
#   demarrer.cmd --port 8800
# Pas de $ErrorActionPreference = 'Stop' : sous Windows PowerShell 5.1, il fait d'un avertissement ecrit par pip ou
# npm une erreur. Chaque commande externe est verifiee par son code de sortie.

$racine = $PSScriptRoot
$venv = Join-Path $racine '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
$web = Join-Path $racine 'interface\web'
$marche = Join-Path $racine 'data\prepared\BTCUSDT-1h.csv'
$roues = @{
    cu130 = 'https://download.pytorch.org/whl/cu130'
    cu126 = 'https://download.pytorch.org/whl/cu126'
    cpu   = 'https://download.pytorch.org/whl/cpu'
}
Set-Location $racine

function Etape([string] $texte) { Write-Host "== $texte" -ForegroundColor Cyan }

function Avertir([string] $texte) { Write-Host $texte -ForegroundColor Yellow }

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

function Trouver-Python {
    # Python 3.11 au moins (tomllib, datetime.UTC), 3.15 au plus (roues de torch 2.14.0) ; 3.13 de preference.
    foreach ($commande in 'py -3.13', 'py -3.12', 'py -3.14', 'py -3.11', 'py -3.15', 'python') {
        $mots = @($commande -split ' ')
        if (-not (Get-Command $mots[0] -ErrorAction SilentlyContinue)) { continue }
        $options = @($mots | Select-Object -Skip 1)
        $convient = & $mots[0] @options -c 'import sys; print((3, 11) <= sys.version_info[:2] <= (3, 15))' 2>$null
        if ($LASTEXITCODE -eq 0 -and $convient -eq 'True') { return ,$mots }
    }
    return $null
}

function Installer-Python {
    # Seulement a la demande de l'utilisateur, dans une console ou il peut repondre.
    if (-not (Get-Command winget -ErrorAction SilentlyContinue) -or [Console]::IsInputRedirected) { return }
    $reponse = Read-Host "Python 3.11 a 3.15 est introuvable. L'installer maintenant (Python 3.13, par winget) ? [O/n]"
    if ($reponse -match '^[nN]') { return }
    & winget install --id Python.Python.3.13 --exact --source winget --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Variante-PyTorch([string] $calcul, [string] $pilote) {
    # NVRTC compile les noyaux du bot pour l'architecture exacte de la GPU. CUDA 13.0 demande une GPU de calcul 7.5
    # ou plus (RTX 20xx) et un pilote 580 ou plus ; CUDA 12.6, une GPU de calcul 5.0 a 9.0 et un pilote 528.33 ou
    # plus. $null : aucune roue ne convient.
    try { $c = [version]$calcul; $p = [version]$pilote } catch { return $null }
    if ($c -ge [version]'7.5' -and $p -ge [version]'580.0') { return 'cu130' }
    if ($c -ge [version]'5.0' -and $c -lt [version]'10.0' -and $p -ge [version]'528.33') { return 'cu126' }
    return $null
}

function Choisir-Variante {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        Avertir "Aucune GPU NVIDIA detectee : PyTorch sans CUDA. L'interface s'ouvre, mais l'entrainement exige une GPU NVIDIA."
        return 'cpu'
    }
    $ligne = @(& nvidia-smi --query-gpu=compute_cap,driver_version,name --format=csv,noheader 2>$null)[0]
    $calcul, $pilote, $nom = @(([string]$ligne -split ',', 3) | ForEach-Object { $_.Trim() })
    $variante = Variante-PyTorch $calcul $pilote
    if (-not $variante) {
        Avertir "GPU $nom (calcul $calcul, pilote $pilote) : aucune roue de PyTorch ne convient. Mettez le pilote NVIDIA a jour (580 ou plus) ; une GPU de calcul inferieur a 5.0 ne peut pas entrainer. PyTorch sans CUDA, en attendant."
        return 'cpu'
    }
    if ($variante -eq 'cu126' -and [version]$calcul -lt [version]'7.5') {
        Avertir "GPU $nom (calcul $calcul) : PyTorch CUDA 12.6, la roue CUDA 13.0 ne prend pas les GPU anterieures aux RTX 20xx."
    }
    elseif ($variante -eq 'cu126') {
        Avertir "Pilote NVIDIA $pilote : PyTorch CUDA 12.6. Un pilote 580 ou plus donnerait la roue CUDA 13.0 de reference."
    }
    return $variante
}

function Variante-Installee {
    # Lue dans la version de torch, sans l'importer : 2.14.0+cu130 donne cu130. Les roues de PyPI pour Windows,
    # sans suffixe, sont sans CUDA. $null sans torch.
    if (-not (Test-Path $python)) { return $null }
    $version = & $python -c "import importlib.metadata as m; print(m.version('torch'))" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $version) { return $null }
    if ($version -match '\+(\w+)$') { return $Matches[1] }
    return 'cpu'
}

function Empreinte-Web {
    # Les sources de l'application web, fins de ligne ramenees a LF : la meme empreinte apres un git clone.
    $sha = [Security.Cryptography.SHA256]::Create()
    $fichiers = @(Get-ChildItem (Join-Path $web 'src') -Recurse -File) + @(Get-Item (Join-Path $web 'index.html'),
        (Join-Path $web 'vite.config.js'), (Join-Path $web 'package.json'), (Join-Path $web 'package-lock.json'))
    $lignes = [string[]]@(foreach ($f in $fichiers) {
        $octets = [Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText($f.FullName).Replace("`r`n", "`n"))
        $f.FullName.Substring($web.Length + 1).Replace('\', '/') + ' ' + [BitConverter]::ToString($sha.ComputeHash($octets)).Replace('-', '')
    })
    [Array]::Sort($lignes, [StringComparer]::Ordinal)
    [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($lignes -join "`n"))).Replace('-', '').ToLower()
}

function Construire-Web([string] $empreinte) {
    # Vrai si Node.js a reconstruit l'application web.
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { return $false }
    $node = [version]((& node --version).TrimStart('v'))
    if ($node -lt [version]'20.19.0') {
        Avertir "Node.js $node est trop ancien pour construire l'application web : il faut la 20.19 ou plus."
        return $false
    }
    Push-Location $web
    try {
        $verrou = Join-Path $web 'package-lock.json'
        $copie = Join-Path $web 'node_modules\.package-lock.installe.json'
        if (Differe $verrou $copie) {
            Etape "Installation des paquets de l'application web (npm ci)"
            & npm.cmd ci --no-audit --no-fund | Out-Host  # a l'ecran, pas dans la valeur de la fonction
            if ($LASTEXITCODE -ne 0) { return $false }
            Copy-Item $verrou $copie
        }
        Etape "Construction de l'application web (npm run build)"
        & npm.cmd run build | Out-Host
        if ($LASTEXITCODE -ne 0) { return $false }
        Set-Content (Join-Path $web 'dist\.sources') $empreinte -Encoding ascii -NoNewline
        return $true
    }
    finally { Pop-Location }
}

# --- 1. Python et PyTorch ---
$installee = Variante-Installee
$voulue = $installee
$requis = Join-Path $racine 'requirements.txt'
$copieRequis = Join-Path $venv 'requirements.txt'
$aInstaller = -not $installee -or (Differe $requis $copieRequis)
if (-not $installee) { $voulue = Choisir-Variante }
elseif ($installee -eq 'cpu' -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    $voulue = Choisir-Variante  # une GPU NVIDIA est peut-etre apparue depuis l'installation
    $aInstaller = $aInstaller -or $voulue -ne 'cpu'
}
if (-not $roues.ContainsKey($voulue)) { $voulue = Choisir-Variante }

if ($aInstaller) {
    $cheminsLongs = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction SilentlyContinue).LongPathsEnabled -eq 1
    if (-not $cheminsLongs -and $racine.Length -gt 100) {
        Echec "Le dossier $racine est trop profond pour installer PyTorch : $($racine.Length) caracteres, 100 au plus sans les chemins longs de Windows. Deplacez-le, par exemple dans C:\Mendel, ou activez les chemins longs : https://pip.pypa.io/warnings/enable-long-paths"
    }
    if (-not (Test-Path $python)) {
        $base = Trouver-Python
        if (-not $base) {
            Installer-Python
            $base = Trouver-Python
        }
        if (-not $base) {
            Echec 'Python 3.11 a 3.15 introuvable. Installez-le depuis https://www.python.org (ou : winget install Python.Python.3.13), puis relancez.'
        }
        Etape "Creation du venv .venv ($($base -join ' '))"
        $options = @($base | Select-Object -Skip 1)
        & $base[0] @options -m venv $venv
        Verifier 'Creation du venv'
    }
    if ($installee -and $installee -ne $voulue) {
        Etape "Remplacement de PyTorch $installee par la variante $voulue"
        & $python -m pip uninstall --disable-pip-version-check -y torch
        Verifier 'Desinstallation de PyTorch'
    }
    Etape "Installation de PyTorch, variante $voulue (jusqu'a 2,5 Go la premiere fois)"
    & $python -m pip install --disable-pip-version-check -r requirements.txt --index-url $roues[$voulue]
    Verifier 'Installation de requirements.txt'
    Copy-Item $requis $copieRequis
}

# --- 2. Application web ---
$page = Join-Path $web 'dist\index.html'
$marque = Join-Path $web 'dist\.sources'
$empreinte = Empreinte-Web
$construite = if (Test-Path $marque) { (Get-Content $marque -Raw).Trim() } else { '' }
if (-not (Test-Path $page) -or $construite -ne $empreinte) {
    if (-not (Construire-Web $empreinte)) {
        if (-not (Test-Path $page)) {
            Echec "L'application web n'est pas construite, et sa construction demande Node.js 20.19 ou plus : https://nodejs.org (ou : winget install OpenJS.NodeJS.LTS)."
        }
        Avertir "L'application web n'a pas ete reconstruite apres la modification de ses sources : la version deja construite s'ouvre."
    }
}

# --- 3. Marche par defaut ---
if (-not (Test-Path $marche)) {
    Etape 'Telechargement du marche par defaut : BTCUSDT horaire, janvier 2018 a decembre 2025 (data.binance.vision)'
    & $python -m scripts.fetch_binance BTCUSDT 1h 2018-01 2025-12
    Verifier 'Telechargement du marche (relancez pour reprendre : les mois deja recus sont gardes)'
}

# --- 4. Interface ---
Etape 'Interface'
& $python -m interface.serveur --ouvrir @args
exit $LASTEXITCODE
