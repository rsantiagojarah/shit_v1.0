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
    
    # Crear subdirectorios necesarios
    repos_dir = os.path.join(home_dir, "repos")
    if not os.path.exists(repos_dir):
        os.makedirs(repos_dir, exist_ok=True)
    
    return home_dir

def copiar_archivos_necesarios(home_dir):
    """Copia los archivos necesarios al directorio oculto"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_copy = ["shit.py", "drive_sync.py", "requirements.txt"]
    
    for file in files_to_copy:
        src_file = os.path.join(current_dir, file)
        dst_file = os.path.join(home_dir, file)
        
        if os.path.exists(src_file):
            shutil.copy2(src_file, dst_file)
            print(f"Copiado: {file} a {home_dir}")
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
    print("  shit init         - Inicializar un repositorio oculto para el directorio actual")
    print("  shit add archivo  - Añadir un archivo al control de versiones")
    print("  shit commit archivo -m \"mensaje\"  - Guardar una versión")
    print("  shit log archivo  - Ver historial de versiones")
    print("  shit checkout archivo versión  - Recuperar una versión")
    print("\nPara más información, consulte la documentación en README.md")

if __name__ == "__main__":
    main() 