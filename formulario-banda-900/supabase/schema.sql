-- =========================================================================
-- Esquema para el MVP de solicitudes banda 900 MHz (ANE)
-- Ejecutar completo en Supabase -> SQL Editor -> New query -> Run
-- =========================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Tipos enumerados
-- ---------------------------------------------------------------------
do $$ begin
  create type origen_estacion as enum ('comunidad', 'red');
exception when duplicate_object then null; end $$;

do $$ begin
  create type tipo_estacion_enum as enum ('nueva', 'repetidora');
exception when duplicate_object then null; end $$;

do $$ begin
  create type formato_coord as enum ('decimal', 'gms');
exception when duplicate_object then null; end $$;

do $$ begin
  create type fuente_carga_enum as enum ('manual', 'archivo', 'formulario_comunidad');
exception when duplicate_object then null; end $$;

do $$ begin
  create type estado_solicitud_enum as enum ('pendiente', 'en_revision', 'viable', 'no_viable');
exception when duplicate_object then null; end $$;

do $$ begin
  create type rol_usuario_enum as enum ('administrador', 'ingeniero_gie');
exception when duplicate_object then null; end $$;

do $$ begin
  create type tipo_archivo_enum as enum ('csv', 'xlsx');
exception when duplicate_object then null; end $$;

do $$ begin
  create type estado_carga_enum as enum ('pendiente', 'procesado', 'error_parcial', 'error');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- solicitudes (RF01)
-- ---------------------------------------------------------------------
create table if not exists solicitudes (
    id serial primary key,
    razon_social text not null,
    nit text not null,
    representante_legal text not null,
    telefono text not null,
    direccion varchar(43) not null,
    correo_electronico text not null,
    radicado_mintic text,
    estado text not null default 'pendiente',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- perfiles: extiende auth.users con el rol de la persona (RNF04)
-- ---------------------------------------------------------------------
create table if not exists perfiles (
    id uuid primary key references auth.users(id) on delete cascade,
    nombre text,
    rol text not null default 'ingeniero_gie',
    created_at timestamptz not null default now()
);

-- crea automaticamente un perfil cuando se registra un usuario en Supabase Auth
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.perfiles (id, nombre, rol)
  values (new.id, new.email, 'ingeniero_gie')
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ---------------------------------------------------------------------
-- estaciones (RF01 y RF02)
-- ---------------------------------------------------------------------
create table if not exists estaciones (
    id serial primary key,
    origen text not null,
    solicitud_id integer references solicitudes(id) on delete cascade,
    tipo_estacion text,
    latitud numeric(10,6) not null,
    longitud numeric(10,6) not null,
    formato_coordenadas text not null default 'decimal',
    direccion_estacion text,
    departamento text,
    municipio text,
    cantidad_sectores integer not null default 1,
    haat_m numeric,
    fuente_carga text not null default 'manual',
    creado_por uuid references perfiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_origen check (origen in ('comunidad','red')),
    constraint chk_solicitud_si_comunidad check (
        (origen = 'comunidad' and solicitud_id is not null) or (origen = 'red')
    )
);

-- ---------------------------------------------------------------------
-- sectores
-- ---------------------------------------------------------------------
create table if not exists sectores (
    id serial primary key,
    estacion_id integer not null references estaciones(id) on delete cascade,
    numero_sector integer not null
);

-- ---------------------------------------------------------------------
-- antenas: aqui viven los 5 rangos del doc "Rangos / Tooltip"
-- ---------------------------------------------------------------------
create table if not exists antenas (
    id serial primary key,
    sector_id integer not null references sectores(id) on delete cascade,
    acimut numeric not null check (acimut >= 0 and acimut <= 359),
    tilt numeric not null check (tilt >= -40 and tilt <= 10),
    ganancia numeric not null check (ganancia >= 0 and ganancia <= 30),
    ganancia_unidad text check (ganancia_unidad in ('dBi','dBd')),
    angulo_apertura numeric not null check (angulo_apertura > 0 and angulo_apertura <= 360),
    altura_suelo numeric not null check (altura_suelo > 1 and altura_suelo <= 20),
    potencia_transmision numeric,
    created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- archivos_carga (trazabilidad de RF02, opcion b)
-- ---------------------------------------------------------------------
create table if not exists archivos_carga (
    id serial primary key,
    usuario_id uuid references perfiles(id),
    nombre_original text not null,
    ruta_storage text not null,
    tipo_archivo text not null,
    estado_procesamiento text not null default 'pendiente',
    filas_ok integer default 0,
    filas_error integer default 0,
    log_errores jsonb,
    created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Row Level Security: todas las tablas quedan bloqueadas por defecto.
-- El backend usa la SERVICE ROLE KEY, que ignora RLS, asi que no necesita
-- politicas adicionales. Esto evita que la anon key (publica, usada solo
-- para el login) pueda leer/escribir estas tablas directamente via la
-- API autogenerada de Supabase.
-- ---------------------------------------------------------------------
alter table solicitudes enable row level security;
alter table estaciones enable row level security;
alter table sectores enable row level security;
alter table antenas enable row level security;
alter table archivos_carga enable row level security;
alter table perfiles enable row level security;

drop policy if exists "usuarios ven su propio perfil" on perfiles;
create policy "usuarios ven su propio perfil"
  on perfiles for select
  using (auth.uid() = id);

-- =========================================================================
-- Despues de correr este script:
-- 1. Ve a Authentication -> Users -> Add user y crea el primer usuario
--    (correo + contrasena) para el panel /admin.
-- 2. En el SQL editor corre:
--      update perfiles set rol = 'administrador' where nombre = 'correo@ejemplo.com';
--    para marcarlo como administrador (opcional, por defecto queda ingeniero_gie).
-- 3. Ve a Storage -> New bucket -> nombre "cargas-antenas" -> Private.
--    (el backend intenta crearlo solo al arrancar, pero si falla, crealo aqui).
-- =========================================================================
