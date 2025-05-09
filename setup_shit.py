#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de instalación para SHIT - Sistema de Historial Integral de Transformaciones
Este script configura el entorno necesario para utilizar SHIT desde cualquier ubicación.
"""

import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path

def crear_directorio_oculto():
    """Crea el directorio oculto donde se almacenará el sistema"""
    if platform.system() == "Windows":
        home_dir = os.path.join(os.environ.get("USERPROFILE"), ".shit")
    else:
        home_dir = os.path.join(os.environ.get("HOME"), ".shit")
    
    if not os.path.exists(home_dir):
        os.makedirs(home_dir, exist_ok=True)
        print(f"Directorio oculto creado en: {home_dir}")
        
        # Ocultar el directorio en Windows
        if platform.system() == "Windows":
            try:
                # Método 1: Usar attrib +h
                subprocess.run(['attrib', '+h', home_dir], shell=True, check=False)
            except Exception:
                try:
                    # Método 2: Usar cmd /c attrib +h
                    cmd = f'cmd /c attrib +h "{home_dir}"'
                    subprocess.run(cmd, shell=True, check=False)
                except Exception as e:
                    print(f"Advertencia: No se pudo ocultar el directorio {home_dir}: {str(e)}")
                    print("El directorio está visible. Para ocultarlo manualmente, use:")
                    print(f'attrib +h "{home_dir}"')
    
    # Crear subdirectorios necesarios
    repos_dir = os.path.join(home_dir, "repos")
    if not os.path.exists(repos_dir):
        os.makedirs(repos_dir, exist_ok=True)
    
    return home_dir

def copiar_archivos_necesarios(home_dir):
    """Copia los archivos necesarios al directorio oculto, sobrescribiendo siempre los existentes"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_copy = ["shit.py", "drive_sync.py", "requirements.txt"]
    
    for file in files_to_copy:
        src_file = os.path.join(current_dir, file)
        dst_file = os.path.join(home_dir, file)
        
        if os.path.exists(src_file):
            shutil.copy2(src_file, dst_file)  # Sobrescribe siempre
            print(f"Copiado (actualizado): {file} a {home_dir}")
        else:
            print(f"Advertencia: No se encontró el archivo {file}")
    
    return True

def crear_enlace_simbolico(home_dir):
    """Crea un enlace simbólico en un directorio del PATH"""
    shit_script = os.path.join(home_dir, "shit.py")
    
    if platform.system() == "Windows":
        # Crear un archivo batch en un directorio del PATH
        script_dir = os.path.join(os.environ.get("USERPROFILE"), "AppData", "Local", "Microsoft", "WindowsApps")
        bat_file = os.path.join(script_dir, "shit.bat")
        
        with open(bat_file, "w") as f:
            f.write(f'@echo off\n"{sys.executable}" "{shit_script}" %*')
        
        print(f"Archivo batch creado en: {bat_file}")
    else:
        # En sistemas Unix, crear un enlace simbólico en /usr/local/bin
        link_path = "/usr/local/bin/shit"
        try:
            if os.path.exists(link_path):
                os.remove(link_path)
            os.symlink(shit_script, link_path)
            os.chmod(shit_script, 0o755)  # Hacer ejecutable
            print(f"Enlace simbólico creado en: {link_path}")
        except PermissionError:
            print("Error: Se necesitan permisos de administrador para crear el enlace simbólico.")
            print(f"Ejecute: sudo ln -s {shit_script} {link_path}")
    
    return True

def instalar_dependencias(home_dir):
    """Instala las dependencias necesarias"""
    requirements_file = os.path.join(home_dir, "requirements.txt")
    
    if os.path.exists(requirements_file):
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", requirements_file], check=True)
            print("Dependencias instaladas correctamente.")
        except subprocess.CalledProcessError:
            print("Error al instalar las dependencias.")
            return False
    else:
        print("Advertencia: No se encontró el archivo requirements.txt")
    
    return True

def main():
    """Función principal de instalación"""
    print("=== Instalando SHIT - Sistema de Historial Integral de Transformaciones ===")
    
    # Crear directorio oculto
    home_dir = crear_directorio_oculto()
    
    # Copiar archivos necesarios
    copiar_archivos_necesarios(home_dir)
    
    # Instalar dependencias
    instalar_dependencias(home_dir)
    
    # Crear enlace simbólico
    crear_enlace_simbolico(home_dir)
    
    print("\n=== Instalación completada ===")
    print("Ahora puede utilizar el sistema desde cualquier ubicación con los siguientes comandos:")
    print("  shit --help                        - Ver ayuda y todos los comandos disponibles")
    print("  shit init                          - Inicializar un repositorio oculto para el directorio actual")
    print("  shit add archivo                   - Añadir un archivo al control de versiones")
    print("  shit add -A                        - Añadir todos los archivos modificados")
    print("  shit commit -m \"mensaje\"           - Guardar versión de todos los archivos en staging")
    print("  shit commit archivo -m \"mensaje\"   - Guardar versión de un archivo específico")
    print("  shit log archivo                   - Ver historial de versiones de un archivo")
    print("  shit log                           - Ver historial de todos los archivos")
    print("  shit status                        - Muestra archivos modificados, añadidos y sin seguimiento")
    print("  shit checkout archivo versión      - Recuperar una versión")
    print("  shit branch create nombre          - Crear una nueva rama")
    print("  shit branch list                   - Listar ramas disponibles")
    print("  shit branch switch nombre          - Cambiar de rama")
    print("  shit branch merge origen [destino] - Fusionar ramas")
    print("  shit remote init nombre            - Inicializar repositorio remoto en Google Drive")
    print("  shit remote clone id               - Clonar desde Google Drive")
    print("  shit remote push                   - Subir cambios al remoto")
    print("  shit remote pull                   - Obtener cambios del remoto")
    print("  shit remote share email            - Compartir el repositorio remoto")
    print("  shit reset --soft <hash>           - Retrocede HEAD y deja cambios en staging")
    print("  shit reflog                        - Ver historial de movimientos de HEAD")
    print("\nPara más información, consulte la documentación en README.md")

if __name__ == "__main__":
    main() 