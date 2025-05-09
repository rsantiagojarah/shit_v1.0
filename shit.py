#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SHIT - Sistema de Historial Integral de Transformaciones
"""

import os # para manejar archivos y directorios
import sys # para manejar argumentos de la linea de comandos
import hashlib # para calcular hashes de datos
import zlib # para comprimir y descomprimir datos
import json # para manejar datos en formato JSON
import datetime # para manejar fechas y horas
import shutil # para copiar y mover archivos
import time # para manejar tiempos
import subprocess # para ejecutar comandos del sistema
import argparse # para manejar argumentos de la linea de comandos
import platform # para obtener información del sistema operativo
import getpass # para obtener el nombre del usuario 
import click # para manejar comandos de la linea de comandos
from pathlib import Path # para manejar rutas de archivos y directorios

# Importar el módulo para manejar atributos de archivos en Windows
if platform.system() == "Windows":
    import ctypes

# Importar el módulo de sincronización con Google Drive
try:
    from drive_sync import DriveSync
    DRIVE_SUPPORT = True
except ImportError:
    DRIVE_SUPPORT = False

# Ubicación del directorio oculto donde se almacenará el repositorio
# Ahora usamos un directorio oculto local, similar a Git
LOCAL_MODE = True  # Directorio oculto local (como Git)

if platform.system() == "Windows":
    HOME_DIR = os.path.join(os.environ.get("USERPROFILE"), ".shit")
else:
    HOME_DIR = os.path.join(os.environ.get("HOME"), ".shit")

# Constante para atributos de archivo en Windows
FILE_ATTRIBUTE_HIDDEN = 0x02

def hide_directory(path):
    """Oculta un directorio en Windows usando múltiples métodos."""
    if platform.system() == "Windows":
        # Convertir path a string para asegurar compatibilidad
        path_str = str(path)
        
        # Método 1: Usar la API de Windows (SetFileAttributes)
        try:
            ret = ctypes.windll.kernel32.SetFileAttributesW(path_str, FILE_ATTRIBUTE_HIDDEN)
            if ret != 0:
                return True  # Éxito con el primer método
        except Exception as e:
            print(f"Info: No se pudo ocultar con SetFileAttributes: {str(e)}")
        
        # Método 2: Usar el comando attrib del sistema
        try:
            # Usar shell=True para mayor compatibilidad
            subprocess.run(['attrib', '+h', path_str], shell=True, check=False)
            return True
        except Exception as e:
            print(f"Info: No se pudo ocultar con attrib: {str(e)}")
            
        # Método 3: Usar comando attrib con cmd /c para mayor compatibilidad
        try:
            cmd = f'cmd /c attrib +h "{path_str}"'
            subprocess.run(cmd, shell=True, check=False)
            return True
        except Exception as e:
            print(f"Advertencia: No se pudo ocultar el directorio {path}: {str(e)}")
            print("IMPORTANTE: La carpeta .shit está visible. Para ocultarla manualmente, use:")
            print(f'attrib +h "{path_str}"')
            return False

class SHIT:
    """Clase principal para el control de versiones de archivos binarios."""

    def __init__(self, repo_path='.'):
        """Inicializa el sistema de control de versiones."""
        self.repo_path = Path(repo_path)
        self.vcs_dir = self.repo_path / '.shit'
        self.objects_dir = self.vcs_dir / 'objects'
        self.refs_dir = self.vcs_dir / 'refs'
        self.branches_dir = self.refs_dir / 'branches'
        self.config_file = self.vcs_dir / 'config.json'
        self.index_file = self.vcs_dir / 'index.json'
        self.head_file = self.vcs_dir / 'HEAD'
        self.index = {}
        self.config = {}
        self.current_branch = "master"

    def init(self):
        """Inicializa un nuevo repositorio."""
        if self.vcs_dir.exists():
            print(f"El repositorio ya existe en: {self.vcs_dir}")
            return False

        # Crear estructura de directorios
        self.vcs_dir.mkdir(exist_ok=True)
        self.objects_dir.mkdir(exist_ok=True)
        self.refs_dir.mkdir(exist_ok=True)
        self.branches_dir.mkdir(exist_ok=True)

        # Crear archivos de configuración iniciales
        self.config = {
            'version': '1.0',
            'created_at': datetime.datetime.now().isoformat(),
        }
        
        self._save_config()
        self._save_index()
        
        # Inicializar rama master (por defecto)
        self._set_head("master")
        
        # Inicializar reflog
        reflog_file = self.vcs_dir / 'reflog'
        with open(reflog_file, 'w') as f:
            f.write("")
        
        # Registrar la inicialización en el reflog
        self._add_to_reflog("init", "master")
        
        # Ocultar el directorio en Windows
        hide_directory(self.vcs_dir)
        
        print(f"Repositorio inicializado en: {self.repo_path}")
        return True

    def add(self, file_path):
        """Añade un archivo al control de versiones o marca archivos modificados para commit."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            print(f"Error: El archivo {file_path} no existe.")
            return False
            
        if not file_path.is_file():
            print(f"Error: {file_path} no es un archivo.")
            return False

        # Cargar el índice actual
        self._load_index()
        
        try:
            # Intentar calcular ruta relativa al repositorio
            rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
            str_path = str(rel_path).replace(os.path.sep, '/')  # Normalizar separadores
        except ValueError:
            # Si no es posible calcular la ruta relativa (porque el archivo está fuera del repo),
            # usar el nombre del archivo como identificador
            str_path = file_path.name
        
        # Verificar si el archivo ya está en el índice
        if str_path in self.index:
            # El archivo ya está en el índice, verificar si ha sido modificado
            current_branch = self._get_current_branch()
            info = self.index[str_path]
            versions = info.get('versions', [])
            branch_versions = [v for v in versions if v.get('branch', 'master') == current_branch]
            
            if branch_versions:
                # Tiene versiones previas en esta rama, verificar si se modificó
                latest_version = branch_versions[-1]
                hash_original = latest_version['hash']
                
                # Calcular el hash actual
                try:
                    with open(file_path, 'rb') as f:
                        contenido = f.read()
                    hash_actual = hashlib.sha256(contenido).hexdigest()
                    
                    if hash_actual != hash_original:
                        # El archivo ha sido modificado
                        print(f"Archivo modificado {str_path} marcado para commit.")
                        return True
                    else:
                        # El archivo no ha sido modificado
                        print(f"El archivo {str_path} no ha sido modificado desde el último commit.")
                        return True
                except Exception as e:
                    print(f"Error al leer el archivo {str_path}: {str(e)}")
                    return False
            else:
                # No tiene versiones en esta rama, está listo para commit
                print(f"Archivo {str_path} ya está añadido y listo para commit.")
                return True
        else:
            # Añadir archivo nuevo al índice
            self.index[str_path] = {
                'added_at': datetime.datetime.now().isoformat(),
                'versions': []
            }
            
            self._save_index()
            print(f"Archivo {str_path} añadido al control de versiones.")
            return True

    def add_all(self):
        """Añade todos los archivos modificados y nuevos al control de versiones."""
        # Cargar el índice actual
        self._load_index()
        
        # Obtener la rama actual
        current_branch = self._get_current_branch()
        
        # Variables para tracking
        added_files = []  # Archivos nuevos añadidos
        updated_files = []  # Archivos modificados re-añadidos
        
        # 1. Procesar archivos ya en el índice (modificados)
        for file_path, info in list(self.index.items()):
            # Convertir / a \ para Windows si es necesario
            file_sys_path = file_path.replace('/', os.path.sep)
            abs_path = self.repo_path / file_sys_path
            
            # Verificar si el archivo existe
            if not abs_path.exists():
                continue
                
            # Verificar si tiene versiones en la rama actual
            versions = info.get('versions', [])
            branch_versions = [v for v in versions if v.get('branch', 'master') == current_branch]
            
            if not branch_versions:
                continue  # No tiene versiones en esta rama, no hay "modificación"
                
            # Obtener el hash de la última versión
            latest_version = branch_versions[-1]
            hash_original = latest_version['hash']
            
            # Calcular el hash actual
            try:
                with open(abs_path, 'rb') as f:
                    contenido = f.read()
                hash_actual = hashlib.sha256(contenido).hexdigest()
                
                # Si los hashes son diferentes, el archivo ha sido modificado
                if hash_actual != hash_original:
                    # "Re-añadir" archivo modificado (marcar como listo para commit)
                    # En nuestro sistema, esto no requiere una acción especial
                    # ya que los archivos ya están en el índice
                    updated_files.append(file_path)
            except Exception:
                pass
        
        # 2. Encontrar y añadir archivos sin seguimiento
        # Crear un conjunto con todas las rutas normalizadas en el índice
        rutas_en_indice = set()
        for str_path in self.index.keys():
            # Normalizar la ruta para comparaciones
            ruta_normalizada = str_path.replace('\\', '/')
            rutas_en_indice.add(ruta_normalizada)
        
        # Primero, obtener todos los archivos en disco
        archivos_en_disco = set()
        
        # Método 1: Usar os.walk para encontrar todos los archivos en todas las carpetas
        for root, _, files in os.walk(self.repo_path):
            # Ignorar el directorio .shit y otros directorios ocultos
            if '.shit' in root or os.path.basename(root).startswith('.'):
                continue
                
            for file in files:
                # Ignorar archivos ocultos
                if file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    # Convertir a ruta relativa
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    # Normalizar para comparación (siempre usar /)
                    rel_path_norm = rel_path.replace(os.path.sep, '/')
                    archivos_en_disco.add(rel_path_norm)
                except Exception as e:
                    print(f"Error al procesar archivo {file_path}: {str(e)}")
                    continue
        
        # Método 2: Verificar explícitamente los archivos en el directorio raíz
        for item in os.listdir(self.repo_path):
            item_path = os.path.join(self.repo_path, item)
            # Solo incluir archivos (no directorios) y que no estén ocultos
            if os.path.isfile(item_path) and not item.startswith('.'):
                rel_path = os.path.relpath(item_path, self.repo_path)
                rel_path_norm = rel_path.replace(os.path.sep, '/')
                archivos_en_disco.add(rel_path_norm)
        
        # Encontrar archivos sin seguimiento (en disco pero no en el índice)
        for archivo in archivos_en_disco:
            if archivo not in rutas_en_indice:
                # Añadir archivo nuevo al índice
                self.index[archivo] = {
                    'added_at': datetime.datetime.now().isoformat(),
                    'versions': []
                }
                added_files.append(archivo)
        
        if added_files or updated_files:
            self._save_index()
            
            if added_files:
                print("Archivos nuevos añadidos al control de versiones:")
                for file in sorted(added_files):
                    print(f"  {file}")
            
            if updated_files:
                print("Archivos modificados marcados para commit:")
                for file in sorted(updated_files):
                    print(f"  {file}")
        else:
            print("No hay archivos nuevos ni modificados para añadir.")
            
        return True

    def commit(self, file_path=None, message="", branch=None):
        """Guarda una nueva versión del archivo o de todos los archivos en staging."""
        # Obtener la rama actual si no se especificó una
        if branch is None:
            branch = self._get_current_branch()
            
        # Cargar el índice
        self._load_index()
        
        if file_path is None:
            # Modo commit de todos los archivos en staging (sin commit previo)
            if not message:
                print("Error: Debe proporcionar un mensaje para el commit con -m")
                return False
            
            # Contar cuántos archivos se procesaron
            archivos_commiteados = 0
            ultimo_hash = None  # Para actualizar la rama
            
            # Iterar sobre todos los archivos en el índice
            for str_path, info in list(self.index.items()):
                file_sys_path = str_path.replace('/', os.path.sep)
                file_abs_path = self.repo_path / file_sys_path
                
                # Verificar si el archivo existe
                if not file_abs_path.exists():
                    print(f"Advertencia: El archivo {str_path} no existe, se omitirá.")
                    continue
                
                # Verificar si el archivo tiene versiones para esta rama
                versiones = info.get('versions', [])
                branch_versions = [v for v in versiones if v.get('branch', 'master') == branch]
                
                # Calcular el hash actual
                try:
                    with open(file_abs_path, 'rb') as f:
                        contenido = f.read()
                    hash_actual = hashlib.sha256(contenido).hexdigest()
                except Exception as e:
                    print(f"Error al leer archivo {str_path}: {str(e)}")
                    continue
                
                # Si no tiene versiones o el hash ha cambiado, hacer commit
                if not branch_versions or branch_versions[-1]['hash'] != hash_actual:
                    # Crear un commit para este archivo
                    if self._commit_file(file_abs_path, str_path, message, branch, update_branch=False):
                        # Guardar el hash para actualizar la rama al final
                        ultimo_hash = hash_actual
                        archivos_commiteados += 1
            
            if archivos_commiteados > 0 and ultimo_hash:
                # Actualizar la rama para que apunte al último hash
                self._update_branch_ref(branch, ultimo_hash)
                # Añadir al reflog
                self._add_to_reflog(f"commit: {message} ({archivos_commiteados} archivos)", branch)
                
                print(f"Commit creado: {message} ({archivos_commiteados} archivos)")
                return True
            else:
                print("No hay archivos para commit. Use 'shit add' para añadir archivos.")
                return False
        else:
            # Modo commit de un archivo específico
            file_path = Path(file_path)
            
            if not file_path.exists():
                print(f"Error: El archivo {file_path} no existe.")
                return False
                
            try:
                # Intentar calcular ruta relativa al repositorio
                rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
                str_path = str(rel_path).replace(os.path.sep, '/')  # Normalizar separadores
            except ValueError:
                # Si no es posible calcular la ruta relativa, usar el nombre del archivo
                str_path = file_path.name
            
            # Verificar que el archivo está en el índice
            if str_path not in self.index:
                print(f"Error: El archivo {str_path} no está bajo control de versiones. Usa 'add' primero.")
                return False
                
            # Hacer commit del archivo específico - actualizar la rama en este caso
            return self._commit_file(file_path, str_path, message, branch, update_branch=True)
            
    def _commit_file(self, file_path, str_path, message, branch, update_branch=True):
        """Método interno para hacer commit de un archivo específico"""
        # Leer el contenido del archivo
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
        except Exception as e:
            print(f"Error al leer el archivo {str_path}: {str(e)}")
            return False
            
        # Calcular hash del contenido
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Verificar si esta versión ya existe
        versions = self.index[str_path]['versions']
        branch_versions = [v for v in versions if v.get('branch', 'master') == branch]
        
        if branch_versions and branch_versions[-1]['hash'] == content_hash:
            print(f"No hay cambios en el archivo {str_path} desde la última versión en la rama {branch}.")
            return False
            
        # Comprimir el contenido
        compressed = zlib.compress(content)
        
        # Guardar el objeto - usando os.path para mayor compatibilidad con Windows
        hash_prefix = content_hash[:2]
        hash_suffix = content_hash[2:]
        object_dir = os.path.join(self.objects_dir, hash_prefix)
        object_file = os.path.join(object_dir, hash_suffix)
        
        # Crear el directorio del objeto de forma manual con os.makedirs
        if not os.path.exists(object_dir):
            try:
                os.makedirs(object_dir, exist_ok=True)
            except Exception as e:
                print(f"Error al crear directorio {object_dir}: {str(e)}")
                return False
                
        # Escribir el objeto
        try:
            with open(object_file, 'wb') as f:
                f.write(compressed)
        except Exception as e:
            print(f"Error al escribir objeto {object_file}: {str(e)}")
            return False
            
        # Actualizar el índice
        version_info = {
            'hash': content_hash,
            'timestamp': datetime.datetime.now().isoformat(),
            'message': message,
            'version': len(branch_versions) + 1,
            'branch': branch
        }
        
        self.index[str_path]['versions'].append(version_info)
        self._save_index()
        
        # Actualizar la referencia de la rama si se solicita
        if update_branch:
            self._update_branch_ref(branch, content_hash)
            # Registrar el commit en el reflog
            self._add_to_reflog(f"commit {str_path}: {message}", branch)
        
        print(f"Nueva versión de {str_path} guardada (v{version_info['version']}) en rama {branch}.")
        return True

    def log(self, file_path=None, branch=None):
        """Muestra el historial de versiones de un archivo o de todos los archivos si no se especifica."""
        self._load_index()
        
        if file_path is None:
            # Mostrar historial de todos los archivos
            if not self.index:
                print("No hay archivos bajo control de versiones.")
                return True
            for str_path in self.index:
                print(f"\n{'='*70}\nHistorial de: {str_path}")
                self.log(str_path, branch)
            return True
        
        file_path = Path(file_path)
        try:
            rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
            str_path = str(rel_path)
        except Exception:
            str_path = str(file_path)
        
        # Verificar que el archivo está en el índice
        if str_path not in self.index:
            print(f"Error: El archivo {str_path} no está bajo control de versiones.")
            return False
        
        # Obtener la rama actual si no se especificó una
        if branch is None:
            branch = self._get_current_branch()
        
        # Filtrar versiones por rama
        all_versions = self.index[str_path]['versions']
        versions = [v for v in all_versions if v.get('branch', 'master') == branch]
        
        if not versions:
            print(f"El archivo {str_path} no tiene versiones guardadas en la rama {branch}.")
            return True
        
        print(f"\nHistorial de versiones para {str_path} (rama {branch}):")
        print("-" * 60)
        for version in versions:
            timestamp = datetime.datetime.fromisoformat(version['timestamp'])
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Versión: {version['version']}")
            print(f"Fecha: {formatted_time}")
            print(f"Hash: {version['hash']}")
            print(f"Mensaje: {version['message']}")
            print("-" * 60)
        return True

    def checkout(self, file_path, version, branch=None):
        """Recupera una versión específica de un archivo."""
        file_path = Path(file_path)
        version = int(version)
        
        try:
            # Intentar calcular ruta relativa al repositorio
            rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
            str_path = str(rel_path)
        except ValueError:
            # Si no es posible calcular la ruta relativa, usar el nombre del archivo
            str_path = file_path.name
        
        # Cargar el índice
        self._load_index()
        
        # Verificar que el archivo está en el índice
        if str_path not in self.index:
            print(f"Error: El archivo {str_path} no está bajo control de versiones.")
            return False
            
        # Obtener la rama actual si no se especificó una
        if branch is None:
            branch = self._get_current_branch()
            
        # Filtrar versiones por rama
        all_versions = self.index[str_path]['versions']
        versions = [v for v in all_versions if v.get('branch', 'master') == branch]
        
        if not versions:
            print(f"El archivo {str_path} no tiene versiones guardadas en la rama {branch}.")
            return False
            
        if version < 1 or version > len(versions):
            print(f"Error: La versión {version} no existe en la rama {branch}. El rango válido es 1-{len(versions)}.")
            return False
            
        # Obtener la versión solicitada
        version_info = versions[version - 1]
        content_hash = version_info['hash']
        
        # Cargar el objeto
        object_path = self.objects_dir / content_hash[:2] / content_hash[2:]
        if not object_path.exists():
            print(f"Error: No se encuentra el objeto {content_hash}.")
            return False
            
        # Crear una copia de seguridad del archivo actual (si existe)
        if file_path.exists():
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            shutil.copy2(file_path, backup_path)
            print(f"Copia de seguridad creada: {backup_path}")
            
        # Leer, descomprimir y escribir el contenido
        with open(object_path, 'rb') as f:
            compressed = f.read()
            
        content = zlib.decompress(compressed)
        
        # Asegurar que los directorios existan
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir el contenido
        with open(file_path, 'wb') as f:
            f.write(content)
            
        print(f"Archivo {str_path} restaurado a la versión {version} de la rama {branch}.")
        return True

    def branch_create(self, branch_name):
        """Crea una nueva rama."""
        if not branch_name:
            print("Error: Debe especificar un nombre para la rama.")
            return False
            
        branch_path = self.branches_dir / branch_name
        if branch_path.exists():
            print(f"Error: La rama {branch_name} ya existe.")
            return False
            
        # Crear la rama basada en la rama actual
        current_branch = self._get_current_branch()
        current_branch_path = self.branches_dir / current_branch
        
        if current_branch_path.exists():
            # Copiar el contenido de la rama actual
            shutil.copy2(current_branch_path, branch_path)
        else:
            # Crear una rama vacía
            with open(branch_path, 'w') as f:
                f.write('')
                
        print(f"Rama '{branch_name}' creada a partir de '{current_branch}'.")
        return True

    def branch_list(self):
        """Lista todas las ramas disponibles."""
        current_branch = self._get_current_branch()
        branches = []
        
        if self.branches_dir.exists():
            for branch_file in self.branches_dir.iterdir():
                if branch_file.is_file():
                    branches.append(branch_file.name)
        
        if not branches:
            print("No hay ramas disponibles.")
            return False
            
        print("\nRamas disponibles:")
        for branch in sorted(branches):
            if branch == current_branch:
                print(f"* {branch} (actual)")
            else:
                print(f"  {branch}")
                
        return True

    def branch_switch(self, branch_name):
        """Cambia a otra rama."""
        if not branch_name:
            print("Error: Debe especificar el nombre de la rama.")
            return False
            
        branch_path = self.branches_dir / branch_name
        if not branch_path.exists():
            print(f"Error: La rama '{branch_name}' no existe.")
            return False
            
        # Registrar el cambio de rama en el reflog
        current_branch = self._get_current_branch()
        self._add_to_reflog(f"branch switch {branch_name}", current_branch)
        
        # Cambiar a la rama especificada
        self._set_head(branch_name)
        print(f"Cambiado a la rama '{branch_name}'.")
        return True

    def branch_merge(self, source_branch, target_branch=None):
        """Fusiona una rama con otra."""
        if not source_branch:
            print("Error: Debe especificar la rama origen.")
            return False
            
        # Si no se especifica la rama destino, usar la rama actual
        if target_branch is None:
            target_branch = self._get_current_branch()
            
        source_path = self.branches_dir / source_branch
        target_path = self.branches_dir / target_branch
        
        if not source_path.exists():
            print(f"Error: La rama origen '{source_branch}' no existe.")
            return False
            
        if not target_path.exists():
            print(f"Error: La rama destino '{target_branch}' no existe.")
            return False
            
        # Registrar la fusión en el reflog
        self._add_to_reflog(f"branch merge {source_branch} -> {target_branch}", target_branch)
        
        # Cargar el índice
        self._load_index()
        
        # Obtener todos los archivos versionados
        for file_path, file_info in self.index.items():
            # Filtrar versiones por rama origen
            source_versions = [v for v in file_info['versions'] if v.get('branch', 'master') == source_branch]
            if not source_versions:
                continue
                
            # Obtener la última versión de la rama origen
            latest_source_version = source_versions[-1]
            source_hash = latest_source_version['hash']
            
            # Obtener la versión correspondiente en la rama destino
            target_versions = [v for v in file_info['versions'] if v.get('branch', 'master') == target_branch]
            
            if not target_versions or target_versions[-1]['hash'] != source_hash:
                # La versión más reciente de la rama origen es diferente, aplicar cambios
                
                # Recuperar el contenido de la versión de la rama origen
                object_path = self.objects_dir / source_hash[:2] / source_hash[2:]
                if not object_path.exists():
                    print(f"Error: No se encuentra el objeto {source_hash} para {file_path}.")
                    continue
                    
                # Leer, descomprimir y guardar una copia en la rama destino
                with open(object_path, 'rb') as f:
                    compressed = f.read()
                    
                content = zlib.decompress(compressed)
                
                # Crear la ruta de archivo
                abs_file_path = self.repo_path / file_path
                abs_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Crear una copia de seguridad si existe
                if abs_file_path.exists():
                    backup_path = abs_file_path.with_suffix(abs_file_path.suffix + '.merge.bak')
                    shutil.copy2(abs_file_path, backup_path)
                
                # Escribir el contenido
                with open(abs_file_path, 'wb') as f:
                    f.write(content)
                    
                # Agregar la versión a la rama destino
                merge_message = f"Fusionado desde rama '{source_branch}'"
                self.commit(abs_file_path, merge_message, branch=target_branch)
                
                print(f"Fusionado: {file_path}")
                
        print(f"Rama '{source_branch}' fusionada en '{target_branch}'.")
        return True

    def remote_init(self, repo_name):
        """Inicializa un repositorio remoto en Google Drive."""
        if not DRIVE_SUPPORT:
            print("Error: El soporte para Google Drive no está disponible.")
            print("Instale los paquetes requeridos: google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return False
        
        drive = DriveSync(self.repo_path)
        repo_id = drive.init_remote(repo_name)
        
        if repo_id:
            print(f"Para compartir este repositorio, comparta este ID: {repo_id}")
            return True
        return False

    def remote_clone(self, repo_id, target_dir='.'):
        """Clona un repositorio desde Google Drive."""
        if not DRIVE_SUPPORT:
            print("Error: El soporte para Google Drive no está disponible.")
            print("Instale los paquetes requeridos: google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return False
        
        drive = DriveSync()
        result = drive.clone(repo_id, target_dir)
        return result is not None

    def remote_push(self, branch=None):
        """Envía cambios al repositorio remoto."""
        if not DRIVE_SUPPORT:
            print("Error: El soporte para Google Drive no está disponible.")
            print("Instale los paquetes requeridos: google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return False
        
        if branch is None:
            branch = self._get_current_branch()
        
        drive = DriveSync(self.repo_path)
        return drive.push(branch)

    def remote_pull(self, branch=None):
        """Obtiene cambios desde el repositorio remoto."""
        if not DRIVE_SUPPORT:
            print("Error: El soporte para Google Drive no está disponible.")
            print("Instale los paquetes requeridos: google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return False
        
        if branch is None:
            branch = self._get_current_branch()
        
        drive = DriveSync(self.repo_path)
        return drive.pull(branch)

    def remote_share(self, email, role='writer'):
        """Comparte el repositorio remoto con otro usuario."""
        if not DRIVE_SUPPORT:
            print("Error: El soporte para Google Drive no está disponible.")
            print("Instale los paquetes requeridos: google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return False
        
        drive = DriveSync(self.repo_path)
        return drive.share(email, role)

    def _get_current_branch(self):
        """Obtiene el nombre de la rama actual."""
        if self.head_file.exists():
            with open(self.head_file, 'r') as f:
                return f.read().strip()
        return "master"

    def _set_head(self, branch_name):
        """Establece la rama actual."""
        with open(self.head_file, 'w') as f:
            f.write(branch_name)
        self.current_branch = branch_name

    def _update_branch_ref(self, branch_name, content_hash):
        """Actualiza la referencia de una rama."""
        # Usar os.path en lugar de pathlib para mayor compatibilidad con directorios ocultos
        branch_dir = os.path.join(self.vcs_dir, "refs", "branches")
        if not os.path.exists(branch_dir):
            try:
                os.makedirs(branch_dir, exist_ok=True)
            except Exception as e:
                print(f"Error al crear directorio de ramas {branch_dir}: {str(e)}")
                return False
        
        branch_path = os.path.join(branch_dir, branch_name)
        
        try:
            with open(branch_path, 'w') as f:
                f.write(content_hash)
        except Exception as e:
            print(f"Error al escribir referencia de rama {branch_path}: {str(e)}")
            return False
        
        return True

    def _save_config(self):
        """Guarda la configuración en disco."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)

    def _load_config(self):
        """Carga la configuración desde disco."""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)

    def _save_index(self):
        """Guarda el índice en disco."""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2)

    def _load_index(self):
        """Carga el índice desde disco."""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
        else:
            self.index = {}

    def status(self):
        """Muestra el estado de los archivos: modificados, añadidos y sin seguimiento."""
        # Cargar el índice
        self._load_index()
        
        # Inicializar listas para cada categoría
        modificados = []
        sin_commit = []
        sin_seguimiento = []
        
        # Crear un conjunto con todas las rutas normalizadas en el índice
        rutas_en_indice = set()
        for str_path in self.index.keys():
            # Normalizar la ruta para comparaciones
            # Convertir todas las barras a formato Unix (/) para consistencia
            ruta_normalizada = str_path.replace('\\', '/')
            rutas_en_indice.add(ruta_normalizada)
        
        # Obtener la rama actual
        branch = self._get_current_branch()
        print(f"\nEstado de la rama '{branch}':")
        
        # Analizar todos los archivos bajo control de versiones
        for file_path, info in self.index.items():
            # Convertir la ruta para el sistema operativo actual
            file_sys_path = file_path.replace('/', os.path.sep)
            abs_path = self.repo_path / file_sys_path
            
            # Si el archivo no existe en disco, ha sido eliminado
            if not abs_path.exists():
                modificados.append(f"eliminado: {file_path}")
                continue
                
            # Verificar si el archivo tiene versiones
            if not info.get('versions'):
                sin_commit.append(file_path)
                continue
                
            # Filtrar versiones para la rama actual
            versiones_rama = [v for v in info['versions'] if v.get('branch', 'master') == branch]
            if not versiones_rama:
                sin_commit.append(file_path)
                continue
                
            # Obtener la última versión y comparar con el contenido actual
            ultima_version = versiones_rama[-1]
            hash_original = ultima_version['hash']
            
            # Leer el contenido actual y calcular su hash
            try:
                with open(abs_path, 'rb') as f:
                    contenido = f.read()
                hash_actual = hashlib.sha256(contenido).hexdigest()
                
                # Si los hashes son diferentes, el archivo ha sido modificado
                if hash_actual != hash_original:
                    modificados.append(f"modificado: {file_path}")
            except Exception:
                modificados.append(f"error al leer: {file_path}")
        
        # Recolectar todos los archivos del sistema de archivos
        archivos_en_disco = set()
        
        # Método 1: Usar os.walk para encontrar todos los archivos en todas las carpetas
        for root, _, files in os.walk(self.repo_path):
            # Ignorar el directorio .shit y otros directorios ocultos
            if '.shit' in root or os.path.basename(root).startswith('.'):
                continue
                
            for file in files:
                # Ignorar archivos ocultos
                if file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    # Convertir a ruta relativa para comparar con el índice
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    # Normalizar la ruta con / para comparar correctamente
                    rel_path = rel_path.replace(os.path.sep, '/')
                    archivos_en_disco.add(rel_path)
                except Exception as e:
                    print(f"Error al procesar archivo {file_path}: {str(e)}")
                    continue
        
        # Método 2: Verificar explícitamente los archivos en el directorio raíz
        for item in os.listdir(self.repo_path):
            item_path = os.path.join(self.repo_path, item)
            # Solo incluir archivos (no directorios) y que no estén ocultos
            if os.path.isfile(item_path) and not item.startswith('.'):
                rel_path = os.path.relpath(item_path, self.repo_path)
                rel_path = rel_path.replace(os.path.sep, '/')
                archivos_en_disco.add(rel_path)
        
        # Encontrar archivos sin seguimiento (en disco pero no en el índice)
        for archivo in archivos_en_disco:
            # Normalizar ruta para comparación consistente
            archivo_normalizado = archivo.replace('\\', '/')
            if archivo_normalizado not in rutas_en_indice:
                sin_seguimiento.append(archivo_normalizado)
        
        # Mostrar los resultados
        if modificados:
            print("\nArchivos modificados:")
            for file in sorted(modificados):
                print(f"  {file}")
                
        if sin_commit:
            print("\nArchivos añadidos al control de versiones (sin commit):")
            for file in sorted(sin_commit):
                print(f"  {file}")
                
        if sin_seguimiento:
            print("\nArchivos sin seguimiento:")
            for file in sorted(sin_seguimiento):
                print(f"  {file}")
                
        if not modificados and not sin_commit and not sin_seguimiento:
            print("No hay cambios en los archivos.")
            
        return True

    def reset(self, commit_hash, mode="soft"):
        """Retrocede HEAD a un commit específico.
        
        Modos:
        - soft: Retrocede HEAD y deja cambios en staging
        """
        # Verificar que el modo es válido
        if mode not in ["soft"]:
            print(f"Error: Modo '{mode}' no soportado. Use 'soft'.")
            return False
            
        # Cargar el índice
        self._load_index()
        
        # Verificar que el hash existe en algún archivo
        hash_exists = False
        affected_files = []
        
        for file_path, info in self.index.items():
            versions = info.get('versions', [])
            for version in versions:
                if version.get('hash') == commit_hash:
                    hash_exists = True
                    affected_files.append((file_path, version))
        
        if not hash_exists:
            print(f"Error: No se encontró ningún commit con hash '{commit_hash}'.")
            return False
            
        # Obtener la rama actual
        current_branch = self._get_current_branch()
        
        # Guardar el estado actual en reflog
        self._add_to_reflog(f"reset --{mode} {commit_hash}", current_branch)
        
        # Actualizar la referencia de la rama
        self._update_branch_ref(current_branch, commit_hash)
        
        print(f"HEAD retrocedió a {commit_hash} en modo {mode}.")
        print(f"Archivos afectados: {len(affected_files)}")
        
        return True
        
    def reflog(self):
        """Muestra el historial de movimientos de HEAD."""
        reflog_file = self.vcs_dir / 'reflog'
        
        if not reflog_file.exists():
            print("No hay historial de movimientos de HEAD.")
            return True
            
        try:
            with open(reflog_file, 'r') as f:
                entries = f.readlines()
                
            print("\nHistorial de movimientos de HEAD:")
            print("-" * 60)
            
            # Mostrar entradas del más reciente al más antiguo
            for entry in reversed(entries):
                entry = entry.strip()
                if entry:
                    # Formato: timestamp|hash|command|branch
                    parts = entry.split('|')
                    if len(parts) >= 4:
                        timestamp, hash_val, command, branch = parts[:4]
                        # Convertir timestamp a formato legible
                        dt = datetime.datetime.fromtimestamp(float(timestamp))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"{hash_val[:8]} - {formatted_time} - {branch}: {command}")
            
            print("-" * 60)
            return True
        except Exception as e:
            print(f"Error al leer el reflog: {str(e)}")
            return False
    
    def _add_to_reflog(self, command, branch):
        """Añade una entrada al reflog."""
        reflog_file = self.vcs_dir / 'reflog'
        
        # Obtener el hash actual de la rama
        branch_file = self.branches_dir / branch
        current_hash = ""
        
        if branch_file.exists():
            try:
                with open(branch_file, 'r') as f:
                    current_hash = f.read().strip()
            except Exception:
                pass
        
        # Crear la entrada del reflog
        timestamp = time.time()
        entry = f"{timestamp}|{current_hash}|{command}|{branch}\n"
        
        # Añadir al archivo
        try:
            with open(reflog_file, 'a+') as f:
                f.write(entry)
        except Exception as e:
            print(f"Advertencia: No se pudo actualizar el reflog: {str(e)}")


# Funciones para el modo local (como Git)
def setup_shit():
    """Configura el entorno para SHIT"""
    # En modo local, no necesitamos un directorio global
    if LOCAL_MODE:
        # Copiar los scripts necesarios si no existen
        current_dir = os.path.dirname(os.path.abspath(__file__))
        files_to_copy = ["drive_sync.py", "requirements.txt"]
        
        # El directorio oculto está en el directorio actual
        vcs_dir = os.path.join(os.getcwd(), ".shit")
        if not os.path.exists(vcs_dir):
            os.makedirs(vcs_dir, exist_ok=True)
            # Ocultar el directorio en Windows
            hide_directory(vcs_dir)
        
        for file in files_to_copy:
            src_file = os.path.join(current_dir, file)
            dst_file = os.path.join(vcs_dir, file)
            
            if os.path.exists(src_file) and not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
        
        print(f"Configuración de SHIT completada en: {vcs_dir}")
        return True
    else:
        # Modo centralizado (original)
        if not os.path.exists(HOME_DIR):
            os.makedirs(HOME_DIR, exist_ok=True)
            print(f"Directorio oculto creado en: {HOME_DIR}")
        
        # Copiamos los scripts necesarios si no existen
        current_dir = os.path.dirname(os.path.abspath(__file__))
        files_to_copy = ["shit.py", "drive_sync.py", "requirements.txt"]
        
        for file in files_to_copy:
            src_file = os.path.join(current_dir, file)
            dst_file = os.path.join(HOME_DIR, file)
            
            if os.path.exists(src_file) and not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                print(f"Copiado: {file} a {HOME_DIR}")
        
        # Crear un subdirectorio para los repositorios
        repos_dir = os.path.join(HOME_DIR, "repos")
        if not os.path.exists(repos_dir):
            os.makedirs(repos_dir, exist_ok=True)
            print(f"Directorio para repositorios creado en: {repos_dir}")
        
        print("Configuración de SHIT completada.")
        return True

def find_repo_root():
    """Busca el directorio raíz del repositorio desde el directorio actual"""
    if LOCAL_MODE:
        # En modo local, buscar el directorio .shit en los directorios superiores
        current = Path(os.getcwd())
        while current != current.parent:  # Mientras no lleguemos a la raíz del sistema
            shit_dir = current / '.shit'
            if shit_dir.exists() and shit_dir.is_dir():
                return str(current)
            current = current.parent
        return None
    else:
        # Modo centralizado (original)
        current_dir = os.getcwd()
        
        # Buscar un mapeo en el archivo de configuración
        mapping_file = os.path.join(HOME_DIR, "mapping.txt")
        if os.path.exists(mapping_file):
            with open(mapping_file, "r") as f:
                for line in f:
                    if line.strip():
                        work_dir, repo_dir = line.strip().split("=")
                        if current_dir.startswith(work_dir):
                            return repo_dir
        
        return None

def create_repo_mapping(work_dir, repo_dir):
    """Crea un mapeo entre el directorio de trabajo y el repositorio oculto"""
    mapping_file = os.path.join(HOME_DIR, "mapping.txt")
    
    # Crear o actualizar el mapeo
    mappings = {}
    if os.path.exists(mapping_file):
        with open(mapping_file, "r") as f:
            for line in f:
                if line.strip():
                    w_dir, r_dir = line.strip().split("=")
                    mappings[w_dir] = r_dir
    
    mappings[work_dir] = repo_dir
    
    with open(mapping_file, "w") as f:
        for w_dir, r_dir in mappings.items():
            f.write(f"{w_dir}={r_dir}\n")
    
    return True

def init_repo():
    """Inicializa un repositorio para el directorio actual"""
    if LOCAL_MODE:
        # En modo local, crear el directorio .shit en el directorio actual
        work_dir = os.getcwd()
        
        # Verificar si ya existe un repositorio
        shit_dir = os.path.join(work_dir, ".shit")
        if os.path.exists(shit_dir):
            print(f"El repositorio ya existe en: {shit_dir}")
            return True
            
        # Crear el directorio .shit si no existe
        if not os.path.exists(shit_dir):
            os.makedirs(shit_dir, exist_ok=True)
            
        # Crear subdirectorios necesarios
        os.makedirs(os.path.join(shit_dir, "objects"), exist_ok=True)
        os.makedirs(os.path.join(shit_dir, "refs", "branches"), exist_ok=True)
        
        # Crear archivos de configuración iniciales
        config = {
            'version': '1.0',
            'created_at': datetime.datetime.now().isoformat(),
        }
        
        with open(os.path.join(shit_dir, "config.json"), 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
            
        with open(os.path.join(shit_dir, "index.json"), 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)
            
        # Inicializar rama master (por defecto)
        with open(os.path.join(shit_dir, "HEAD"), 'w') as f:
            f.write("master")
            
        # Ocultar el directorio en Windows
        hide_directory(shit_dir)
        
        print(f"Repositorio inicializado en: {work_dir}")
        return True
    else:
        # Modo centralizado (original)
        work_dir = os.getcwd()
        
        # Crear un nombre para el repositorio basado en el directorio actual
        repo_name = f"{Path(work_dir).name}_{getpass.getuser()}_{hash(work_dir) % 10000}"
        repo_dir = os.path.join(HOME_DIR, "repos", repo_name)
        
        # Crear el directorio del repositorio
        if not os.path.exists(repo_dir):
            os.makedirs(repo_dir, exist_ok=True)
        
        # Inicializar un objeto SHIT para el repositorio oculto
        vcs = SHIT(repo_dir)
        result = vcs.init()
        
        if result:
            # Crear mapeo entre el directorio de trabajo y el repositorio
            create_repo_mapping(work_dir, repo_dir)
            print(f"Repositorio inicializado para: {work_dir}")
            print(f"Almacenado en: {repo_dir}")
            return True
        else:
            print(f"Error al inicializar el repositorio")
            return False

def execute_shit_command(args):
    """Ejecuta un comando de SHIT en el repositorio correspondiente"""
    if LOCAL_MODE:
        # En modo local, buscamos el directorio .shit o lo creamos
        repo_dir = find_repo_root()
        
        if not repo_dir and args and args[0] != "init":
            print("Error: No se encontró un repositorio para este directorio.")
            print("Ejecute 'shit init' para inicializar un repositorio.")
            return False
        
        # Si es un comando init, usamos el directorio actual
        if args and args[0] == "init":
            repo_dir = os.getcwd()
    else:
        # Modo centralizado (original)
        repo_dir = find_repo_root()
        
        if not repo_dir:
            print("Error: No se encontró un repositorio para este directorio.")
            print("Ejecute 'shit init' para inicializar un repositorio.")
            return False

    # Crear una instancia de SHIT para el repositorio encontrado
    vcs = SHIT(repo_dir)
    
    # Convertir rutas relativas a absolutas para los comandos que toman archivos
    if args and args[0] in ["add", "commit", "log", "checkout"]:
        if len(args) > 1 and not os.path.isabs(args[1]):
            args[1] = os.path.abspath(args[1])
    
    # Ejecutar el comando correspondiente
    if args and args[0] == "add":
        if "-A" in args or "--all" in args:
            return vcs.add_all()
        elif len(args) > 1:
            # Si estamos en el directorio de trabajo (no en el repo oculto)
            # No intentar calcular ruta relativa, permitir que add maneje el path absoluto
            abs_path = os.path.abspath(args[1])
            return vcs.add(abs_path)
        else:
            print("Error: Debe especificar un archivo o usar la opción -A para añadir todos los archivos.")
            return False
    elif args and args[0] == "commit":
        if "-m" in args:
            msg_index = args.index("-m") + 1
            if msg_index < len(args):
                message = args[msg_index]
            else:
                print("Error: Falta el mensaje después de -m")
                return False
        else:
            print("Error: Debe especificar un mensaje con -m")
            return False
        
        branch = None
        if "-b" in args:
            b_index = args.index("-b") + 1
            if b_index < len(args):
                branch = args[b_index]
        
        # Verificar si hay un archivo específico o si es un commit general
        file_path = None
        # Buscar si hay un archivo para commit que no sea parte de una opción
        for i, arg in enumerate(args):
            # El primer argumento es "commit", omitirlo
            if i == 0:
                continue
            # Omitir las opciones y sus valores
            if arg.startswith("-"):
                continue
            if i > 0 and args[i-1].startswith("-"):
                continue
            # Si encontramos un argumento que no es una opción ni valor de opción, es el archivo
            file_path = arg
            break
            
        if file_path:
            # Usar ruta absoluta si se especificó un archivo
            abs_path = os.path.abspath(file_path)
            return vcs.commit(abs_path, message, branch)
        else:
            # Commit de todos los archivos en staging
            return vcs.commit(None, message, branch)
    elif args and args[0] == "log" and len(args) > 1:
        branch = None
        if "-b" in args:
            b_index = args.index("-b") + 1
            if b_index < len(args):
                branch = args[b_index]
        
        # Usar ruta absoluta
        abs_path = os.path.abspath(args[1])
        return vcs.log(abs_path, branch)
    elif args and args[0] == "checkout" and len(args) > 2:
        branch = None
        if "-b" in args:
            b_index = args.index("-b") + 1
            if b_index < len(args):
                branch = args[b_index]
        
        try:
            version = int(args[2])
            # Usar ruta absoluta
            abs_path = os.path.abspath(args[1])
            return vcs.checkout(abs_path, version, branch)
        except ValueError:
            print(f"Error: La versión debe ser un número entero")
            return False
    elif args and args[0] == "branch":
        if len(args) > 1:
            if args[1] == "create" and len(args) > 2:
                return vcs.branch_create(args[2])
            elif args[1] == "list":
                return vcs.branch_list()
            elif args[1] == "switch" and len(args) > 2:
                return vcs.branch_switch(args[2])
            elif args[1] == "merge" and len(args) > 2:
                target = None
                if len(args) > 3:
                    target = args[3]
                return vcs.branch_merge(args[2], target)
        print("Comando de rama no válido")
        return False
    elif args and args[0] == "remote":
        if len(args) > 1:
            if args[1] == "init" and len(args) > 2:
                return vcs.remote_init(args[2])
            elif args[1] == "clone" and len(args) > 2:
                target_dir = '.'
                if len(args) > 3:
                    target_dir = args[3]
                return vcs.remote_clone(args[2], target_dir)
            elif args[1] == "push":
                branch = None
                if "-b" in args:
                    b_index = args.index("-b") + 1
                    if b_index < len(args):
                        branch = args[b_index]
                return vcs.remote_push(branch)
            elif args[1] == "pull":
                branch = None
                if "-b" in args:
                    b_index = args.index("-b") + 1
                    if b_index < len(args):
                        branch = args[b_index]
                return vcs.remote_pull(branch)
            elif args[1] == "share" and len(args) > 2:
                role = "writer"
                if "-r" in args:
                    r_index = args.index("-r") + 1
                    if r_index < len(args):
                        role = args[r_index]
                return vcs.remote_share(args[2], role)
        print("Comando remoto no válido")
        return False
    elif args and args[0] == "status":
        return vcs.status()
    elif args and args[0] == "reset":
        if len(args) > 1:
            mode = "soft"
            if "-m" in args:
                m_index = args.index("-m") + 1
                if m_index < len(args):
                    mode = args[m_index]
            elif "--mode" in args:
                m_index = args.index("--mode") + 1
                if m_index < len(args):
                    mode = args[m_index]
            # Reconocer --soft como una opción específica
            elif "--soft" in args:
                mode = "soft"
            return vcs.reset(args[1], mode)
    elif args and args[0] == "reflog":
        return vcs.reflog()
    else:
        print("Uso: shit <comando> [argumentos]")
        print("Comandos disponibles:")
        print("  init             - Inicializa un repositorio")
        print("  add <archivo>    - Añade un archivo al control de versiones")
        print("  add -A          - Añade todos los archivos modificados")
        print("  commit -m \"mensaje\" - Guarda versión de todos los archivos en staging")
        print("  commit <archivo> -m \"mensaje\" - Guarda versión de un archivo específico")
        print("  log <archivo>    - Muestra el historial de versiones")
        print("  status           - Muestra archivos modificados, añadidos y sin seguimiento")
        print("  checkout <archivo> <versión> - Recupera una versión")
        print("  branch create <nombre> - Crea una nueva rama")
        print("  branch list      - Lista las ramas disponibles")
        print("  branch switch <nombre> - Cambia a otra rama")
        print("  branch merge <origen> [destino] - Fusiona ramas")
        print("  remote init <nombre> - Inicializa un repositorio remoto en Google Drive")
        print("  remote clone <repo_id> [target_dir] - Clona un repositorio desde Google Drive")
        print("  remote push [-b branch] - Envía cambios al repositorio remoto")
        print("  remote pull [-b branch] - Obtiene cambios desde el repositorio remoto")
        print("  remote share <email> [-r role] - Comparte el repositorio con otro usuario")
        print("  reset <commit_hash> [-m mode] - Retrocede HEAD a un commit específico")
        print("  reflog           - Muestra el historial de movimientos de HEAD")
        return False


# CLI con Click para la interfaz de línea de comandos estándar
@click.group()
def cli():
    """SHIT - Sistema de Historial Integral de Transformaciones."""
    pass


@cli.command()
@click.argument('directory', required=False, default='.')
def init(directory):
    """Inicializa un repositorio."""
    vcs = SHIT(directory)
    vcs.init()


@cli.command()
@click.argument('file', required=False, type=click.Path(exists=True))
@click.option('-A', '--all', is_flag=True, help='Añade todos los archivos modificados')
def add(file, all):
    """Añade archivos al control de versiones."""
    vcs = SHIT()
    if all:
        vcs.add_all()
    elif file:
        vcs.add(file)
    else:
        print("Error: Debe especificar un archivo o usar la opción -A para añadir todos los archivos.")


@cli.command()
@click.argument('file', required=False, type=click.Path(exists=True))
@click.option('-m', '--message', required=True, help='Mensaje descriptivo de la versión')
@click.option('-b', '--branch', help='Rama en la que se guardará la versión')
def commit(file, message, branch):
    """Guarda una nueva versión de un archivo o de todos los archivos en staging."""
    vcs = SHIT()
    vcs.commit(file, message, branch)


@cli.command()
@click.argument('file', required=False)
@click.option('-b', '--branch', help='Rama específica a consultar')
def log(file, branch):
    """Muestra el historial de versiones de un archivo o de todos los archivos si no se especifica."""
    vcs = SHIT()
    vcs.log(file, branch)


@cli.command()
@click.argument('file', required=True, type=click.Path())
@click.argument('version', required=True, type=int)
@click.option('-b', '--branch', help='Rama de la que recuperar')
def checkout(file, version, branch):
    """Recupera una versión específica de un archivo."""
    vcs = SHIT()
    vcs.checkout(file, version, branch)


# Grupo de comandos para ramas
@cli.group()
def branch():
    """Gestión de ramas."""
    pass


@branch.command(name='create')
@click.argument('name', required=True)
def branch_create_cmd(name):
    """Crea una nueva rama."""
    vcs = SHIT()
    vcs.branch_create(name)


@branch.command(name='list')
def branch_list_cmd():
    """Lista todas las ramas disponibles."""
    vcs = SHIT()
    vcs.branch_list()


@branch.command(name='switch')
@click.argument('name', required=True)
def branch_switch_cmd(name):
    """Cambia a otra rama."""
    vcs = SHIT()
    vcs.branch_switch(name)


@branch.command(name='merge')
@click.argument('source', required=True)
@click.argument('target', required=False)
def branch_merge_cmd(source, target):
    """Fusiona una rama con otra."""
    vcs = SHIT()
    vcs.branch_merge(source, target)


# Grupo de comandos para repositorios remotos
@cli.group()
def remote():
    """Gestión de repositorios remotos."""
    pass


@remote.command(name='init')
@click.argument('name', required=True)
def remote_init_cmd(name):
    """Inicializa un repositorio remoto en Google Drive."""
    vcs = SHIT()
    vcs.remote_init(name)


@remote.command(name='clone')
@click.argument('repo_id', required=True)
@click.argument('directory', required=False, default='.')
def remote_clone_cmd(repo_id, directory):
    """Clona un repositorio desde Google Drive."""
    vcs = SHIT()
    vcs.remote_clone(repo_id, directory)


@remote.command(name='push')
@click.option('-b', '--branch', help='Rama específica a enviar')
def remote_push_cmd(branch):
    """Envía cambios al repositorio remoto."""
    vcs = SHIT()
    vcs.remote_push(branch)


@remote.command(name='pull')
@click.option('-b', '--branch', help='Rama específica a obtener')
def remote_pull_cmd(branch):
    """Obtiene cambios desde el repositorio remoto."""
    vcs = SHIT()
    vcs.remote_pull(branch)


@remote.command(name='share')
@click.argument('email', required=True)
@click.option('-r', '--role', default='writer', 
              type=click.Choice(['reader', 'writer', 'commenter']),
              help='Rol del usuario (reader, writer, commenter)')
def remote_share_cmd(email, role):
    """Comparte el repositorio con otro usuario."""
    vcs = SHIT()
    vcs.remote_share(email, role)


@cli.command()
def status():
    """Muestra archivos modificados, añadidos y sin seguimiento."""
    vcs = SHIT()
    vcs.status()


@cli.command()
@click.argument('commit_hash', required=True)
@click.option('-m', '--mode', default='soft', help='Modo de reset')
@click.option('--soft', is_flag=True, default=False, show_default=True, help='Equivalente a --mode=soft')
def reset(commit_hash, mode, soft):
    """Retrocede HEAD a un commit específico."""
    vcs = SHIT()
    # Si se usa --soft, ignorar el valor de mode
    if soft:
        mode = "soft"
    vcs.reset(commit_hash, mode)


@cli.command()
def reflog():
    """Muestra el historial de movimientos de HEAD."""
    vcs = SHIT()
    vcs.reflog()


# Punto de entrada para la ejecución del script
def main():
    # Siempre usar la interfaz de Click para todos los comandos
    cli()


if __name__ == '__main__':
    main() 