/****************************************************
 * SISTEMA PROGRAMACIÓN CC - ESTABLE + SIN UI + SIN CHOQUE VALIDACIONES
 * - Copia CC1 como plantilla (mantiene diseño)
 * - Crea una hoja por cada CC (solo renombra pestaña)
 * - Consolida a 000_CONSOLIDADO (desactiva validación solo en salida)
 ****************************************************/

const SPREADSHEET_ID = "10U4r58pYIK4Jw1t9a_YPgEE1Jw3vxnSGLPKdoCvoWz8";

const CONFIG = {
  TEMPLATE_SHEET: "CC1",
  CONSOLIDADO_SHEET: "000_CONSOLIDADO",

  DATA_START_ROW: 7,
  DATA_END_ROW: 17,
  DATA_NUM_COLS: 35, // A..AI

  // Columnas dentro del bloque (1-based)
  COL_ESPECIFICA: 7,    // G
  COL_SIGEAD: 8,        // H
  COL_TOTAL_PROG: 22,   // V (se usa como "Certificación" por defecto)
  COL_TOTAL_DEV: 32,    // AF

  THRESH_CERTIF: 0.90,
  THRESH_DEV: 0.65
};

const COST_CENTERS = [
  "0001-PI 2","0002-DCEME","0003-DE","0004-OPP","0005-JEF","0006-GG","0007-PLLA",
  "0008-OAUGD","0009-OTI","0010-OA","0011-OC","0012-OAJ","0013-OCI","0014-DETN",
  "0015-DETN","0016-DETN","0017-DCEME","0018-DCEME","0019-DE","0020-DE","0021-PI 1"
];

function getSS_() {
  const bound = SpreadsheetApp.getActiveSpreadsheet();
  if (bound) return bound;
  return SpreadsheetApp.openById(SPREADSHEET_ID);
}

/****************************************************
 * 1) CREAR HOJAS POR CENTRO DE COSTO (SIN ESCRIBIR EN CELDAS)
 ****************************************************/
function setupCostCenters() {
  const ss = getSS_();
  const tpl = ss.getSheetByName(CONFIG.TEMPLATE_SHEET);
  if (!tpl) throw new Error("No existe la hoja plantilla: " + CONFIG.TEMPLATE_SHEET);

  COST_CENTERS.forEach(cc => {
    let sh = ss.getSheetByName(cc);
    if (!sh) {
      sh = tpl.copyTo(ss).setName(cc);
    }
    // ⚠️ NO escribimos el CC en ninguna celda (evita validaciones como B7)
    // La identificación del CC será el NOMBRE DE LA PESTAÑA.
  });

  rebuildConsolidado();
}

/****************************************************
 * 2) CONSOLIDAR EN 000_CONSOLIDADO
 *    - Limpia contenidos del bloque
 *    - Quita validaciones SOLO en el bloque de salida para poder pegar sin error
 ****************************************************/
function rebuildConsolidado() {
  const ss = getSS_();
  const cons = ss.getSheetByName(CONFIG.CONSOLIDADO_SHEET);
  if (!cons) throw new Error("No existe: " + CONFIG.CONSOLIDADO_SHEET);

  const blockRows = CONFIG.DATA_END_ROW - CONFIG.DATA_START_ROW + 1;

  // Limpia contenido del bloque (mantiene formato)
  const baseRange = cons.getRange(CONFIG.DATA_START_ROW, 1, blockRows, CONFIG.DATA_NUM_COLS);
  baseRange.clearContent();

  const allRows = [];

  COST_CENTERS.forEach(cc => {
    const sh = ss.getSheetByName(cc);
    if (!sh) return;

    const values = sh.getRange(
      CONFIG.DATA_START_ROW, 1,
      blockRows, CONFIG.DATA_NUM_COLS
    ).getValues();

    // Filtra filas sin específica
    const rows = values.filter(r => String(r[CONFIG.COL_ESPECIFICA - 1] || "").trim() !== "");

    // Orden por específica
    rows.sort((a, b) => extractKey_(a[CONFIG.COL_ESPECIFICA - 1]).localeCompare(extractKey_(b[CONFIG.COL_ESPECIFICA - 1])));

    // 👇 Si quieres que el CC aparezca en el consolidado, lo ponemos en la columna A del consolidado
    // (esto no afecta hojas CC, y si A tiene validación en consolidado, la quitaremos abajo)
    rows.forEach(r => {
      r[0] = cc; // Columna A
      allRows.push(r);
    });
  });

  // Si hay más filas que el bloque, insertamos
  if (allRows.length > blockRows) {
    cons.insertRowsAfter(CONFIG.DATA_END_ROW, allRows.length - blockRows);
  }

  if (allRows.length > 0) {
    const outRange = cons.getRange(CONFIG.DATA_START_ROW, 1, allRows.length, CONFIG.DATA_NUM_COLS);

    // ✅ Para evitar el error de validación en consolidado (B7 y otras),
    // quitamos validaciones SOLO en el rango donde pegamos el consolidado.
    outRange.clearDataValidations();

    // Pegamos valores
    outRange.setValues(allRows);
  }

  // Revisa umbrales y marca con colores (solo formato, no escribe datos)
  checkAllThresholds_();
}

