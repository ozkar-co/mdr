"""Texto de ayuda compartido (CLI e in-app)."""

HELP_LINES = [
    "mdr — lector de Markdown en terminal",
    "",
    "Uso:  ./run.sh                         lista de archivos .md",
    "      ./run.sh <directorio>            lista de archivos .md en ese directorio",
    "      ./run.sh <archivo.md>            abrir directamente",
    "      ./run.sh help",
    "",
    "Selector de archivos",
    "  ↑ / ↓         Elegir archivo",
    "  Enter         Abrir",
    "  q / Esc       Salir",
    "",
    "Navegación",
    "  ↑ / ↓         Desplazarse línea a línea",
    "  RePág / AvPág Avanzar una página",
    "  Home / End    Inicio / final del documento",
    "",
    "Enlaces",
    "  ← / →         Cambiar enlace activo",
    "  Enter         Abrir enlace",
    "  Backspace     Volver (al selector si no hay historial)",
    "",
    "Búsqueda",
    "  /             Buscar texto",
    "  n / N         Siguiente / anterior coincidencia",
    "",
    "General",
    "  h             Mostrar esta ayuda",
    "  q / Esc       Salir",
    "",
    "Pulsa cualquier tecla para cerrar",
]


def help_for_terminal() -> str:
    lines = [ln for ln in HELP_LINES if ln != "Pulsa cualquier tecla para cerrar"]
    return "\n".join(lines)
