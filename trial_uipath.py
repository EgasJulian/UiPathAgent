import requests
import socket

# --- Parámetros de configuración (reemplazar con tus valores) ---
ORGANIZATION = 'minsacsvndlb'
TENANT = 'CO_DEMO'
PAT = 'rt_BA202D4B901AD1687937668565CEE96EBDCCAA9B0A73021A69FB2AFFF59CA5FB-1'  # Personal Access Token generado en Orchestrator
PROCESS_NAME = 'RPA.Workflow'  # Nombre del proceso publicado en Orchestrator
ROBOT_NAME = "jegas@indracompany.com-unattended"
# -------------------------------------------------------------

# Construir URL base de Orchestrator Cloud
base_url = f'https://cloud.uipath.com/{ORGANIZATION}/{TENANT}/orchestrator_/odata/'

# Header con el token PAT
headers = {
    'Authorization': f'Bearer {PAT}',
    'Content-Type': 'application/json'
}

# 1. Obtener ReleaseKey del proceso
params = {"$filter": f"Name eq '{PROCESS_NAME}'"}
res = requests.get(base_url + "Releases", headers=headers, params=params)
res.raise_for_status()
releases = res.json().get("value", [])
if not releases:
    raise Exception(f"No se encontró proceso con nombre '{PROCESS_NAME}'")
release_key = releases[0]["Key"]
print(f"[OK] ReleaseKey: {release_key}")

# 2. Obtener RobotId (intentando con UserName)
robot_headers = {
    "Authorization": f"Bearer {PAT}",
    "Content-Type": "application/json",
    "X-UIPATH-OrganizationUnitId": "421017"
}
res_rb = requests.get(base_url + "Robots", headers=robot_headers)
print(res_rb.json())
# params = {"$filter": f"UserName eq 'jegas@indracompany.com'"}
# res = requests.get(base_url + "Robots", headers=robot_headers, params=params)
# res.raise_for_status()
# robots = res.json().get("value", [])
# if not robots:
#     raise Exception("No se encontró robot con UserName = jegas@indracompany.com")
# robot_id = robots[0]["Id"]
# print(f"[OK] RobotId: {robot_id}")

jobs_url = f"{base_url}/Jobs?$top=1&$orderby=CreationTime desc"
resp = requests.get(jobs_url, headers=robot_headers)
resp.raise_for_status()
jobs = resp.json()

if not jobs.get("value"):
    raise Exception("No se encontraron Jobs recientes, corre uno manual desde la UI primero.")

last_job = jobs["value"][0]
# robot_id = last_job["Robot"]["Id"]
# print(f"[OK] Último RobotId encontrado: {last_job}")

# 3. Iniciar Job en ese robot específico
start_job_url = base_url + "Jobs/UiPath.Server.Configuration.OData.StartJobs"
data = {
    "startInfo": {
        "ReleaseKey": release_key,
        "Strategy": "ModernJobsCount",
        "RuntimeType": "Development", 
        "JobsCount": 1,
        "Source": "Manual",      # obligatorio en Cloud
        "InputArguments": "{\"InCorreo\": \"jegas@indracompany.com\"}",   # obligatorio aunque esté vacío
        "JobPriority": "Normal"
    }
}

res = requests.post(start_job_url, headers=robot_headers, json=data)
res.raise_for_status()
job_info = res.json()

print("[OK] Job iniciado:")
print(job_info)