#!/bin/bash
# ============================================================
# Itosturre LegalTech — Setup del Agente Jurídico con IA
# OpenNotebook RAG + Scraper SJF + Metodología VVCA
# ============================================================
# Uso: bash setup.sh
# Requisitos: Python 3.10+, Node.js 18+, Git

set -e

VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
ROJO='\033[0;31m'
CYAN='\033[0;36m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║         ITOSTURRE LEGALTECH — SETUP AGENTE IA        ║${RESET}"
echo -e "${CYAN}║         OpenNotebook · Scraper SJF · VVCA             ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""

# ── 0. Verificar prerrequisitos ───────────────────────────────────────────

echo -e "${AMARILLO}[1/7] Verificando prerrequisitos...${RESET}"

if ! command -v python3 &>/dev/null; then
    echo -e "${ROJO}❌ Python 3 no encontrado. Instala Python 3.10 o superior.${RESET}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ✅ Python $PYTHON_VERSION"

if ! command -v node &>/dev/null; then
    echo -e "${ROJO}❌ Node.js no encontrado. Instala Node.js 18 o superior.${RESET}"
    exit 1
fi
echo -e "  ✅ Node.js $(node --version)"

if ! command -v git &>/dev/null; then
    echo -e "${ROJO}❌ Git no encontrado.${RESET}"
    exit 1
fi
echo -e "  ✅ Git $(git --version | awk '{print $3}')"

# ── 1. Datos del cliente ──────────────────────────────────────────────────

echo ""
echo -e "${AMARILLO}[2/7] Configuración del despacho...${RESET}"
echo ""

read -p "  Nombre del despacho / firma: " NOMBRE_DESPACHO
read -p "  Nombre del licenciado titular: " NOMBRE_LIC
read -p "  Estado de la República (ej: Jalisco): " ESTADO
read -p "  Correo electrónico: " EMAIL_DESPACHO
read -p "  API Key de Anthropic (sk-ant-...): " ANTHROPIC_KEY
echo ""

# ── 2. Entorno Python ─────────────────────────────────────────────────────

echo -e "${AMARILLO}[3/7] Creando entorno virtual Python...${RESET}"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements_opennotebook.txt -q
pip install playwright -q
playwright install chromium --with-deps -q

echo -e "  ✅ Entorno Python configurado"

# ── 3. Scraper SJF ───────────────────────────────────────────────────────

echo ""
echo -e "${AMARILLO}[4/7] Instalando Scraper SJF...${RESET}"

if [ -d "../itosturre-scraper" ]; then
    cd ../itosturre-scraper
    npm install -q
    cd ../itosturre-auditor
    echo -e "  ✅ Scraper SJF listo"
else
    echo -e "  ⚠️  Directorio itosturre-scraper no encontrado."
    echo -e "     Clona el repo: git clone git@github.com:Sickboooooy/itosturre-scraper.git"
fi

# ── 4. Corpus de PDFs ────────────────────────────────────────────────────

echo ""
echo -e "${AMARILLO}[5/7] Indexando corpus jurídico...${RESET}"
echo ""
echo -e "  Coloca los PDFs de leyes y jurisprudencia en una carpeta."
read -p "  Ruta a la carpeta de PDFs (Enter para omitir por ahora): " RUTA_PDFS

if [ -n "$RUTA_PDFS" ] && [ -d "$RUTA_PDFS" ]; then
    echo -e "  ⏳ Indexando PDFs en ChromaDB (puede tardar varios minutos)..."
    python3 OpenNotebook.py ingest --directory "$RUTA_PDFS"
    echo -e "  ✅ Corpus indexado"
else
    echo -e "  ⚠️  Corpus omitido. Para indexar después:"
    echo -e "     source venv/bin/activate"
    echo -e "     python3 OpenNotebook.py ingest --directory /ruta/a/tus/pdfs/"
fi

# ── 5. Variables de entorno ───────────────────────────────────────────────

echo ""
echo -e "${AMARILLO}[6/7] Guardando configuración...${RESET}"

cat > .env << EOF
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
DESPACHO=$NOMBRE_DESPACHO
TITULAR=$NOMBRE_LIC
ESTADO=$ESTADO
EMAIL=$EMAIL_DESPACHO
EOF

chmod 600 .env
echo -e "  ✅ .env creado (permisos restringidos)"