/****************************************************
 * 3) ALERTAS POR UMBRALES (SIN UI)
 *    - Solo cambia color de una celda "badge" en cada hoja CC (A1) para no chocar validaciones
 ****************************************************/
function onEdit(e) {
  processEdit_(e);
}

function processEdit_(e) {
  if (!e || !e.range) return;

  const sh = e.range.getSheet();
  const name = sh.getName();

  const isCC = COST_CENTERS.includes(name);
  const isCons = (name === CONFIG.CONSOLIDADO_SHEET);
  if (!isCC && !isCons) return;

  const col = e.range.getColumn();

  // columnas relevantes + meses (I..T = 9..20)
  if (
    col === CONFIG.COL_SIGEAD ||
    col === CONFIG.COL_TOTAL_PROG ||
    col === CONFIG.COL_TOTAL_DEV ||
    (col >= 9 && col <= 20)
  ) {
    checkThresholdForSheet_(sh);
    if (isCC) rebuildConsolidado();
  }
}

function checkAllThresholds_() {
  const ss = getSS_();
  COST_CENTERS.forEach(cc => {
    const sh = ss.getSheetByName(cc);
    if (sh) checkThresholdForSheet_(sh);
  });
}

function checkThresholdForSheet_(sh) {
  const start = CONFIG.DATA_START_ROW;
  const n = CONFIG.DATA_END_ROW - CONFIG.DATA_START_ROW + 1;

  const sig = sh.getRange(start, CONFIG.COL_SIGEAD, n, 1).getValues().flat().map(num_);
  const cert = sh.getRange(start, CONFIG.COL_TOTAL_PROG, n, 1).getValues().flat().map(num_);
  const dev = sh.getRange(start, CONFIG.COL_TOTAL_DEV, n, 1).getValues().flat().map(num_);

  const sigTotal = sig.reduce((a, b) => a + b, 0);
  const certTotal = cert.reduce((a, b) => a + b, 0);
  const devTotal = dev.reduce((a, b) => a + b, 0);

  // ✅ Badge en A1 (casi siempre no tiene validación)
  const badge = sh.getRange("A1");
  badge.setBackground(null);

  if (sigTotal > 0) {
    const certRate = certTotal / sigTotal;
    const devRate = devTotal / sigTotal;

    if (certRate > CONFIG.THRESH_CERTIF) {
      badge.setBackground("#f4cccc"); // rojo
      badge.setNote(`ALERTA: Certificación ${(certRate * 100).toFixed(1)}% > 90%`);
    } else {
      badge.setNote("");
    }

    if (devRate > CONFIG.THRESH_DEV) {
      badge.setBackground("#fce5cd"); // naranja
      badge.setNote(`ALERTA: Devengado ${(devRate * 100).toFixed(1)}% > 65%`);
    }
  }
}

/****************************************************
 * HELPERS
 ****************************************************/
function extractKey_(val) {
  const s = String(val || "").trim();
  const code = s.split(" - ")[0].trim();
  return code.split(".").map(x => x.padStart(3, "0")).join(".");
}

function num_(v) {
  if (v === null || v === "" || typeof v === "undefined") return 0;
  if (typeof v === "number") return v;
  const n = Number(String(v).replace(/,/g, "").trim());
  return isNaN(n) ? 0 : n;
}
