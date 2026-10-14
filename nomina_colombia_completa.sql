-- SISTEMA DE NOMINA COLOMBIA - PostgreSQL 15+
-- Instalacion inicial en una base de datos vacia.
-- No ejecutar nuevamente sobre datos productivos sin plan de migracion.
BEGIN;
CREATE SCHEMA IF NOT EXISTS nomina;
SET search_path TO nomina, public;

-- 1. EMPRESA Y SEGURIDAD
CREATE TABLE empresas (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 nit VARCHAR(30) NOT NULL UNIQUE, razon_social VARCHAR(200) NOT NULL,
 direccion TEXT, telefono VARCHAR(30), correo VARCHAR(150), activa BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE sedes (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT NOT NULL REFERENCES empresas(id), nombre VARCHAR(120) NOT NULL,
 direccion TEXT, UNIQUE(empresa_id,nombre)
);
CREATE TABLE centros_costo (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT NOT NULL REFERENCES empresas(id), codigo VARCHAR(30) NOT NULL,
 nombre VARCHAR(120) NOT NULL, activo BOOLEAN NOT NULL DEFAULT TRUE,
 UNIQUE(empresa_id,codigo)
);
CREATE TABLE roles (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, codigo VARCHAR(40) NOT NULL UNIQUE,
 descripcion VARCHAR(200)
);
CREATE TABLE usuarios (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT REFERENCES empresas(id), correo VARCHAR(150) NOT NULL UNIQUE,
 hash_password TEXT NOT NULL, activo BOOLEAN NOT NULL DEFAULT TRUE,
 creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE usuarios_roles (
 usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
 rol_id BIGINT NOT NULL REFERENCES roles(id), PRIMARY KEY(usuario_id,rol_id)
);
CREATE TABLE auditoria (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 usuario_id BIGINT REFERENCES usuarios(id), tabla VARCHAR(100) NOT NULL,
 registro_id BIGINT, accion VARCHAR(20) NOT NULL,
 antes JSONB, despues JSONB, creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. CONFIGURACION: PARAMETROS Y TARIFAS POR VIGENCIA
CREATE TABLE parametros_nomina (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT REFERENCES empresas(id), -- NULL = parametro nacional
 codigo VARCHAR(60) NOT NULL, descripcion VARCHAR(220) NOT NULL,
 valor NUMERIC(18,5) NOT NULL,
 vigente_desde DATE NOT NULL, vigente_hasta DATE,
 fuente_normativa TEXT, creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK(vigente_hasta IS NULL OR vigente_hasta>=vigente_desde)
);
CREATE UNIQUE INDEX uq_parametros_nacional ON parametros_nomina(codigo,vigente_desde)
 WHERE empresa_id IS NULL;
CREATE UNIQUE INDEX uq_parametros_empresa ON parametros_nomina(empresa_id,codigo,vigente_desde)
 WHERE empresa_id IS NOT NULL;

CREATE TABLE tipos_recargo (
 codigo VARCHAR(20) PRIMARY KEY, nombre VARCHAR(120) NOT NULL,
 descripcion TEXT,
 -- ADICIONAL: ya se remunera la hora base / COMPLETO: se paga base + recargo
 modo_pago VARCHAR(12) NOT NULL CHECK(modo_pago IN ('ADICIONAL','COMPLETO')),
 activo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE tarifas_recargo (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT REFERENCES empresas(id), -- NULL = tarifa nacional
 tipo_codigo VARCHAR(20) NOT NULL REFERENCES tipos_recargo(codigo),
 porcentaje NUMERIC(8,4) NOT NULL CHECK(porcentaje>=0),
 vigente_desde DATE NOT NULL, vigente_hasta DATE,
 fuente_normativa TEXT,
 CHECK(vigente_hasta IS NULL OR vigente_hasta>=vigente_desde)
);
CREATE UNIQUE INDEX uq_tarifa_nacional ON tarifas_recargo(tipo_codigo,vigente_desde)
 WHERE empresa_id IS NULL;
CREATE UNIQUE INDEX uq_tarifa_empresa ON tarifas_recargo(empresa_id,tipo_codigo,vigente_desde)
 WHERE empresa_id IS NOT NULL;

-- Bloquea solapamiento temporal para el mismo parametro/empresa.
CREATE OR REPLACE FUNCTION validar_vigencias() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE existe BOOLEAN;
BEGIN
 IF TG_TABLE_NAME='parametros_nomina' THEN
  SELECT EXISTS(SELECT 1 FROM parametros_nomina p WHERE p.id<>NEW.id
    AND p.empresa_id IS NOT DISTINCT FROM NEW.empresa_id AND p.codigo=NEW.codigo
    AND daterange(p.vigente_desde,p.vigente_hasta,'[]') &&
        daterange(NEW.vigente_desde,NEW.vigente_hasta,'[]')) INTO existe;
 ELSE
  SELECT EXISTS(SELECT 1 FROM tarifas_recargo t WHERE t.id<>NEW.id
    AND t.empresa_id IS NOT DISTINCT FROM NEW.empresa_id AND t.tipo_codigo=NEW.tipo_codigo
    AND daterange(t.vigente_desde,t.vigente_hasta,'[]') &&
        daterange(NEW.vigente_desde,NEW.vigente_hasta,'[]')) INTO existe;
 END IF;
 IF existe THEN RAISE EXCEPTION 'Las vigencias se solapan para el mismo codigo y empresa'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trg_parametros_vigencia BEFORE INSERT OR UPDATE ON parametros_nomina
 FOR EACH ROW EXECUTE FUNCTION validar_vigencias();
CREATE TRIGGER trg_tarifas_vigencia BEFORE INSERT OR UPDATE ON tarifas_recargo
 FOR EACH ROW EXECUTE FUNCTION validar_vigencias();

-- Consulta valor vigente con prioridad a configuracion empresarial.
CREATE OR REPLACE FUNCTION parametro_vigente(p_empresa BIGINT,p_codigo TEXT,p_fecha DATE)
RETURNS NUMERIC LANGUAGE sql STABLE AS $$
 SELECT valor FROM nomina.parametros_nomina
 WHERE codigo=p_codigo AND vigente_desde<=p_fecha
 AND (vigente_hasta IS NULL OR vigente_hasta>=p_fecha)
 AND (empresa_id=p_empresa OR empresa_id IS NULL)
 ORDER BY (empresa_id IS NOT NULL) DESC, vigente_desde DESC LIMIT 1
$$;
CREATE OR REPLACE FUNCTION porcentaje_recargo(p_empresa BIGINT,p_codigo TEXT,p_fecha DATE)
RETURNS NUMERIC LANGUAGE sql STABLE AS $$
 SELECT porcentaje FROM nomina.tarifas_recargo
 WHERE tipo_codigo=p_codigo AND vigente_desde<=p_fecha
 AND (vigente_hasta IS NULL OR vigente_hasta>=p_fecha)
 AND (empresa_id=p_empresa OR empresa_id IS NULL)
 ORDER BY (empresa_id IS NOT NULL) DESC, vigente_desde DESC LIMIT 1
$$;

-- 3. EMPLEADOS Y CONTRATOS
CREATE TABLE empleados (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT NOT NULL REFERENCES empresas(id),
 tipo_documento VARCHAR(10) NOT NULL,
 numero_documento VARCHAR(30) NOT NULL,
 nombres VARCHAR(100) NOT NULL, apellidos VARCHAR(100) NOT NULL,
 fecha_nacimiento DATE, telefono VARCHAR(30), correo VARCHAR(150), direccion TEXT,
 contacto_emergencia VARCHAR(150), telefono_emergencia VARCHAR(30),
 banco VARCHAR(120), tipo_cuenta VARCHAR(25), numero_cuenta VARCHAR(60),
 eps VARCHAR(120), fondo_pension VARCHAR(120), fondo_cesantias VARCHAR(120),
 arl VARCHAR(120), caja_compensacion VARCHAR(120),
 estado VARCHAR(15) NOT NULL DEFAULT 'ACTIVO' CHECK(estado IN ('ACTIVO','INACTIVO')),
 creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(empresa_id,tipo_documento,numero_documento)
);
CREATE TABLE contratos (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empleado_id BIGINT NOT NULL REFERENCES empleados(id),
 sede_id BIGINT REFERENCES sedes(id), centro_costo_id BIGINT REFERENCES centros_costo(id),
 tipo_contrato VARCHAR(30) NOT NULL CHECK(tipo_contrato IN
  ('INDEFINIDO','FIJO','OBRA_LABOR','APRENDIZAJE','OTRO')),
 cargo VARCHAR(140) NOT NULL, fecha_inicio DATE NOT NULL, fecha_fin DATE,
 salario_mensual NUMERIC(15,2) NOT NULL CHECK(salario_mensual>=0),
 horas_semanales NUMERIC(6,2) NOT NULL CHECK(horas_semanales>0),
 dia_descanso SMALLINT NOT NULL DEFAULT 7 CHECK(dia_descanso BETWEEN 1 AND 7),
 tiene_auxilio_transporte BOOLEAN NOT NULL DEFAULT TRUE,
 estado VARCHAR(15) NOT NULL DEFAULT 'ACTIVO' CHECK(estado IN ('ACTIVO','TERMINADO')),
 CHECK(fecha_fin IS NULL OR fecha_fin>=fecha_inicio)
);
CREATE TABLE historial_salarios (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 vigente_desde DATE NOT NULL, salario_mensual NUMERIC(15,2) NOT NULL CHECK(salario_mensual>=0),
 observacion TEXT, UNIQUE(contrato_id,vigente_desde)
);
CREATE TABLE horarios (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT NOT NULL REFERENCES empresas(id), nombre VARCHAR(120) NOT NULL,
 hora_entrada TIME NOT NULL, hora_salida TIME NOT NULL,
 minutos_descanso INTEGER NOT NULL DEFAULT 0 CHECK(minutos_descanso>=0)
);
CREATE TABLE asignaciones_horario (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id), horario_id BIGINT NOT NULL REFERENCES horarios(id),
 vigente_desde DATE NOT NULL, vigente_hasta DATE,
 CHECK(vigente_hasta IS NULL OR vigente_hasta>=vigente_desde)
);

-- 4. ASISTENCIA, NOVEDADES Y HORAS EXTRAS
CREATE TABLE asistencias (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 entrada TIMESTAMPTZ NOT NULL, salida TIMESTAMPTZ,
 minutos_descanso INTEGER NOT NULL DEFAULT 0 CHECK(minutos_descanso>=0),
 estado VARCHAR(15) NOT NULL DEFAULT 'REGISTRADA'
   CHECK(estado IN ('REGISTRADA','VALIDADA','ANULADA')),
 observacion TEXT, CHECK(salida IS NULL OR salida>entrada)
);
CREATE TABLE horas_extras (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 asistencia_id BIGINT REFERENCES asistencias(id),
 tipo_codigo VARCHAR(20) NOT NULL REFERENCES tipos_recargo(codigo),
 fecha DATE NOT NULL, cantidad_horas NUMERIC(8,3) NOT NULL CHECK(cantidad_horas>0),
 valor_hora_base NUMERIC(15,4), porcentaje_aplicado NUMERIC(8,4),
 modo_pago_aplicado VARCHAR(12) CHECK(modo_pago_aplicado IN ('ADICIONAL','COMPLETO')),
 valor_calculado NUMERIC(15,2),
 estado VARCHAR(15) NOT NULL DEFAULT 'PENDIENTE'
  CHECK(estado IN ('PENDIENTE','APROBADA','RECHAZADA','LIQUIDADA')),
 aprobado_por BIGINT REFERENCES usuarios(id), observaciones TEXT
);

-- 5. INCAPACIDADES, VACACIONES Y LICENCIAS
CREATE TABLE incapacidades (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 tipo VARCHAR(30) NOT NULL CHECK(tipo IN
  ('ENFERMEDAD_GENERAL','ACCIDENTE_LABORAL','ENFERMEDAD_LABORAL',
   'MATERNIDAD','PATERNIDAD','OTRA')),
 fecha_inicio DATE NOT NULL, fecha_fin DATE NOT NULL,
 entidad_responsable VARCHAR(150), numero_certificado VARCHAR(100),
 documento_soporte_url TEXT, porcentaje_reconocimiento NUMERIC(8,4),
 valor_estimado NUMERIC(15,2), valor_reconocido NUMERIC(15,2),
 estado VARCHAR(20) NOT NULL DEFAULT 'REGISTRADA' CHECK(estado IN
   ('REGISTRADA','VALIDADA','EN_COBRO','PAGADA','RECHAZADA')),
 observaciones TEXT, CHECK(fecha_fin>=fecha_inicio)
);
CREATE TABLE vacaciones (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 fecha_inicio DATE NOT NULL, fecha_fin DATE NOT NULL, fecha_reintegro DATE,
 dias_habiles NUMERIC(8,3) NOT NULL CHECK(dias_habiles>0),
 estado VARCHAR(20) NOT NULL DEFAULT 'SOLICITADA' CHECK(estado IN
  ('SOLICITADA','APROBADA','DISFRUTADA','CANCELADA')),
 aprobada_por BIGINT REFERENCES usuarios(id), observaciones TEXT,
 CHECK(fecha_fin>=fecha_inicio)
);
CREATE TABLE movimientos_vacaciones (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 vacaciones_id BIGINT REFERENCES vacaciones(id),
 fecha DATE NOT NULL, tipo VARCHAR(20) NOT NULL CHECK(tipo IN
  ('CAUSACION','DISFRUTE','COMPENSACION','AJUSTE')),
 dias NUMERIC(10,3) NOT NULL CHECK(dias<>0),
 observacion TEXT
);
CREATE UNIQUE INDEX uq_descuento_vacacion ON movimientos_vacaciones(vacaciones_id)
 WHERE tipo='DISFRUTE' AND vacaciones_id IS NOT NULL;
CREATE TABLE licencias (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 tipo VARCHAR(30) NOT NULL, remunerada BOOLEAN NOT NULL DEFAULT FALSE,
 fecha_inicio DATE NOT NULL, fecha_fin DATE NOT NULL,
 estado VARCHAR(20) NOT NULL DEFAULT 'SOLICITADA', observaciones TEXT,
 CHECK(fecha_fin>=fecha_inicio)
);

-- 6. CONCEPTOS Y DESCUENTOS
CREATE TABLE conceptos_nomina (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 codigo VARCHAR(35) NOT NULL UNIQUE, nombre VARCHAR(150) NOT NULL,
 tipo VARCHAR(12) NOT NULL CHECK(tipo IN ('DEVENGADO','DEDUCCION')),
 constituye_salario BOOLEAN NOT NULL DEFAULT FALSE,
 integra_base_seguridad_social BOOLEAN NOT NULL DEFAULT FALSE,
 activo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE deducciones_empleado (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 concepto_id BIGINT NOT NULL REFERENCES conceptos_nomina(id),
 descripcion TEXT, monto_original NUMERIC(15,2), saldo_pendiente NUMERIC(15,2),
 valor_cuota NUMERIC(15,2) NOT NULL CHECK(valor_cuota>0),
 vigente_desde DATE NOT NULL, vigente_hasta DATE,
 periodicidad VARCHAR(20) NOT NULL DEFAULT 'POR_PERIODO'
  CHECK(periodicidad IN ('UNICA','POR_PERIODO')),
 activa BOOLEAN NOT NULL DEFAULT TRUE,
 CHECK(vigente_hasta IS NULL OR vigente_hasta>=vigente_desde),
 CHECK(monto_original IS NULL OR monto_original>=0),
 CHECK(saldo_pendiente IS NULL OR saldo_pendiente>=0)
);

-- 7. LIQUIDACIONES
CREATE TABLE periodos_nomina (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 empresa_id BIGINT NOT NULL REFERENCES empresas(id),
 tipo VARCHAR(15) NOT NULL CHECK(tipo IN ('SEMANAL','QUINCENAL','MENSUAL')),
 fecha_inicio DATE NOT NULL, fecha_fin DATE NOT NULL, fecha_pago DATE NOT NULL,
 estado VARCHAR(15) NOT NULL DEFAULT 'ABIERTO'
  CHECK(estado IN ('ABIERTO','EN_REVISION','CERRADO')),
 CHECK(fecha_fin>=fecha_inicio),
 UNIQUE(empresa_id,tipo,fecha_inicio,fecha_fin)
);
CREATE TABLE nominas (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 contrato_id BIGINT NOT NULL REFERENCES contratos(id),
 periodo_id BIGINT NOT NULL REFERENCES periodos_nomina(id),
 salario_referencia NUMERIC(15,2) NOT NULL DEFAULT 0,
 total_devengado NUMERIC(15,2) NOT NULL DEFAULT 0,
 total_deducciones NUMERIC(15,2) NOT NULL DEFAULT 0,
 neto_pagar NUMERIC(15,2) GENERATED ALWAYS AS
  (total_devengado-total_deducciones) STORED,
 estado VARCHAR(15) NOT NULL DEFAULT 'BORRADOR' CHECK(estado IN
  ('BORRADOR','APROBADA','PAGADA','ANULADA')),
 fecha_liquidacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 aprobada_por BIGINT REFERENCES usuarios(id), observaciones TEXT,
 UNIQUE(contrato_id,periodo_id)
);
CREATE TABLE detalles_nomina (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 nomina_id BIGINT NOT NULL REFERENCES nominas(id),
 concepto_id BIGINT NOT NULL REFERENCES conceptos_nomina(id),
 cantidad NUMERIC(12,3), valor_unitario NUMERIC(15,4),
 porcentaje_aplicado NUMERIC(8,4), valor NUMERIC(15,2) NOT NULL CHECK(valor>=0),
 origen_tipo VARCHAR(30), origen_id BIGINT, descripcion TEXT
);
CREATE TABLE pagos_nomina (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 nomina_id BIGINT NOT NULL REFERENCES nominas(id), fecha_pago DATE NOT NULL,
 valor NUMERIC(15,2) NOT NULL CHECK(valor>0),
 medio VARCHAR(20) NOT NULL CHECK(medio IN ('TRANSFERENCIA','EFECTIVO','CHEQUE','OTRO')),
 referencia VARCHAR(100), observaciones TEXT
);

-- Calcular totales desde el detalle, sin confiar en lo enviado por el cliente.
CREATE OR REPLACE FUNCTION actualizar_totales_nomina(p_nomina BIGINT) RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
 UPDATE nominas n SET
  total_devengado=COALESCE((SELECT SUM(d.valor) FROM detalles_nomina d
     JOIN conceptos_nomina c ON c.id=d.concepto_id
     WHERE d.nomina_id=p_nomina AND c.tipo='DEVENGADO'),0),
  total_deducciones=COALESCE((SELECT SUM(d.valor) FROM detalles_nomina d
     JOIN conceptos_nomina c ON c.id=d.concepto_id
     WHERE d.nomina_id=p_nomina AND c.tipo='DEDUCCION'),0)
 WHERE n.id=p_nomina;
END $$;
CREATE OR REPLACE FUNCTION detalle_nomina_recalcular() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='INSERT' THEN PERFORM actualizar_totales_nomina(NEW.nomina_id);
 ELSIF TG_OP='DELETE' THEN PERFORM actualizar_totales_nomina(OLD.nomina_id);
 ELSE
  PERFORM actualizar_totales_nomina(NEW.nomina_id);
  IF OLD.nomina_id<>NEW.nomina_id THEN PERFORM actualizar_totales_nomina(OLD.nomina_id); END IF;
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER trg_detalle_totales AFTER INSERT OR UPDATE OR DELETE ON detalles_nomina
 FOR EACH ROW EXECUTE FUNCTION detalle_nomina_recalcular();
CREATE OR REPLACE FUNCTION bloquear_detalle_cerrado() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_id BIGINT; v_estado TEXT;
BEGIN
 IF TG_OP IN ('UPDATE','DELETE') THEN
  SELECT estado INTO v_estado FROM nominas WHERE id=OLD.nomina_id FOR UPDATE;
  IF v_estado<>'BORRADOR' THEN RAISE EXCEPTION 'No se puede modificar el detalle de una nomina %',v_estado; END IF;
 END IF;
 IF TG_OP IN ('INSERT','UPDATE') THEN
  SELECT estado INTO v_estado FROM nominas WHERE id=NEW.nomina_id FOR UPDATE;
  IF v_estado<>'BORRADOR' THEN RAISE EXCEPTION 'No se puede modificar el detalle de una nomina %',v_estado; END IF;
 END IF;
 RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER trg_bloquear_detalle BEFORE INSERT OR UPDATE OR DELETE ON detalles_nomina
 FOR EACH ROW EXECUTE FUNCTION bloquear_detalle_cerrado();

-- 8. FESTIVOS (SE ALIMENTAN POR ANO SEGUN CALENDARIO OFICIAL)
CREATE TABLE festivos (
 fecha DATE PRIMARY KEY, nombre VARCHAR(150) NOT NULL,
 observaciones TEXT
);

-- 9. INDICES
CREATE INDEX idx_contratos_empleado ON contratos(empleado_id);
CREATE INDEX idx_salarios_contrato_fecha ON historial_salarios(contrato_id,vigente_desde DESC);
CREATE INDEX idx_asistencia_contrato ON asistencias(contrato_id,entrada);
CREATE INDEX idx_extras_contrato_fecha ON horas_extras(contrato_id,fecha,estado);
CREATE INDEX idx_incapacidades_contrato ON incapacidades(contrato_id,fecha_inicio,fecha_fin);
CREATE INDEX idx_vacaciones_contrato ON vacaciones(contrato_id,fecha_inicio,fecha_fin);
CREATE INDEX idx_mov_vacaciones_contrato ON movimientos_vacaciones(contrato_id,fecha);
CREATE INDEX idx_nominas_periodo ON nominas(periodo_id);
CREATE INDEX idx_detalles_nomina ON detalles_nomina(nomina_id);
CREATE INDEX idx_parametros_busqueda ON parametros_nomina(codigo,vigente_desde DESC);
CREATE INDEX idx_tarifas_busqueda ON tarifas_recargo(tipo_codigo,vigente_desde DESC);

-- 10. SEMILLAS DE CONFIGURACION Y CATALOGO
INSERT INTO roles(codigo,descripcion) VALUES
 ('ADMIN','Administrador'),('NOMINA','Gestion de nomina'),
 ('RRHH','Recursos humanos'),('CONSULTA','Solo lectura');
INSERT INTO conceptos_nomina(codigo,nombre,tipo,constituye_salario,integra_base_seguridad_social) VALUES
 ('SALARIO','Salario basico','DEVENGADO',TRUE,TRUE),
 ('AUX_TRANSPORTE','Auxilio de transporte','DEVENGADO',FALSE,FALSE),
 ('HED','Hora extra diurna','DEVENGADO',TRUE,TRUE),
 ('HEN','Hora extra nocturna','DEVENGADO',TRUE,TRUE),
 ('RN','Recargo nocturno','DEVENGADO',TRUE,TRUE),
 ('RDD','Recargo descanso obligatorio diurno','DEVENGADO',TRUE,TRUE),
 ('RDN','Recargo descanso obligatorio nocturno','DEVENGADO',TRUE,TRUE),
 ('HEDD','Hora extra descanso obligatorio diurna','DEVENGADO',TRUE,TRUE),
 ('HEDN','Hora extra descanso obligatorio nocturna','DEVENGADO',TRUE,TRUE),
 ('VACACIONES','Vacaciones','DEVENGADO',FALSE,TRUE),
 ('INCAPACIDAD','Incapacidad','DEVENGADO',FALSE,TRUE),
 ('BONIFICACION','Bonificacion','DEVENGADO',FALSE,FALSE),
 ('SALUD','Aporte salud trabajador','DEDUCCION',FALSE,FALSE),
 ('PENSION','Aporte pension trabajador','DEDUCCION',FALSE,FALSE),
 ('FSP','Fondo solidaridad pensional','DEDUCCION',FALSE,FALSE),
 ('PRESTAMO','Prestamo','DEDUCCION',FALSE,FALSE),
 ('LIBRANZA','Libranza','DEDUCCION',FALSE,FALSE),
 ('EMBARGO','Embargo judicial','DEDUCCION',FALSE,FALSE),
 ('OTRA_DEDUCCION','Otra deduccion','DEDUCCION',FALSE,FALSE);
INSERT INTO tipos_recargo(codigo,nombre,descripcion,modo_pago) VALUES
 ('HED','Hora extra diurna','Recargo sobre hora ordinaria','COMPLETO'),
 ('HEN','Hora extra nocturna','Recargo sobre hora ordinaria','COMPLETO'),
 ('RN','Recargo nocturno ordinario','Solo componente adicional','ADICIONAL'),
 ('RDD','Descanso obligatorio o festivo diurno','Solo componente adicional','ADICIONAL'),
 ('RDN','Descanso obligatorio o festivo nocturno','Suma de recargo de descanso y nocturno','ADICIONAL'),
 ('HEDD','Hora extra en descanso obligatorio diurna','Suma de recargo extra diurno y descanso','COMPLETO'),
 ('HEDN','Hora extra en descanso obligatorio nocturna','Suma de recargo extra nocturno y descanso','COMPLETO');
INSERT INTO parametros_nomina(codigo,descripcion,valor,vigente_desde,fuente_normativa) VALUES
 ('SMMLV','Salario minimo mensual 2026',1750905,'2026-02-19','Decreto 0159 de 2026; revisar efectos para periodos anteriores'),
 ('AUX_TRANSPORTE','Auxilio transporte 2026',249095,'2026-01-01','Decreto 1470 de 2025'),
 ('HORAS_SEMANALES','Jornada maxima general',42,'2026-07-15','Ley 2101 de 2021'),
 ('DIVISOR_HORA_MENSUAL','Divisor referencia de hora ordinaria para 42 horas',210,'2026-07-15','Revisar criterio juridico aplicable'),
 ('HORA_NOCTURNA_INICIO','Inicio jornada nocturna formato HHMM',1900,'2025-12-25','Ley 2466 de 2025'),
 ('HORA_NOCTURNA_FIN','Fin jornada nocturna formato HHMM',600,'2025-12-25','Ley 2466 de 2025'),
 ('APORTE_SALUD_TRABAJADOR','Porcentaje trabajador salud',4,'2026-01-01','Validar excepciones'),
 ('APORTE_PENSION_TRABAJADOR','Porcentaje trabajador pension',4,'2026-01-01','Validar excepciones'),
 ('LIMITE_AUX_TRANSPORTE_SMMLV','Tope salarial auxilio en multiplos SMMLV',2,'2026-01-01','Decreto 1470 de 2025');
INSERT INTO tarifas_recargo(tipo_codigo,porcentaje,vigente_desde,fuente_normativa) VALUES
 ('HED',25,'2026-07-01','Recargo extra diurno'),
 ('HEN',75,'2026-07-01','Recargo extra nocturno'),
 ('RN',35,'2026-07-01','Recargo ordinario nocturno'),
 ('RDD',90,'2026-07-01','Ley 2466 de 2025'),
 ('RDN',125,'2026-07-01','90 + 35; comprobar condiciones'),
 ('HEDD',115,'2026-07-01','90 + 25; comprobar condiciones'),
 ('HEDN',165,'2026-07-01','90 + 75; comprobar condiciones');
-- FUTURA VIGENCIA: cierre de tarifa previa y nuevo porcentaje
UPDATE tarifas_recargo SET vigente_hasta='2027-06-30'
 WHERE tipo_codigo IN ('RDD','RDN','HEDD','HEDN') AND vigente_desde='2026-07-01';
INSERT INTO tarifas_recargo(tipo_codigo,porcentaje,vigente_desde,fuente_normativa) VALUES
 ('RDD',100,'2027-07-01','Ley 2466 de 2025'),
 ('RDN',135,'2027-07-01','100 + 35; comprobar condiciones'),
 ('HEDD',125,'2027-07-01','100 + 25; comprobar condiciones'),
 ('HEDN',175,'2027-07-01','100 + 75; comprobar condiciones');

-- CONSULTAS Y VISTAS
CREATE VIEW vw_saldo_vacaciones AS
 SELECT c.id AS contrato_id,c.empleado_id,
 COALESCE(SUM(m.dias),0)::NUMERIC(12,3) AS dias_saldo
 FROM contratos c LEFT JOIN movimientos_vacaciones m ON m.contrato_id=c.id
 GROUP BY c.id,c.empleado_id;
CREATE VIEW vw_resumen_nomina AS
 SELECT n.id AS nomina_id, e.empresa_id,e.numero_documento,e.nombres,e.apellidos,
 p.fecha_inicio,p.fecha_fin,n.total_devengado,n.total_deducciones,n.neto_pagar,n.estado
 FROM nominas n JOIN contratos c ON c.id=n.contrato_id
 JOIN empleados e ON e.id=c.empleado_id JOIN periodos_nomina p ON p.id=n.periodo_id;
COMMIT;

-- EJEMPLOS DE CONSULTA (descomentar segun necesidad):
-- SELECT nomina.parametro_vigente(NULL,'SMMLV',DATE '2026-10-14');
-- SELECT nomina.porcentaje_recargo(NULL,'HED',DATE '2026-10-14');
-- SELECT * FROM nomina.vw_saldo_vacaciones;
-- SELECT * FROM nomina.vw_resumen_nomina;
