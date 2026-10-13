# Fuentes locales y reproducción

Trabajo retrospectivo. El inventario distingue el snapshot completo del historial admitido antes del corte exclusivo 2026-06-10. No reajusto modelos ni recalculo métricas en esta comprobación.

La incorporación aprobada comprende únicamente los ZIP de martj42, Fjelstul y Openfootball, además de esta documentación. Las restantes fuentes permanecen locales.

## Integridad y reconstrucción

```powershell
python tools/verify_data.py
python tools/verify_data.py --rebuild-history
```

Si solo dispongo de los insumos del historial, uso `python tools/verify_data.py --history-only --rebuild-history`. Este alcance exige martj42, Fjelstul y el calendario resuelto; no exige fuentes opcionales o excluidas y no acredita su integridad.

El primer comando verifica bytes y SHA256 de archivos y miembros del ZIP, más los 43 artefactos y cinco archivos de código protegidos. Falla ante un archivo ausente o distinto. `--included-only` verifica solo fuentes rastreadas y no acredita reproducción completa.

El segundo reconstruye el historial en memoria con el cargador existente, sin entrenar modelos, generar variables ni guardar resultados. Compara el CSV con CRLF con `history_sha256` y lee todos los conteos esperados de `reports/final_evaluation/data_inventory.json`.

| Comprobación | Esperado (inventario ejecutado) |
|---|---:|
| Historial | 49,469 |
| Ajuste 2000–2022 | 21,781 |
| Validación 2016–2022 | 6,376 |
| Evaluación semiconfirmatoria | 3,624 |
| Partidos de grupos | 72 |

SHA256 del historial: `0d0e7c8abda04d8d7723d5bd1d11e70af8f9415727a7c0353be03227e475f8d6`.

## Obtención manual de dependencias externas

No hay descarga automática. Recupero el mismo snapshot local y lo coloco con el nombre indicado en el manifiesto. Cuando existe un enlace confirmado en documentación local, puedo consultar allí su disponibilidad; una descarga actual puede tener otro hash y no reproduce este estudio. Para las fuentes sin URL o licencia confirmada, necesito el enlace o la documentación de origen del proveedor antes de proponer su redistribución.

Martj42 se actualiza: la versión queda fijada por el SHA256 del ZIP y de sus cuatro CSV, no por el nombre del archivo ni por las cantidades desactualizadas del README de origen.

Registro la modificación local de cada archivo como «fecha local del archivo»; no es una fecha de obtención verificada. Ambas categorías están separadas en `MANIFEST.csv`.

