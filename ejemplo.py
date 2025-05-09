#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de ejemplo para demostrar el uso de SHIT.
Este script crea un archivo binario simple y almacena múltiples versiones.
También demuestra el uso de ramas y Google Drive.
"""

import os
import struct
import random
import time
import subprocess
import click

# Ejemplo de línea añadida para probar el comando reset --soft

def crear_archivo_binario(nombre, num_datos=10):
    """Crea un archivo binario con datos aleatorios."""
    datos = [(random.randint(0, 1000), random.random()) for _ in range(num_datos)]
    
    with open(nombre, 'wb') as f:
        # Escribir cabecera
        f.write(b'BINFILE')
        f.write(struct.pack('I', num_datos))
        
        # Escribir datos
        for entero, flotante in datos:
            f.write(struct.pack('If', entero, flotante))
    
    click.echo(f"Archivo binario creado: {nombre}")
    click.echo(f"Datos almacenados: {datos}")
    return datos

def modificar_archivo_binario(nombre, cambios=2):
    """Modifica algunos valores en el archivo binario."""
    # Leer el archivo
    with open(nombre, 'rb') as f:
        cabecera = f.read(7)  # BINFILE
        num_datos = struct.unpack('I', f.read(4))[0]
        
        datos = []
        for _ in range(num_datos):
            entero, flotante = struct.unpack('If', f.read(8))
            datos.append((entero, flotante))
    
    # Modificar algunos valores aleatorios
    indices_a_cambiar = random.sample(range(num_datos), min(cambios, num_datos))
    for idx in indices_a_cambiar:
        datos[idx] = (random.randint(0, 1000), random.random())
    
    # Escribir el archivo actualizado
    with open(nombre, 'wb') as f:
        f.write(cabecera)
        f.write(struct.pack('I', num_datos))
        
        for entero, flotante in datos:
            f.write(struct.pack('If', entero, flotante))
    
    click.echo(f"Archivo binario modificado: {nombre}")
    click.echo(f"Nuevos datos: {datos}")
    return datos

def ejecutar_comando(comando):
    """Ejecuta un comando de SHIT y muestra el resultado."""
    click.echo("\n$ " + comando)
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
    click.echo(resultado.stdout)
    if resultado.stderr:
        click.echo(f"Error: {resultado.stderr}", err=True)
    return resultado.returncode == 0

def demostrar_binvcs_basico():
    """Realiza una demostración básica de SHIT."""
    # Nombre del archivo de prueba
    archivo = "datos_binarios.bin"
    
    # Inicializar repositorio
    ejecutar_comando("python shit.py init")
    
    # Crear archivo binario
    click.echo("\n=== Creando archivo binario inicial ===")
    crear_archivo_binario(archivo)
    
    # Añadir archivo al control de versiones
    ejecutar_comando(f"python shit.py add {archivo}")
    
    # Hacer primer commit
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Versión inicial del archivo binario\"")
    
    # Modificar y crear segunda versión
    click.echo("\n=== Modificando archivo (versión 2) ===")
    time.sleep(1)  # Pausa para separar timestamps
    modificar_archivo_binario(archivo)
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Segunda versión con datos actualizados\"")
    
    # Modificar y crear tercera versión
    click.echo("\n=== Modificando archivo (versión 3) ===")
    time.sleep(1)  # Pausa para separar timestamps
    modificar_archivo_binario(archivo)
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Tercera versión con más cambios\"")
    
    # Ver historial de versiones
    ejecutar_comando(f"python shit.py log {archivo}")
    
    # Recuperar primera versión
    click.echo("\n=== Recuperando versión 1 ===")
    ejecutar_comando(f"python shit.py checkout {archivo} 1")

def demostrar_ramas():
    """Realiza una demostración del uso de ramas."""
    # Nombre del archivo de prueba
    archivo = "datos_ramas.bin"
    
    # Crear archivo binario
    click.echo("\n=== Creando archivo binario para demostración de ramas ===")
    crear_archivo_binario(archivo)
    
    # Añadir archivo al control de versiones
    ejecutar_comando(f"python shit.py add {archivo}")
    
    # Commit inicial en rama master
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Versión inicial en master\"")
    
    # Crear rama de desarrollo
    click.echo("\n=== Creando rama de desarrollo ===")
    ejecutar_comando("python shit.py branch create desarrollo")
    
    # Cambiar a rama desarrollo
    ejecutar_comando("python shit.py branch switch desarrollo")
    
    # Listar ramas
    ejecutar_comando("python shit.py branch list")
    
    # Modificar archivo en rama desarrollo
    click.echo("\n=== Modificando archivo en rama desarrollo ===")
    modificar_archivo_binario(archivo, cambios=3)
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Cambios en rama desarrollo\"")
    
    # Volver a rama master
    ejecutar_comando("python shit.py branch switch master")
    
    # Modificar archivo en rama master (diferente a desarrollo)
    click.echo("\n=== Modificando archivo en rama master ===")
    modificar_archivo_binario(archivo, cambios=2)
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Cambios en rama master\"")
    
    # Ver log en ambas ramas
    click.echo("\n=== Historial en rama master ===")
    ejecutar_comando(f"python shit.py log {archivo} -b master")
    
    click.echo("\n=== Historial en rama desarrollo ===")
    ejecutar_comando(f"python shit.py log {archivo} -b desarrollo")
    
    # Fusionar rama desarrollo en master
    click.echo("\n=== Fusionando rama desarrollo en master ===")
    ejecutar_comando("python shit.py branch merge desarrollo master")
    
    # Ver log después de la fusión
    ejecutar_comando(f"python shit.py log {archivo}")

def demostrar_google_drive():
    """Realiza una demostración de la integración con Google Drive."""
    # Verificar si las credenciales están disponibles
    if not os.path.exists("credentials.json"):
        click.echo("Error: Para la demostración de Google Drive se requiere el archivo credentials.json", err=True)
        click.echo("Descárguelo desde la consola de Google Cloud y colóquelo en este directorio.")
        return False
    
    # Nombre del archivo de prueba
    archivo = "datos_drive.bin"
    
    # Crear archivo binario
    click.echo("\n=== Creando archivo binario para demostración de Google Drive ===")
    crear_archivo_binario(archivo)
    
    # Añadir archivo al control de versiones
    ejecutar_comando(f"python shit.py add {archivo}")
    
    # Commit inicial
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Versión inicial para Google Drive\"")
    
    # Inicializar repositorio remoto
    click.echo("\n=== Inicializando repositorio remoto en Google Drive ===")
    ejecutar_comando("python shit.py remote init \"Repositorio de prueba SHIT\"")
    
    # Enviar cambios al remoto
    click.echo("\n=== Enviando cambios al repositorio remoto ===")
    ejecutar_comando("python shit.py remote push")
    
    # Modificar archivo y hacer nuevo commit
    click.echo("\n=== Modificando archivo y enviando al remoto ===")
    modificar_archivo_binario(archivo)
    ejecutar_comando(f"python shit.py commit {archivo} -m \"Cambios para enviar a Google Drive\"")
    ejecutar_comando("python shit.py remote push")
    
    click.echo("\n=== Demostración de Google Drive completada ===")
    click.echo("Nota: Para una demostración completa, clone el repositorio en otro directorio usando:")
    click.echo("      python shit.py remote clone [ID_REPOSITORIO]")
    
    return True


@click.group()
def cli():
    """Demostraciones de SHIT."""
    pass


@cli.command()
def basico():
    """Ejecuta la demostración básica."""
    click.echo("\n========== DEMOSTRACIÓN BÁSICA ==========")
    demostrar_binvcs_basico()


@cli.command()
def ramas():
    """Ejecuta la demostración de ramas."""
    click.echo("\n========== DEMOSTRACIÓN DE RAMAS ==========")
    demostrar_ramas()


@cli.command()
def drive():
    """Ejecuta la demostración de Google Drive."""
    click.echo("\n========== DEMOSTRACIÓN DE GOOGLE DRIVE ==========")
    demostrar_google_drive()


@cli.command()
def todo():
    """Ejecuta todas las demostraciones."""
    basico()
    ramas()
    drive()
    
    click.echo("\n=== Demostraciones completadas ===")
    click.echo("Puede examinar el directorio .shit para ver la estructura interna.")


if __name__ == "__main__":
    cli() 