# ── 6. CLAUDE.md del cliente ─────────────────────────────────────────────

echo ""
echo -e "${AMARILLO}[7/7] Generando CLAUDE.md personalizado...${RESET}"

cat > CLAUDE.md << EOF
# CLAUDE.md — Agente Jurídico IA
# $NOMBRE_DESPACHO · $NOMBRE_LIC · $ESTADO

Este archivo configura tu asistente jurídico con IA desarrollado por **Itosturre LegalTech**.

---

## Identidad

Eres el agente de investigación legal de **$NOMBRE_DESPACHO**, asistiendo a **$NOMBRE_LIC**.
Operas con herramientas verificadas por la metodología VVCA de Itosturre LegalTech.

Filosofía: *"La IA facilita estrategias, el abogado certifica soluciones."*

---

## Metodología VVCA (obligatoria en toda investigación jurídica)

- 🟢 **Verificación** — ¿La fuente es oficial? (SJF, DOF, legislación vigente)
- 🟡 **Validación** — ¿El criterio es aplicable al caso concreto?
- 🔵 **Contextualización** — ¿Qué época, sala, materia y jerarquía tiene?
- 🔴 **Auditabilidad** — ¿Puedes citar número de registro, fecha y tribunal?

**Semáforo de confianza:**
- 🟢 Verde >85 — Citar con seguridad
- 🟡 Amarillo 60–84 — Citar con reserva
- 🔴 Rojo <60 — No citar, investigar más

---

## Herramientas disponibles

### OpenNotebook — Auditoría RAG Anti-Alucinaciones
\`\`\`bash
# Auditar un texto o borrador:
source venv/bin/activate
python3 OpenNotebook.py audit --text "artículo o estrategia a verificar"
python3 OpenNotebook.py audit --file /ruta/borrador.md

# Indexar nuevos PDFs al corpus:
python3 OpenNotebook.py ingest --directory /ruta/a/pdfs/
\`\`\`

### Scraper SJF — Jurisprudencia y Tesis
\`\`\`bash
cd ../itosturre-scraper
npx ts-node --esm scraper_final.ts   # búsqueda individual
npx ts-node --esm scraper_batch.ts   # búsqueda múltiple
\`\`\`
Modifica el término de búsqueda en \`scraper_final.ts\` en la línea \`page.fill()\`.
Resultados en \`/jurisprudencia/[tema].json\`.

---

## Protocolo de auditoría (obligatorio en escritos legales)

Antes de entregar cualquier demanda, concepto de impugnación o cita jurisprudencial:

1. Corre: \`python3 OpenNotebook.py audit --file /ruta/borrador.md\`
2. Revisa el campo \`"alerts"\` — corrige antes de entregar
3. Aplica semáforo VVCA a cada tesis del Scraper SJF
4. Si OpenNotebook falla: aplica VVCA manual y marca con 🟡 lo no verificado

---

## Fuentes primarias autorizadas

1. Semanario Judicial de la Federación — sjf2.scjn.gob.mx
2. Diario Oficial de la Federación — dof.gob.mx
3. Cámara de Diputados — diputados.gob.mx
4. SCJN — scjn.gob.mx

---

## Soporte técnico

Este agente es desarrollado y mantenido por **Itosturre LegalTech**.
Actualizaciones del corpus y soporte técnico vigentes durante la suscripción activa.

Contacto: $EMAIL_DESPACHO · itosturre.com
EOF

echo -e "  ✅ CLAUDE.md generado para $NOMBRE_DESPACHO"

# ── Resumen final ─────────────────────────────────────────────────────────

echo ""
echo -e "${VERDE}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${VERDE}║              ✅ SETUP COMPLETADO                     ║${RESET}"
echo -e "${VERDE}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  Despacho:  $NOMBRE_DESPACHO"
echo -e "  Titular:   $NOMBRE_LIC"
echo -e "  Estado:    $ESTADO"
echo ""
echo -e "  Para iniciar Claude Code con tu agente:"
echo -e "  ${CYAN}claude${RESET}"
echo ""
echo -e "  Para auditar un borrador:"
echo -e "  ${CYAN}source venv/bin/activate && python3 OpenNotebook.py audit --file borrador.md${RESET}"
echo ""
echo -e "  Soporte: itosturre.com"
echo ""
