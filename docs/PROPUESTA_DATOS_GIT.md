# Inclusión de fuentes

Aprobada explícitamente: únicamente los tres ZIP de la tabla y documentación. Modelos, métricas y etiquetas anteriores permanecen intactos.

| Archivo propuesto | Bytes | Licencia local | Condiciones |
|---|---:|---|---|
| `data/raw/international_results_current.zip` | 1,300,320 | CC0-1.0 | Snapshot sin modificar; licencia local; conserva los cuatro CSV y su documentación. |
| `data/raw/fjelstul_worldcup.zip` | 22,537,679 | CC-BY-SA-4.0 | Archivo sin modificar; atribución y share-alike para adaptaciones de la base. |
| `data/raw/openfootball_worldcup.zip` | 1,007,635 | CC0-1.0 | Archivo intacto, licencia local; se conserva fuente separada. |

Los cuatro CSV de martj42 se incluyen dentro del ZIP intacto. El manifiesto verifica también los bytes descomprimidos de cada CSV. No duplico los datos ni cambio las rutas del cargador.

Exclusiones propuestas: ranking semestral y foto repetida (licencia no verificada), GeoNames (licencia no verificada), Transfermarkt DuckDB (tamaño, vínculo exacto no verificado), StatsBomb (restricción expresa y tamaño), calendario original (licencia no verificada), otros archivos históricos de la competencia (no son insumos del diseño final).

Incluyo documentación, manifiesto y verificadores. El calendario resuelto ya está en Git; su licencia no verificada requiere confirmación independiente, sin modificar el sellado.

Pendientes de confirmar: URLs exactas martj42, Openfootball, ranking semestral, GeoNames y calendario; fechas de obtención de todas las fuentes; licencias de ranking, GeoNames y calendario; identidad de origen del DuckDB exacto.

Decisión de publicación: aplico una lista explícita de archivos permitidos en `.gitignore`, traslado la sección Datos propuesta al README principal, registro la revisión documental sin cambiar auditorías históricas de métricas y creo el commit separado con etiqueta `docs-data-sources`. Las etiquetas existentes permanecen intactas.
