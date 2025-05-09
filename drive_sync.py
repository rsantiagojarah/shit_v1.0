#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Módulo de integración de SHIT con Google Drive
Permite sincronizar repositorios locales con Google Drive para colaboración.
"""

import os
import json
import pickle
import time
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import io
import hashlib


# Permisos necesarios para Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'

class DriveSync:
    """Clase para manejar la sincronización con Google Drive."""
    
    def __init__(self, repo_path='.'):
        """Inicializa el cliente de Google Drive."""
        self.repo_path = Path(repo_path)
        self.vcs_dir = self.repo_path / '.shit'
        self.drive_config_file = self.vcs_dir / 'drive_config.json'
        self.drive_config = {}
        self.service = None
        
    def authenticate(self):
        """Autentica con Google Drive API."""
        creds = None
        
        # Buscar el archivo de token tanto en directorio actual como en .shit
        token_paths = [
            Path(TOKEN_FILE),
            self.vcs_dir / TOKEN_FILE
        ]
        
        for token_path in token_paths:
            if token_path.exists():
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
                    break
        
        # Si no hay credenciales válidas, solicitar inicio de sesión
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                credentials_paths = [
                    Path(CREDENTIALS_FILE),
                    self.vcs_dir / CREDENTIALS_FILE
                ]
                
                credentials_path = None
                for path in credentials_paths:
                    if path.exists():
                        credentials_path = path
                        break
                
                if not credentials_path:
                    raise FileNotFoundError(
                        "No se encontró el archivo de credenciales. "
                        "Descárgalo desde la Consola de Google Cloud y guárdalo como "
                        f"'{CREDENTIALS_FILE}' en el directorio del repositorio."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Guardar el token para la próxima vez
            token_save_path = self.vcs_dir / TOKEN_FILE
            self.vcs_dir.mkdir(exist_ok=True)
            with open(token_save_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        return True
    
    def init_remote(self, repo_name):
        """Inicializa un repositorio remoto en Google Drive."""
        try:
            self.authenticate()
            
            # Crear carpeta principal del proyecto
            file_metadata = {
                'name': repo_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            
            # Crear subcarpetas necesarias
            objects_folder = self._create_folder('objects', folder_id)
            refs_folder = self._create_folder('refs', folder_id)
            
            # Guardar la configuración
            self.drive_config = {
                'repo_name': repo_name,
                'repo_id': folder_id,
                'objects_folder_id': objects_folder,
                'refs_folder_id': refs_folder,
                'last_sync': None
            }
            
            # Guardar la configuración de Drive
            self._save_drive_config()
            
            print(f"Repositorio remoto '{repo_name}' inicializado en Google Drive.")
            print(f"ID del repositorio: {folder_id}")
            
            # Crear archivo compartido de configuración
            self._upload_file(
                self.vcs_dir / 'config.json',
                'config.json',
                folder_id,
                'application/json'
            )
            
            return folder_id
            
        except Exception as e:
            print(f"Error al inicializar repositorio remoto: {e}")
            return None
    
    def clone(self, repo_id, target_dir='.'):
        """Clona un repositorio desde Google Drive."""
        target_path = Path(target_dir)
        target_path.mkdir(exist_ok=True)
        
        try:
            self.authenticate()
            
            # Obtener información del repositorio
            repo_file = self.service.files().get(fileId=repo_id).execute()
            repo_name = repo_file['name']
            
            # Crear estructura de directorios local
            local_repo = target_path / repo_name
            local_repo.mkdir(exist_ok=True)
            
            vcs_dir = local_repo / '.shit'
            vcs_dir.mkdir(exist_ok=True)
            
            objects_dir = vcs_dir / 'objects'
            objects_dir.mkdir(exist_ok=True)
            
            refs_dir = vcs_dir / 'refs'
            refs_dir.mkdir(exist_ok=True)
            
            # Buscar subcarpetas
            query = f"'{repo_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
            folders = self.service.files().list(
                q=query, fields="files(id, name)"
            ).execute().get('files', [])
            
            objects_folder_id = None
            refs_folder_id = None
            
            for folder in folders:
                if folder['name'] == 'objects':
                    objects_folder_id = folder['id']
                elif folder['name'] == 'refs':
                    refs_folder_id = folder['id']
            
            # Descargar archivos de configuración
            query = f"'{repo_id}' in parents and mimeType != 'application/vnd.google-apps.folder'"
            files = self.service.files().list(
                q=query, fields="files(id, name)"
            ).execute().get('files', [])
            
            for file in files:
                if file['name'] in ['config.json', 'index.json']:
                    self._download_file(file['id'], vcs_dir / file['name'])
            
            # Guardar configuración de Drive
            drive_config = {
                'repo_name': repo_name,
                'repo_id': repo_id,
                'objects_folder_id': objects_folder_id,
                'refs_folder_id': refs_folder_id,
                'last_sync': None
            }
            
            with open(vcs_dir / 'drive_config.json', 'w', encoding='utf-8') as f:
                json.dump(drive_config, f, indent=2)
            
            print(f"Repositorio '{repo_name}' clonado desde Google Drive a {local_repo}")
            return local_repo
            
        except Exception as e:
            print(f"Error al clonar repositorio: {e}")
            return None
    
    def push(self, branch='master'):
        """Sube cambios locales a Google Drive."""
        try:
            # Cargar configuración
            self._load_drive_config()
            if not self.drive_config:
                print("No hay repositorio remoto configurado. Use init_remote primero.")
                return False
            
            self.authenticate()
            
            # Cargar el índice local
            index_path = self.vcs_dir / 'index.json'
            if not index_path.exists():
                print("No hay índice local.")
                return False
            
            with open(index_path, 'r', encoding='utf-8') as f:
                local_index = json.load(f)
            
            # Verificar si existe el índice remoto y descargarlo
            remote_index = self._get_remote_index()
            
            # Sincronizar objetos (archivos versionados)
            self._sync_objects()
            
            # Actualizar rama actual
            branch_path = self.vcs_dir / 'refs' / branch
            if branch_path.exists():
                self._upload_refs(branch)
            
            # Subir el índice actualizado
            self._upload_file(
                index_path,
                'index.json',
                self.drive_config['repo_id'],
                'application/json'
            )
            
            # Actualizar última sincronización
            self.drive_config['last_sync'] = str(time.time())
            self._save_drive_config()
            
            print(f"Cambios de la rama '{branch}' enviados a Google Drive.")
            return True
            
        except Exception as e:
            print(f"Error al enviar cambios: {e}")
            return False
    
    def pull(self, branch='master'):
        """Obtiene cambios desde Google Drive."""
        try:
            # Cargar configuración
            self._load_drive_config()
            if not self.drive_config:
                print("No hay repositorio remoto configurado. Use init_remote o clone primero.")
                return False
            
            self.authenticate()
            
            # Descargar el índice remoto
            index_id = self._find_file_by_name('index.json', self.drive_config['repo_id'])
            if not index_id:
                print("No se encontró el índice remoto.")
                return False
            
            self._download_file(index_id, self.vcs_dir / 'index.json')
            
            # Descargar los objetos necesarios
            self._sync_objects(download_only=True)
            
            # Descargar las referencias de ramas
            self._download_refs(branch)
            
            # Actualizar última sincronización
            self.drive_config['last_sync'] = str(time.time())
            self._save_drive_config()
            
            print(f"Cambios de la rama '{branch}' obtenidos desde Google Drive.")
            return True
            
        except Exception as e:
            print(f"Error al obtener cambios: {e}")
            return False
    
    def share(self, email, role='writer'):
        """Comparte el repositorio con otro usuario."""
        try:
            self._load_drive_config()
            if not self.drive_config or 'repo_id' not in self.drive_config:
                print("No hay repositorio remoto configurado.")
                return False
            
            self.authenticate()
            
            # Roles disponibles: 'reader', 'writer', 'commenter'
            valid_roles = ['reader', 'writer', 'commenter']
            if role not in valid_roles:
                print(f"Rol inválido. Debe ser uno de: {', '.join(valid_roles)}")
                return False
            
            # Crear permiso
            user_permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            self.service.permissions().create(
                fileId=self.drive_config['repo_id'],
                body=user_permission,
                sendNotificationEmail=True
            ).execute()
            
            print(f"Repositorio compartido con {email} (rol: {role}).")
            return True
            
        except Exception as e:
            print(f"Error al compartir repositorio: {e}")
            return False
    
    def _create_folder(self, folder_name, parent_id):
        """Crea una carpeta en Google Drive."""
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        
        folder = self.service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        
        return folder.get('id')
    
    def _upload_file(self, local_path, file_name, parent_id, mime_type=None):
        """Sube un archivo a Google Drive."""
        if not mime_type:
            mime_type = 'application/octet-stream'
            
        file_metadata = {
            'name': file_name,
            'parents': [parent_id]
        }
        
        # Verificar si el archivo ya existe
        existing_file_id = self._find_file_by_name(file_name, parent_id)
        
        media = MediaFileUpload(local_path, mimetype=mime_type)
        
        if existing_file_id:
            # Actualizar archivo existente
            file = self.service.files().update(
                fileId=existing_file_id,
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        else:
            # Crear nuevo archivo
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        
        return file.get('id')
    
    def _find_file_by_name(self, file_name, parent_id):
        """Busca un archivo por nombre en una carpeta específica."""
        query = f"name = '{file_name}' and '{parent_id}' in parents and trashed = false"
        
        results = self.service.files().list(
            q=query,
            fields="files(id)"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            return None
        
        return files[0]['id']
    
    def _download_file(self, file_id, local_path):
        """Descarga un archivo desde Google Drive."""
        request = self.service.files().get_media(fileId=file_id)
        
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        with io.FileIO(local_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
    
    def _get_remote_index(self):
        """Obtiene el índice remoto si existe."""
        index_id = self._find_file_by_name('index.json', self.drive_config['repo_id'])
        if not index_id:
            return {}
        
        temp_path = self.vcs_dir / 'temp_index.json'
        self._download_file(index_id, temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            remote_index = json.load(f)
        
        # Eliminar archivo temporal
        temp_path.unlink()
        
        return remote_index
    
    def _sync_objects(self, download_only=False):
        """Sincroniza los objetos entre local y remoto."""
        # Obtener lista de objetos locales
        objects_dir = self.vcs_dir / 'objects'
        local_objects = []
        
        if objects_dir.exists():
            for prefix_dir in objects_dir.iterdir():
                if prefix_dir.is_dir():
                    for obj_file in prefix_dir.iterdir():
                        if obj_file.is_file():
                            local_objects.append(prefix_dir.name + obj_file.name)
        
        # Obtener lista de objetos remotos
        remote_objects = []
        query = f"'{self.drive_config['objects_folder_id']}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        
        for file in results.get('files', []):
            remote_objects.append(file['name'])
        
        if not download_only:
            # Subir objetos locales que no están en remoto
            for obj_hash in local_objects:
                if obj_hash not in remote_objects:
                    prefix = obj_hash[:2]
                    suffix = obj_hash[2:]
                    
                    local_path = objects_dir / prefix / suffix
                    
                    self._upload_file(
                        local_path,
                        obj_hash,
                        self.drive_config['objects_folder_id']
                    )
        
        # Descargar objetos remotos que no están en local
        for obj_hash in remote_objects:
            if obj_hash not in local_objects:
                prefix = obj_hash[:2]
                suffix = obj_hash[2:]
                
                remote_id = self._find_file_by_name(obj_hash, self.drive_config['objects_folder_id'])
                if remote_id:
                    local_path = objects_dir / prefix / suffix
                    objects_dir.mkdir(exist_ok=True)
                    (objects_dir / prefix).mkdir(exist_ok=True)
                    
                    self._download_file(remote_id, local_path)
    
    def _upload_refs(self, branch):
        """Sube referencias de ramas a Google Drive."""
        branch_path = self.vcs_dir / 'refs' / branch
        if not branch_path.exists():
            return
        
        # Buscar o crear carpeta de ramas en Drive
        branches_folder_id = self._find_file_by_name('branches', self.drive_config['refs_folder_id'])
        if not branches_folder_id:
            branches_folder_id = self._create_folder('branches', self.drive_config['refs_folder_id'])
        
        # Subir archivo de rama
        self._upload_file(
            branch_path,
            branch,
            branches_folder_id,
            'text/plain'
        )
    
    def _download_refs(self, branch):
        """Descarga referencias de ramas desde Google Drive."""
        # Buscar carpeta de ramas en Drive
        branches_folder_id = self._find_file_by_name('branches', self.drive_config['refs_folder_id'])
        if not branches_folder_id:
            return
        
        # Buscar archivo de rama específica
        branch_id = self._find_file_by_name(branch, branches_folder_id)
        if branch_id:
            branch_path = self.vcs_dir / 'refs' / branch
            (self.vcs_dir / 'refs').mkdir(exist_ok=True)
            
            self._download_file(branch_id, branch_path)
    
    def _save_drive_config(self):
        """Guarda la configuración de Drive en el repositorio local."""
        self.vcs_dir.mkdir(exist_ok=True)
        with open(self.drive_config_file, 'w', encoding='utf-8') as f:
            json.dump(self.drive_config, f, indent=2)
    
    def _load_drive_config(self):
        """Carga la configuración de Drive desde el repositorio local."""
        if self.drive_config_file.exists():
            with open(self.drive_config_file, 'r', encoding='utf-8') as f:
                self.drive_config = json.load(f)
        else:
            self.drive_config = {}