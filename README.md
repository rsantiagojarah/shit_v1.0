# SHIT - Sistema de Historial Integral de Transformaciones

Un sistema simple de control de versiones diseñado específicamente para archivos binarios.

## Características
- Almacenamiento de múltiples versiones de archivos binarios
- Seguimiento de cambios entre versiones
- Recuperación de versiones anteriores
- Gestión de metadatos (autor, fecha, comentarios)
- Soporte para ramas (branches) similar a Git
- Integración con Google Drive para trabajo colaborativo

## Requisitos
- Python 3.8+
- Paquetes requeridos en requirements.txt
- Para funcionalidad de Google Drive:
  - Cuenta de Google
  - Archivo de credenciales de Google Drive API (`credentials.json`)

## Uso Básico
```
python shit.py init [directorio]     # Inicializa un repositorio
python shit.py add [archivo]         # Añade un archivo al control de versiones
python shit.py commit [archivo] -m "mensaje"  # Guarda una nueva versión
python shit.py log [archivo]         # Muestra el historial de versiones
python shit.py checkout [archivo] [versión]   # Recupera una versión específica
```

## Gestión de Ramas
```
python shit.py branch create [nombre]  # Crea una nueva rama
python shit.py branch list             # Lista todas las ramas disponibles
python shit.py branch switch [nombre]  # Cambia a otra rama
python shit.py branch merge [origen] [destino]  # Fusiona una rama con otra
```

## Trabajo Colaborativo con Google Drive
```
python shit.py remote init [nombre]  # Inicializa un repositorio remoto en Google Drive
python shit.py remote clone [id]     # Clona un repositorio desde Google Drive
python shit.py remote push           # Envía cambios al repositorio remoto
python shit.py remote pull           # Obtiene cambios desde el repositorio remoto
python shit.py remote share [email]  # Comparte el repositorio con otro usuario
```

## Configuración de Google Drive
1. Crear un proyecto en [Google Cloud Console](https://console.cloud.google.com/)
2. Habilitar la API de Google Drive
3. Crear credenciales de OAuth
4. Descargar el archivo `credentials.json` y colocarlo en el directorio del repositorio

## Ejemplo de Flujo de Trabajo Colaborativo
```
# Usuario 1
python shit.py init .
python shit.py add datos.bin
python shit.py commit datos.bin -m "Versión inicial"
python shit.py remote init "Proyecto Compartido"
# Compartir el ID del repositorio con el Usuario 2

# Usuario 2
python shit.py remote clone [ID_REPOSITORIO]
python shit.py branch create feature1
python shit.py branch switch feature1
# Modificar archivos
python shit.py commit datos.bin -m "Cambios en feature1"
python shit.py remote push -b feature1

# Usuario 1
python shit.py remote pull
python shit.py branch list
python shit.py branch switch feature1
python shit.py log datos.bin
``` 