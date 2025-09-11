import requests
import json

def ejecutar_robot_uipath(personal_access_token, folder_name, process_name, input_args=None):
    """
    Ejecuta un proceso de UiPath usando Personal Access Token
    
    Args:
        personal_access_token: Tu token personal de UiPath
        folder_name: Nombre de la carpeta (ej: "NovaIA Agent")
        process_name: Nombre exacto del proceso
        input_args: Diccionario con argumentos de entrada (opcional)
    
    Returns:
        Job ID si se ejecutó correctamente, None si hubo error
    """
    
    # URL base de tu Orchestrator (basado en tu screenshot)
    base_url = "https://cloud.uipath.com/minsoft/CO_DEMO/orchestrator_"
    
    # Headers con Personal Access Token
    headers = {
        "Authorization": f"Bearer {personal_access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # 1. Obtener el Folder ID por nombre
        folders_url = f"{base_url}/odata/Folders"
        response = requests.get(folders_url, headers=headers)
        response.raise_for_status()
        
        folders = response.json()["value"]
        folder = next((f for f in folders if f["DisplayName"] == folder_name), None)
        
        if not folder:
            print(f"❌ No se encontró la carpeta '{folder_name}'")
            return None
            
        folder_id = str(folder["Id"])
        print(f"✓ Carpeta encontrada: {folder_name} (ID: {folder_id})")
        
        # Agregar el Folder ID a los headers
        headers["X-UIPATH-OrganizationUnitId"] = folder_id
        
        # 2. Obtener Release Key del proceso
        releases_url = f"{base_url}/odata/Releases"
        params = {"$filter": f"ProcessKey eq '{process_name}'"}
        
        response = requests.get(releases_url, headers=headers, params=params)
        response.raise_for_status()
        
        releases = response.json()["value"]
        if not releases:
            print(f"❌ No se encontró el proceso '{process_name}' en la carpeta '{folder_name}'")
            return None
            
        release_key = releases[0]["Key"]
        print(f"✓ Proceso encontrado: {process_name}")
        
        # 3. Iniciar el Job
        start_job_url = f"{base_url}/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        
        job_payload = {
            "startInfo": {
                "ReleaseKey": release_key,
                "Strategy": "ModernJobsCount",
                "JobsCount": 1,
                "Source": "Manual"
            }
        }
        
        # Agregar argumentos si existen
        if input_args:
            job_payload["startInfo"]["InputArguments"] = json.dumps(input_args)
        
        response = requests.post(start_job_url, headers=headers, json=job_payload)
        response.raise_for_status()
        
        job_data = response.json()["value"][0]
        job_id = job_data["Id"]
        
        print(f"✅ Proceso iniciado exitosamente!")
        print(f"   Job ID: {job_id}")
        print(f"   Estado: {job_data.get('State', 'Running')}")
        
        return job_id
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error HTTP: {e}")
        if e.response:
            print(f"   Detalles: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


def verificar_estado_job(personal_access_token, job_id, folder_id=None):
    """
    Verifica el estado de un job en ejecución
    """
    base_url = "https://cloud.uipath.com/minsoft/CO_DEMO/orchestrator_"
    
    headers = {
        "Authorization": f"Bearer {personal_access_token}",
        "Content-Type": "application/json"
    }
    
    if folder_id:
        headers["X-UIPATH-OrganizationUnitId"] = str(folder_id)
    
    url = f"{base_url}/odata/Jobs({job_id})"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        job_info = response.json()
        estado = job_info.get("State")
        
        print(f"📊 Estado del Job {job_id}: {estado}")
        
        if estado == "Successful":
            print("   ✅ Completado exitosamente")
            if job_info.get("OutputArguments"):
                print(f"   📤 Output: {job_info['OutputArguments']}")
        elif estado == "Faulted":
            print(f"   ❌ Error: {job_info.get('Info', 'Sin detalles')}")
        elif estado in ["Running", "Pending"]:
            print("   ⏳ En progreso...")
            
        return job_info
        
    except Exception as e:
        print(f"❌ Error verificando estado: {str(e)}")
        return None


# ============================================
# EJEMPLO DE USO CON TU CONFIGURACIÓN
# ============================================

if __name__ == "__main__":
    
    # Tu configuración
    PERSONAL_ACCESS_TOKEN = "rt_4895A464AEE32CA8DCB0D227E303B6441E83632296DCBD4D9ABBA79C7C8C7E2E-1"  # El token que acabas de crear
    FOLDER_NAME = "Shared"  # Lo veo en tu screenshot
    PROCESS_NAME = "RPA.Workflow"  # Reemplaza con el nombre exacto de tu proceso
    
    print("="*50)
    print("🤖 EJECUTOR DE PROCESOS UIPATH")
    print("="*50)
    
    # Ejemplo 1: Ejecutar sin argumentos
    print("\n📌 Ejecutando proceso sin argumentos...")
    job_id = ejecutar_robot_uipath(
        personal_access_token=PERSONAL_ACCESS_TOKEN,
        folder_name=FOLDER_NAME,
        process_name=PROCESS_NAME
    )
    
    # Ejemplo 2: Ejecutar con argumentos de entrada
    # print("\n📌 Ejecutando proceso con argumentos...")
    # argumentos = {
    #     "in_NombreVariable": "valor texto",
    #     "in_NumeroVariable": 123,
    #     "in_BoolVariable": True
    # }
    # 
    # job_id = ejecutar_robot_uipath(
    #     personal_access_token=PERSONAL_ACCESS_TOKEN,
    #     folder_name=FOLDER_NAME,
    #     process_name=PROCESS_NAME,
    #     input_args=argumentos
    # )
    
    # Verificar estado (opcional)
    if job_id:
        print("\n⏳ Esperando 5 segundos antes de verificar estado...")
        import time
        time.sleep(5)
        verificar_estado_job(PERSONAL_ACCESS_TOKEN, job_id)
    
    print("\n" + "="*50)
    print("✨ Proceso completado")