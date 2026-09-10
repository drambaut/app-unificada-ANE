# B900 — MVP formulario web ANE

Contenido del zip:

```
b900-mvp/
├── Dockerfile              # build combinado frontend+backend, lo usa Render
├── render.yaml             # blueprint de despliegue en Render
├── backend/                # FastAPI (API + validaciones)
├── frontend/                # React + Vite (formulario público y panel admin)
└── supabase/
    ├── schema.sql               # script a correr en Supabase
    └── plantilla_carga_masiva.csv  # ejemplo para probar la carga masiva
```

Ya está probado localmente: el backend arranca y responde, y `npm run build` del frontend compila sin errores. Lo que falta es conectar tus propias credenciales de Supabase y desplegar.

---

## 1. Subir el proyecto a GitHub

```bash
cd b900-mvp
git init
git add .
git commit -m "MVP formulario B900"
```

Luego en GitHub: crea un repositorio nuevo (vacío, sin README) y copia los comandos que te da GitHub para "…or push an existing repository from the command line", algo como:

```bash
git remote add origin https://github.com/TU_USUARIO/b900-mvp.git
git branch -M main
git push -u origin main
```

---

## 2. Crear el proyecto en Supabase

1. Entra a [supabase.com](https://supabase.com) → **New project**. Elige nombre, contraseña de base de datos (guárdala, la vas a necesitar) y región (idealmente la más cercana a Colombia, ej. `us-east-1`).
2. Espera a que aprovisione el proyecto (1-2 minutos).
3. Ve a **SQL Editor → New query**, pega todo el contenido de `supabase/schema.sql` y dale **Run**. Esto crea las 6 tablas (`solicitudes`, `perfiles`, `estaciones`, `sectores`, `antenas`, `archivos_carga`) con los rangos de acimut/tilt/ganancia/ángulo/altura ya validados a nivel de base de datos.
4. Ve a **Authentication → Users → Add user**. Crea el usuario que va a usar el Ingeniero GIE para entrar a `/admin` (correo + contraseña). Este es el único login del sistema; el formulario público no necesita cuenta.
5. (Opcional) En **SQL Editor** corre esto para marcarlo como administrador (por defecto queda como `ingeniero_gie`, que ya tiene acceso al panel):
   ```sql
   update perfiles set rol = 'administrador' where nombre = 'correo-que-usaste@ejemplo.com';
   ```
6. Ve a **Storage → New bucket**. Nombre: `cargas-antenas`. Marca **Private** (no público). El backend también intenta crear este bucket solo al arrancar, así que si lo olvidas no es grave.
7. Reúne las 4 credenciales que vas a necesitar en Render (todas están en **Project Settings**):
   - **Project Settings → Database → Connection string → modo "Transaction pooler"** (puerto 6543) → esto es tu `DATABASE_URL`. Reemplaza `[YOUR-PASSWORD]` por la contraseña que pusiste en el paso 1.
   - **Project Settings → API → Project URL** → `SUPABASE_URL`.
   - **Project Settings → API → anon public** → `SUPABASE_ANON_KEY`.
   - **Project Settings → API → service_role** (¡secreta, no la expongas nunca en el frontend!) → `SUPABASE_SERVICE_ROLE_KEY`.
   - **Project Settings → API → JWT Settings → JWT Secret** → `SUPABASE_JWT_SECRET`.

---

## 3. Desplegar en Render

**Opción A — con el `render.yaml` (recomendada):**

1. En [render.com](https://render.com) → **New → Blueprint**.
2. Conecta tu repo de GitHub `b900-mvp`. Render detecta `render.yaml` automáticamente y arma el servicio (Docker, plan free).
3. Antes de desplegar te va a pedir los valores de las env vars marcadas `sync: false`. Pega ahí las 5 credenciales del paso anterior.
4. Dale **Apply** / **Deploy**. El primer build tarda unos minutos (compila el frontend y la imagen de Python).

**Opción B — manual:**

1. **New → Web Service** → conecta el repo.
2. Runtime: **Docker** (Render lo detecta solo por el `Dockerfile`).
3. Plan: **Free**.
4. En **Environment**, agrega las 5 variables: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`.
5. **Create Web Service**.

Al terminar tendrás una URL como `https://b900-ane.onrender.com`:
- `/` → formulario público de las comunidades (RF01).
- `/admin` → login del Ingeniero GIE (RF02), con el correo/contraseña que creaste en Supabase.

⚠️ El plan free de Render "duerme" el servicio tras ~15 min sin tráfico y tarda ~30-50 segundos en despertar la primera vez que alguien entra. Es normal en un demo gratis; si eso molesta para las pruebas, el plan Starter lo evita.

---

## 4. Probar la carga masiva (RF02, opción b)

Dentro de `/admin` → pestaña **Carga masiva**, sube el archivo `supabase/plantilla_carga_masiva.csv` incluido en el zip. Trae 3 filas de ejemplo (2 sectores de una estación + 1 estación adicional), todas dentro de los rangos válidos, para que veas el flujo completo funcionando. Las columnas que reconoce el sistema son:

- Obligatorias: `latitud, longitud, numero_sector, acimut, tilt, ganancia, angulo_apertura, altura_suelo`
- Opcionales: `direccion_estacion, departamento, municipio, ganancia_unidad, potencia_transmision, tipo_estacion`

Si alguna fila se sale de rango, el sistema la rechaza y te dice exactamente cuál y por qué, pero sigue cargando las demás filas válidas.

---

## 5. Correrlo en tu máquina (opcional, antes de desplegar)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate   # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # y llena las 5 variables con tus credenciales de Supabase
uvicorn app.main:app --reload
```

**Frontend** (en otra terminal):
```bash
cd frontend
npm install
npm run dev
```
Abre `http://localhost:5173`. El `vite.config.js` ya tiene un proxy que manda `/api/*` a `http://localhost:8000`, así que no necesitas configurar CORS ni variables extra para desarrollo local.

---

## 6. Qué quedó fuera de este MVP

Documentado también en el plan de implementación que ya revisaste:
- RF05 (verificación de contornos) y RF06 (parametrización HAAT/PIRE/contornos): son motor de reglas de negocio, no solo captura de datos.
- Autenticación contra Active Directory de la ANE (RNF02): el login de Supabase Auth es el sustituto para este MVP.
- Generación automática de "concepto técnico" en Word/PDF (RF05).
- Cálculo real de HAAT (el campo existe en la base, pero el cálculo contra cartografía no está implementado).

Cuando quieras seguir con alguno de estos, el modelo de datos ya tiene los campos/tablas listos para no tener que rehacer nada.