| Archivo local | Fecha local del archivo | Origen confirmado | Licencia / decisión | SHA256 esperado |
|---|---|---|---|---|
| `data/raw/international_results_current.zip` | 2026-10-11T22:57:12.939057-05:00 | no verificada | CC0-1.0; Snapshot sin modificar; licencia local; conserva los cuatro CSV y su documentación. | `c4ce2d659ed254a5cd1327d52b09e55e21c50fcc860e16e6b0ab8af94dc980d5` |
| `data/raw/fjelstul_worldcup.zip` | 2026-06-05T12:45:44.681970-05:00 | https://github.com/jfjelstul/worldcup | CC-BY-SA-4.0; Archivo sin modificar; atribución y share-alike para adaptaciones de la base. | `dff7f988cb0e283b55e75132e7d835f3e871782d2be95901488412c2dcb12c15` |
| `data/raw/fifa_rank_semesters.zip` | 2026-10-11T22:57:47.028805-05:00 | no verificada | no verificada; Licencia y origen no verificados. | `5324582bf969b977b013e248664bf053004b765211f3e779ef81e05b6f3d7fd5` |
| `data/raw/fifa_rank_repeated_snapshot_excluded.csv` | 2026-10-11T23:18:23.484763-05:00 | no verificada | no verificada; No es un histórico; licencia y origen no verificados. | `6b22784ee665a060f6acce3fad6b8faf5c404edb4521807294f1c4784927953d` |
| `data/raw/geonames_cities15000.zip` | 2026-10-11T22:55:52.536647-05:00 | no verificada | no verificada; ZIP sin licencia ni metadatos de origen; no inferir condiciones de memoria. | `8c2390a973087b9f42671a01c401ccbbc4d1346fe1d0371c15d1090b21d2d725` |
| `data/raw/transfermarkt.duckdb` | 2026-10-12T00:10:32.039514-05:00 | https://github.com/dcaribou/transfermarkt-datasets | CC0 declarada para el dataset; vínculo del DuckDB exacto no verificado; Tamaño superior a 100 MiB; no se incluye. Metadatos declaran CC0; falta procedencia verificable del snapshot exacto. | `ba1eff7337b8ca78cb533df0b6eba0d6fc58218e0767460f6770e0b37f5a2113` |
| `data/raw/transfermarkt_repository.zip` | 2026-10-11T22:57:06.398474-05:00 | https://github.com/dcaribou/transfermarkt-datasets | CC0-1.0 (repositorio); Se conserva evidencia de documentación, no se publica todo el repositorio ajeno. | `d684fe944e12d80e99740b69653aede13a4f309911c9d2d4dd955e5c23376ba5` |
| `data/raw/statsbomb_open_data.zip` | 2026-10-11T23:03:43.075259-05:00 | https://github.com/statsbomb/open-data | StatsBomb Public Data User Agreement; no redistribución; Acuerdo local prohíbe redistribuir datos; archivo de más de 1 GiB. | `26bf5d5549d0df260e747b48ce086be6f2a4c6b7f8f02cd186ae727bd93eeb23` |
| `data/raw/openfootball_worldcup.zip` | 2026-10-11T22:58:07.487889-05:00 | no verificada | CC0-1.0; Archivo intacto, licencia local; se conserva fuente separada. | `399d3f202c6b00dfb958cd74aac7e8f220febd822277db443ffd8629a57a2130` |
| `reports/probabilistic/resolved_fixtures.csv` | 2026-10-11T22:12:30.847102-05:00 | no verificada | no verificada; Ya incluido en Git; procedencia declarada del proyecto histórico, sin licencia de entrada verificada. No modificar el archivo. | `556103e18a99610742ea604e51fdbf76101a1135344bb3fc44b4aa660e759247` |
| `data/raw/worldcup_fixtures.zip` | 2026-06-05T13:00:11.770010-05:00 | no verificada | no verificada; Archivo sin licencia ni URL; los slots no son resultados de entrenamiento. | `fdeddf8cf8d6832dc77feda364132755a8b9b06f4df99befac7b2eb3dcdbfeda` |
| `worldcup_2026_model_pipeline.py` | 2026-10-12T14:36:47.253219-05:00 | no verificada | términos de la competencia pendientes de verificar; No se utiliza como modelo ni baseline. | `59334e474f39f6704f4677c4f67c68519d3ed4b2aee0cf5e075d4418bb527bb1` |

El DuckDB se proporciona como snapshot del dataset dcaribou. Su README local contiene el enlace de descarga, pero no demuestra la identidad del archivo recibido; la correspondencia exacta queda no verificada. El ranking semestral y GeoNames solo pueden recuperarse del snapshot suministrado hasta confirmar su origen.

## Atribución y alcance

Martj42: cuatro CSV sin modificar y licencia CC0 local. Openfootball: archivo separado, sin modificar, CC0 local. Sus URLs exactas requieren confirmación; no deduzco un enlace solo del nombre del ZIP.

Fjelstul: © 2023 Joshua C. Fjelstul, Ph.D.; autoría indicada en el README de origen como "Joshua C. Fjelstul, Ph.D." y aviso "© 2023 Joshua C. Fjelstul, Ph.D.". [Repositorio](https://github.com/jfjelstul/worldcup); [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode). Redistribuyo el ZIP sin modificar. Las adaptaciones de esta base, incluido el historial reconstruido cuando incorpora su información, conservan atribución y CC BY-SA 4.0. La licencia MIT del código propio no reemplaza estas condiciones.

StatsBomb permanece local: su acuerdo, incluido en el ZIP, impide redistribuir los datos (1.2.1 y 7); cualquier análisis publicado que lo utilice requiere la atribución y logo indicados en sus condiciones. Esta inspección no convierte la validación opcional en evidencia ejecutada.

`resolved_fixtures.csv` y `worldcup_2026_model_pipeline.py`: **términos de la competencia pendientes de verificar**. El calendario resuelto ya está rastreado y permanece intacto como metadato del sellado. La entrega de competencia queda como histórico excluido de modelos y comparaciones. No asumo que MIT cubra estas entradas.

Las copias de documentación en `license_evidence/` permiten inspeccionar las afirmaciones sobre licencias. En StatsBomb registro el hash y la ubicación del PDF sin extraerlo para redistribución.
