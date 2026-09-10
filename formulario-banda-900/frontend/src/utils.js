export function antenaVacia() {
  return {
    acimut: '',
    tilt: '',
    ganancia: '',
    angulo_apertura: '',
    altura_suelo: '',
  }
}

export function sectorVacio(numero) {
  return { numero_sector: numero, antenas: [antenaVacia()] }
}

export function estacionVacia() {
  return {
    latitud: '',
    longitud: '',
    formato_coordenadas: 'decimal',
    direccion_estacion: '',
    departamento: '',
    municipio: '',
    tipo_estacion: '',
    sectores: [sectorVacio(1)],
  }
}

export function prepararEstacionParaEnvio(estacion) {
  return {
    latitud: Number(estacion.latitud),
    longitud: Number(estacion.longitud),
    formato_coordenadas: estacion.formato_coordenadas,
    direccion_estacion: estacion.direccion_estacion || null,
    departamento: estacion.departamento || null,
    municipio: estacion.municipio || null,
    tipo_estacion: estacion.tipo_estacion || null,
    cantidad_sectores: estacion.sectores.length,
    sectores: estacion.sectores.map((s) => ({
      numero_sector: s.numero_sector,
      antenas: s.antenas.map((a) => ({
        acimut: Number(a.acimut),
        tilt: Number(a.tilt),
        ganancia: Number(a.ganancia),
        angulo_apertura: Number(a.angulo_apertura),
        altura_suelo: Number(a.altura_suelo),
      })),
    })),
  }
}
