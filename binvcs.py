#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BinVCS - Sistema de Control de Versiones para Archivos Binarios
"""

import os
import sys
import hashlib
import zlib
import json
import click
import datetime
import shutil
import time
from pathlib import Path

# Importar el módulo de sincronización con Google Drive
try:
    from drive_sync import DriveSync
    DRIVE_SUPPORT = True
except ImportError:
    DRIVE_SUPPORT = False


class BinVCS:
    """Clase principal para el control de versiones de archivos binarios."""

    def __init__(self, repo_path='.'):
        """Inicializa el sistema de control de versiones."""
        self.repo_path = Path(repo_path)
        self.vcs_dir = self.repo_path / '.binvcs'
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
        
        print(f"Repositorio inicializado en: {self.repo_path}")
        return True

    def add(self, file_path):
        """Añade un archivo al control de versiones."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            print(f"Error: El archivo {file_path} no existe.")
            return False
            
        if not file_path.is_file():
            print(f"Error: {file_path} no es un archivo.")
            return False

        # Cargar el índice actual
        self._load_index()
        
        # Calcular ruta relativa al repositorio
        rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
        str_path = str(rel_path)
        
        # Añadir archivo al índice
        self.index[str_path] = {
            'added_at': datetime.datetime.now().isoformat(),
            'versions': []
        }
        
        self._save_index()
        print(f"Archivo {rel_path} añadido al control de versiones.")
        return True

    def commit(self, file_path, message, branch=None):
        """Guarda una nueva versión del archivo."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            print(f"Error: El archivo {file_path} no existe.")
            return False
            
        # Calcular ruta relativa al repositorio
        rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
        str_path = str(rel_path)
        
        # Cargar el índice
        self._load_index()
        
        # Verificar que el archivo está en el índice
        if str_path not in self.index:
            print(f"Error: El archivo {rel_path} no está bajo control de versiones. Usa 'add' primero.")
            return False
            
        # Leer el contenido del archivo
        with open(file_path, 'rb') as f:
            content = f.read()
            
        # Calcular hash del contenido
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Obtener la rama actual si no se especificó una
        if branch is None:
            branch = self._get_current_branch()
            
        # Verificar si esta versión ya existe
        versions = self.index[str_path]['versions']
        branch_versions = [v for v in versions if v.get('branch', 'master') == branch]
        
        if branch_versions and branch_versions[-1]['hash'] == content_hash:
            print(f"No hay cambios en el archivo {rel_path} desde la última versión en la rama {branch}.")
            return False
            
        # Comprimir el contenido
        compressed = zlib.compress(content)
        
        # Guardar el objeto
        object_path = self.objects_dir / content_hash[:2] / content_hash[2:]
        object_path.parent.mkdir(exist_ok=True)
        with open(object_path, 'wb') as f:
            f.write(compressed)
            
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
        
        # Actualizar la referencia de la rama
        self._update_branch_ref(branch, content_hash)
        
        print(f"Nueva versión de {rel_path} guardada (v{version_info['version']}) en rama {branch}.")
        return True

    def log(self, file_path, branch=None):
        """Muestra el historial de versiones de un archivo."""
        file_path = Path(file_path)
        
        # Calcular ruta relativa al repositorio
        rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
        str_path = str(rel_path)
        
        # Cargar el índice
        self._load_index()
        
        # Verificar que el archivo está en el índice
        if str_path not in self.index:
            print(f"Error: El archivo {rel_path} no está bajo control de versiones.")
            return False
            
        # Obtener la rama actual si no se especificó una
        if branch is None:
            branch = self._get_current_branch()
            
        # Filtrar versiones por rama
        all_versions = self.index[str_path]['versions']
        versions = [v for v in all_versions if v.get('branch', 'master') == branch]
            
        if not versions:
            print(f"El archivo {rel_path} no tiene versiones guardadas en la rama {branch}.")
            return True
            
        print(f"\nHistorial de versiones para {rel_path} (rama {branch}):")
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
        
        # Calcular ruta relativa al repositorio
        rel_path = file_path.resolve().relative_to(self.repo_path.resolve())
        str_path = str(rel_path)
        
        # Cargar el índice
        self._load_index()
        
        # Verificar que el archivo está en el índice
        if str_path not in self.index:
            print(f"Error: El archivo {rel_path} no está bajo control de versiones.")
            return False
            
        # Obtener la rama actual si no se especificó una
        if branch is None:
            branch = self._get_current_branch()
            
        # Filtrar versiones por rama
        all_versions = self.index[str_path]['versions']
        versions = [v for v in all_versions if v.get('branch', 'master') == branch]
        
        if not versions:
            print(f"El archivo {rel_path} no tiene versiones guardadas en la rama {branch}.")
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
            
        print(f"Archivo {rel_path} restaurado a la versión {version} de la rama {branch}.")
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
        branch_path = self.branches_dir / branch_name
        self.branches_dir.mkdir(exist_ok=True)
        
        with open(branch_path, 'w') as f:
            f.write(content_hash)

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


# CLI con Click
@click.group()
def cli():
    """BinVCS - Control de Versiones para Archivos Binarios."""
    pass


@cli.command()
@click.argument('directory', required=False, default='.')
def init(directory):
    """Inicializa un repositorio."""
    vcs = BinVCS(directory)
    vcs.init()


@cli.command()
@click.argument('file', required=True, type=click.Path(exists=True))
def add(file):
    """Añade un archivo al control de versiones."""
    vcs = BinVCS()
    vcs.add(file)


@cli.command()
@click.argument('file', required=True, type=click.Path(exists=True))
@click.option('-m', '--message', required=True, help='Mensaje descriptivo de la versión')
@click.option('-b', '--branch', help='Rama en la que se guardará la versión')
def commit(file, message, branch):
    """Guarda una nueva versión de un archivo."""
    vcs = BinVCS()
    vcs.commit(file, message, branch)


@cli.command()
@click.argument('file', required=True, type=click.Path(exists=True))
@click.option('-b', '--branch', help='Rama específica a consultar')
def log(file, branch):
    """Muestra el historial de versiones de un archivo."""
    vcs = BinVCS()
    vcs.log(file, branch)


@cli.command()
@click.argument('file', required=True, type=click.Path())
@click.argument('version', required=True, type=int)
@click.option('-b', '--branch', help='Rama de la que recuperar')
def checkout(file, version, branch):
    """Recupera una versión específica de un archivo."""
    vcs = BinVCS()
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
    vcs = BinVCS()
    vcs.branch_create(name)


@branch.command(name='list')
def branch_list_cmd():
    """Lista todas las ramas disponibles."""
    vcs = BinVCS()
    vcs.branch_list()


@branch.command(name='switch')
@click.argument('name', required=True)
def branch_switch_cmd(name):
    """Cambia a otra rama."""
    vcs = BinVCS()
    vcs.branch_switch(name)


@branch.command(name='merge')
@click.argument('source', required=True)
@click.argument('target', required=False)
def branch_merge_cmd(source, target):
    """Fusiona una rama con otra."""
    vcs = BinVCS()
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
    vcs = BinVCS()
    vcs.remote_init(name)


@remote.command(name='clone')
@click.argument('repo_id', required=True)
@click.argument('directory', required=False, default='.')
def remote_clone_cmd(repo_id, directory):
    """Clona un repositorio desde Google Drive."""
    vcs = BinVCS()
    vcs.remote_clone(repo_id, directory)


@remote.command(name='push')
@click.option('-b', '--branch', help='Rama específica a enviar')
def remote_push_cmd(branch):
    """Envía cambios al repositorio remoto."""
    vcs = BinVCS()
    vcs.remote_push(branch)


@remote.command(name='pull')
@click.option('-b', '--branch', help='Rama específica a obtener')
def remote_pull_cmd(branch):
    """Obtiene cambios desde el repositorio remoto."""
    vcs = BinVCS()
    vcs.remote_pull(branch)


@remote.command(name='share')
@click.argument('email', required=True)
@click.option('-r', '--role', default='writer', 
              type=click.Choice(['reader', 'writer', 'commenter']),
              help='Rol del usuario (reader, writer, commenter)')
def remote_share_cmd(email, role):
    """Comparte el repositorio con otro usuario."""
    vcs = BinVCS()
    vcs.remote_share(email, role)


if __name__ == '__main__':
    cli() 