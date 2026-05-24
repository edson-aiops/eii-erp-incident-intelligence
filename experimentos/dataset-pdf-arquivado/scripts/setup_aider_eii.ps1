
# ============================================================
# SCRIPT POWERSHELL — CONFIGURAR AIDER + OLLAMA PARA EII
# Copie e cole no PowerShell como Administrador
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  EII — Setup Aider + Ollama (GRATIS)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- PASSO 1: Verificar Python ---
Write-Host "[1/6] Verificando Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Python encontrado: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Python não encontrado. Instale Python 3.13+ em https://python.org" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "  ❌ Python não encontrado. Instale Python 3.13+ em https://python.org" -ForegroundColor Red
    exit 1
}

# --- PASSO 2: Verificar/Instalar Aider ---
Write-Host ""
Write-Host "[2/6] Verificando Aider..." -ForegroundColor Yellow
try {
    $aiderVersion = aider --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Aider já instalado: $aiderVersion" -ForegroundColor Green
    } else {
        throw "Aider não encontrado"
    }
} catch {
    Write-Host "  📦 Instalando Aider..." -ForegroundColor Cyan
    pip install aider-chat
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Aider instalado com sucesso!" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Falha ao instalar Aider. Tente: pip install --upgrade aider-chat" -ForegroundColor Red
        exit 1
    }
}

# --- PASSO 3: Verificar Ollama ---
Write-Host ""
Write-Host "[3/6] Verificando Ollama..." -ForegroundColor Yellow
try {
    $ollamaVersion = ollama --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Ollama encontrado: $ollamaVersion" -ForegroundColor Green
    } else {
        throw "Ollama não encontrado"
    }
} catch {
    Write-Host "  ❌ Ollama não encontrado." -ForegroundColor Red
    Write-Host "  📥 Baixe em: https://ollama.com/download/windows" -ForegroundColor Cyan
    Write-Host "  ⚠️  Instale Ollama e execute este script novamente." -ForegroundColor Yellow
    exit 1
}

# --- PASSO 4: Verificar modelos Ollama ---
Write-Host ""
Write-Host "[4/6] Verificando modelos Ollama disponíveis..." -ForegroundColor Yellow
$models = ollama list 2>$null
if ($models -match "llama3.2") {
    Write-Host "  ✅ llama3.2 encontrado" -ForegroundColor Green
} else {
    Write-Host "  📥 Baixando llama3.2 (pode levar alguns minutos)..." -ForegroundColor Cyan
    ollama pull llama3.2
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ llama3.2 baixado com sucesso!" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Falha ao baixar llama3.2. Tentando gemma2..." -ForegroundColor Yellow
        ollama pull gemma2:2b
    }
}

# --- PASSO 5: Verificar GROQ_API_KEY ---
Write-Host ""
Write-Host "[5/6] Verificando GROQ_API_KEY..." -ForegroundColor Yellow
try {
    $groqKey = python -c "import keyring; print(keyring.get_password('EII_Project', 'GROQ_API_KEY'))" 2>$null
    if ($groqKey -and $groqKey -ne "None") {
        Write-Host "  ✅ GROQ_API_KEY configurada no keyring" -ForegroundColor Green
        $hasGroq = $true
    } else {
        Write-Host "  ⚠️  GROQ_API_KEY não encontrada no keyring" -ForegroundColor Yellow
        $hasGroq = $false
    }
} catch {
    Write-Host "  ⚠️  Não foi possível verificar GROQ_API_KEY" -ForegroundColor Yellow
    $hasGroq = $false
}

# --- PASSO 6: Criar alias e instruções ---
Write-Host ""
Write-Host "[6/6] Configurando ambiente..." -ForegroundColor Yellow

# Criar arquivo de configuração Aider
$aiderConfig = @"
# Aider config para EII
# Coloque este arquivo em ~/.aider.conf.yml (ou %USERPROFILE%\.aider.conf.yml no Windows)

# Modelo padrão: Ollama local (GRATIS)
model: ollama/llama3.2

# Alternativa: Groq (você já tem API key)
# model: groq/llama-3.3-70b-versatile

# Git settings
git: true
auto-commits: true
commit-prompt: "feat: {message}"

# Contexto
cache-prompts: true
map-refresh: auto

# Output
stream: true
pretty: true
"@

$aiderConfigPath = "$env:USERPROFILE\.aider.conf.yml"
$aiderConfig | Out-File -FilePath $aiderConfigPath -Encoding UTF8
Write-Host "  ✅ Configuração Aider salva em: $aiderConfigPath" -ForegroundColor Green

# --- RESUMO ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ SETUP CONCLUÍDO!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 COMO USAR O AIDER NO EII:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Entre no diretório do projeto:" -ForegroundColor White
Write-Host "   cd C:\Projetos\eii-erp-incident-intelligence" -ForegroundColor Yellow
Write-Host ""
Write-Host "2. Inicie o Aider com Ollama (GRATIS):" -ForegroundColor White
Write-Host "   aider --model ollama/llama3.2" -ForegroundColor Yellow
Write-Host ""
if ($hasGroq) {
    Write-Host "3. Ou use Groq (melhor qualidade, custo baixo):" -ForegroundColor White
    Write-Host "   aider --model groq/llama-3.3-70b-versatile" -ForegroundColor Yellow
} else {
    Write-Host "3. (Opcional) Configure GROQ_API_KEY para usar modelos Groq:" -ForegroundColor White
    Write-Host "   python -c \"import keyring; keyring.set_password('EII_Project', 'GROQ_API_KEY', 'sua-chave')\"" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "4. Dentro do Aider, execute tarefas:" -ForegroundColor White
Write-Host "   > Crie 11 arquivos de teste para o projeto EII" -ForegroundColor Yellow
Write-Host "   > Corrija DeprecationWarnings em xml_parser.py" -ForegroundColor Yellow
Write-Host "   > Implemente 100+ testes com unittest.mock" -ForegroundColor Yellow
Write-Host "   > Configure credenciais: QDRANT_API_KEY, LANGCHAIN_API_KEY, QWEN_API_KEY" -ForegroundColor Yellow
Write-Host ""
Write-Host "5. O Aider faz commits automaticamente!" -ForegroundColor White
Write-Host "   Você só precisa aprovar e fazer push:" -ForegroundColor Yellow
Write-Host "   git push origin feature/aider-tests-and-secrets" -ForegroundColor Yellow
Write-Host ""
Write-Host "📚 DOCUMENTAÇÃO:" -ForegroundColor Cyan
Write-Host "   https://aider.chat/docs/" -ForegroundColor Yellow
Write-Host ""
Write-Host "💡 DICA: Use /add para adicionar arquivos ao contexto:" -ForegroundColor White
Write-Host "   > /add xml_parser.py tests/" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
