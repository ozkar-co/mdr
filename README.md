# mdr

Lector ligero de Markdown en terminal, inspirado en [Glow](https://github.com/charmbracelet/glow).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Uso

```bash
./run.sh              # selector de archivos .md
./run.sh ejemplo.md   # abrir directamente
./run.sh help
```

## Controles

| Tecla | Acción |
|-------|--------|
| ↑ / ↓ | Mover selección / desplazarse |
| Enter | Abrir archivo o enlace |
| RePág / AvPág | Avanzar una página |
| ← / → | Cambiar entre enlaces |
| Backspace | Volver (al selector si no hay historial) |
| `/` | Buscar texto |
| `n` / `N` | Siguiente / anterior coincidencia |
| `h` | Ayuda |
| q / Esc | Salir |

Soporta **tablas**, **tachado** (`~~texto~~`), bloques de código con sintaxis, enlaces locales y externos.
