"""Inventory supplied files and prepare documentation, without changing the study."""
import csv
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_final_evaluation import frozen_checks, git
from verify_data import sha256

UNKNOWN = 'no verificada'


def csv_summary(content, date_columns=()):
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
    rows = list(reader)
    values = [r[c] for r in rows for c in date_columns if r.get(c)]
    return {'rows': len(rows), 'columns': reader.fieldnames,
            'date_first': min(values) if values else '', 'date_last': max(values) if values else ''}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true', help='Apply the explicitly approved data documentation')
    approved = parser.parse_args().publish
    frozen = frozen_checks()
    inventory = json.loads((ROOT / 'reports/final_evaluation/data_inventory.json').read_text(encoding='utf-8'))
    tracked = set(git('ls-files').decode('utf-8').splitlines())
    if approved:
        tracked.update('data/raw/' + name for name in ['international_results_current.zip', 'fjelstul_worldcup.zip', 'openfootball_worldcup.zip'])
    output = ROOT / 'data'
    output.mkdir(exist_ok=True)
    evidence = output / 'license_evidence'
    evidence.mkdir(exist_ok=True)
    rows = []
    sources = []

    def add(source, file, role, license=UNKNOWN, license_evidence='', url=UNKNOWN,
            origin_evidence='', proposal='exclude', reason='', member='', summary=None):
        path = ROOT / file
        if member:
            with zipfile.ZipFile(path) as archive:
                content = archive.read(member)
                size = len(content)
                digest = hashlib.sha256(content).hexdigest()
        else:
            size = path.stat().st_size
            with path.open('rb') as stream:
                digest = sha256(stream)
        row = dict(source=source, file=file, archive_member=member, bytes=size, sha256=digest,
                   rows='', date_first='', date_last='', date_semantics='', origin_url=url,
                   origin_evidence=origin_evidence, obtained_date=UNKNOWN,
                   local_file_date=datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
                   date_label='fecha local del archivo', license=license,
                   license_evidence=license_evidence, role=role,
                   included_in_git='yes' if file in tracked else 'no', proposed_action=proposal,
                   decision_reason=reason)
        if summary:
            row.update({k: v for k, v in summary.items() if k != 'columns'})
        rows.append(row)
        return row

    def retain_text(archive_name, member, name):
        with zipfile.ZipFile(ROOT / 'data/raw' / archive_name) as archive:
            content = archive.read(member)
        (evidence / name).write_bytes(content)
        return f'data/license_evidence/{name}'

    martj = retain_text('international_results_current.zip', 'international_results-master/LICENSE', 'martj42_CC0.txt')
    retain_text('international_results_current.zip', 'international_results-master/README.md', 'martj42_README.md')
    fjel = retain_text('fjelstul_worldcup.zip', 'worldcup-master/README.md', 'fjelstul_README.md')
    openlicense = retain_text('openfootball_worldcup.zip', 'worldcup-master/LICENSE.md', 'openfootball_CC0.txt')
    retain_text('openfootball_worldcup.zip', 'worldcup-master/README.md', 'openfootball_README.md')
    retain_text('transfermarkt_repository.zip', 'transfermarkt-datasets-master/LICENSE', 'transfermarkt_repository_CC0.txt')
    tmmeta = retain_text('transfermarkt_repository.zip', 'transfermarkt-datasets-master/data/prep/dataset-metadata.json', 'transfermarkt_dataset_metadata.json')
    tmreadme = retain_text('transfermarkt_repository.zip', 'transfermarkt-datasets-master/README.md', 'transfermarkt_README.md')
    retain_text('statsbomb_open_data.zip', 'open-data-master/README.md', 'statsbomb_README.md')
    # Retain the agreement hash and archive location, not a redistributed PDF.
    add('martj42 snapshot', 'data/raw/international_results_current.zip', 'estado Elo; ajuste; validación 2026 tras sellado',
        'CC0-1.0', martj, proposal='include', reason='Snapshot sin modificar; licencia local; conserva los cuatro CSV y su documentación.')
    with zipfile.ZipFile(ROOT / 'data/raw/international_results_current.zip') as archive:
        for name in ['results', 'shootouts', 'goalscorers', 'former_names']:
            member = 'international_results-master/' + name + '.csv'
            columns = ('start_date', 'end_date') if name == 'former_names' else ('date',)
            summary = csv_summary(archive.read(member), columns)
            summary['date_semantics'] = 'intervalos de nombres históricos' if name == 'former_names' else 'fecha del partido; snapshot completo, no conjunto de ajuste'
            add('martj42 ' + name, 'data/raw/international_results_current.zip',
                'normalización' if name == 'former_names' else 'estado Elo; ajuste; verificación de duración',
                'CC0-1.0', martj, proposal='include', member=member, summary=summary,
                reason='Miembro sin modificar del ZIP propuesto; hash de bytes descomprimidos.')
    add('Fjelstul', 'data/raw/fjelstul_worldcup.zip', 'validación de duración; reconstrucción histórica a 90 minutos',
        'CC-BY-SA-4.0', fjel, 'https://github.com/jfjelstul/worldcup', fjel,
        'include', 'Archivo sin modificar; atribución y share-alike para adaptaciones de la base.')
    with zipfile.ZipFile(ROOT / 'data/raw/fjelstul_worldcup.zip') as archive:
        for name, dates in [('matches', ('match_date',)), ('goals', ()), ('teams', ())]:
            member = 'worldcup-master/data-csv/' + name + '.csv'
            summary = csv_summary(archive.read(member), dates)
            add('Fjelstul ' + name, 'data/raw/fjelstul_worldcup.zip', 'validación; catálogo histórico',
                'CC-BY-SA-4.0', fjel, 'https://github.com/jfjelstul/worldcup', fjel,
                'include', 'Tabla del archivo intacto; incluye torneos masculinos y femeninos.', member, summary)
    with zipfile.ZipFile(ROOT / 'data/raw/fifa_rank_semesters.zip') as archive:
        member = 'fifa_mens_rank.csv'
        summary = csv_summary(archive.read(member), ('date',))
        summary['date_semantics'] = 'año; semestre en columna semester; disponibilidad posterior al fin del semestre'
        add('Ranking FIFA semestral', 'data/raw/fifa_rank_semesters.zip', 'ablación; excluido del modelo elegido',
            member=member, summary=summary, reason='Sin licencia ni URL de origen en el archivo local.')
    add('Ranking FIFA semestral contenedor', 'data/raw/fifa_rank_semesters.zip', 'ablación; excluida', reason='Licencia y origen no verificados.')
    add('Ranking FIFA foto repetida', 'data/raw/fifa_rank_repeated_snapshot_excluded.csv', 'excluida',
        summary={**csv_summary((ROOT / 'data/raw/fifa_rank_repeated_snapshot_excluded.csv').read_bytes(), ('rank_date',)),
                 'date_semantics': 'fechas impresas; foto repetida, no observaciones históricas válidas'},
        reason='No es un histórico; licencia y origen no verificados.')
    with zipfile.ZipFile(ROOT / 'data/raw/geonames_cities15000.zip') as archive:
        content = archive.read('cities15000.txt')
        count = sum(bool(line) for line in content.splitlines())
        add('GeoNames cities15000', 'data/raw/geonames_cities15000.zip', 'ablación de altitud estática; excluida del modelo elegido',
            summary={'rows': count, 'date_semantics': 'dato estático; modificación de ficha no es fecha de obtención'},
            reason='ZIP sin licencia ni metadatos de origen; no inferir condiciones de memoria.')
        add('GeoNames cities15000 tabla', 'data/raw/geonames_cities15000.zip', 'ablación', member='cities15000.txt',
            summary={'rows': count}, reason='Mismo archivo sin encabezado; 19 columnas tabuladas.')
    import duckdb
    connection = duckdb.connect(str(ROOT / 'data/raw/transfermarkt.duckdb'), read_only=True)
    tables = []
    for (table,) in connection.sql('SHOW TABLES').fetchall():
        columns = connection.sql(f'DESCRIBE "{table}"').fetchall()
        count = connection.sql(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        date_column = 'date' if any(c[0] == 'date' for c in columns) else None
        bounds = connection.sql(f'SELECT min(date),max(date) FROM "{table}"').fetchone() if date_column else ('', '')
        tables.append({'table': table, 'rows': count, 'date_first': str(bounds[0]), 'date_last': str(bounds[1]),
                       'date_semantics': 'date' if date_column else 'sin fecha histórica de observación',
                       'columns': [{'name': c[0], 'type': c[1]} for c in columns]})
    tmurl = 'https://github.com/dcaribou/transfermarkt-datasets'
    add('Transfermarkt DuckDB', 'data/raw/transfermarkt.duckdb', 'games: validación 2026; mercado y national_teams: excluidos como variables',
        'CC0 declarada para el dataset; vínculo del DuckDB exacto no verificado', tmmeta, tmurl, tmreadme,
        reason='Tamaño superior a 100 MiB; no se incluye. Metadatos declaran CC0; falta procedencia verificable del snapshot exacto.',
        summary={'rows': sum(t['rows'] for t in tables), 'date_semantics': 'suma de filas de tablas distintas; rangos y esquemas por tabla en source_inventory.json'})
    add('Transfermarkt repositorio de origen', 'data/raw/transfermarkt_repository.zip', 'evidencia de origen/licencia; no entrada del modelo',
        'CC0-1.0 (repositorio)', 'data/license_evidence/transfermarkt_repository_CC0.txt', tmurl, tmreadme,
        reason='Se conserva evidencia de documentación, no se publica todo el repositorio ajeno.')
    connection.close()
    with zipfile.ZipFile(ROOT / 'data/raw/statsbomb_open_data.zip') as archive:
        matches = []
        metadata_files = [n for n in archive.namelist() if '/data/matches/' in n and n.endswith('.json')]
        for member in metadata_files:
            matches.extend(json.loads(archive.read(member)))
        dates = [r['match_date'] for r in matches]
        event_files = sum('/data/events/' in n and n.endswith('.json') for n in archive.namelist())
        license_hash = hashlib.sha256(archive.read('open-data-master/LICENSE.pdf')).hexdigest()
        stats_summary = {'rows': len(matches), 'date_first': min(dates), 'date_last': max(dates),
                         'date_semantics': 'filas de metadatos de partidos; eventos no sumados como filas'}
        add('StatsBomb', 'data/raw/statsbomb_open_data.zip', 'validación opcional; no usada para ajustar ni elegir modelos',
            'StatsBomb Public Data User Agreement; no redistribución',
            'data/raw/statsbomb_open_data.zip::open-data-master/LICENSE.pdf (1.2.1 y 7)',
            'https://github.com/statsbomb/open-data', 'LICENSE.pdf, apartado 2.1',
            reason='Acuerdo local prohíbe redistribuir datos; archivo de más de 1 GiB.', summary=stats_summary)
    open_summary = {}
    with zipfile.ZipFile(ROOT / 'data/raw/openfootball_worldcup.zip') as archive:
        for member in ['worldcup-master/2026--canada-usa-mexico/cup.txt', 'worldcup-master/2026--canada-usa-mexico/cup_finals.txt']:
            dates = []; day = None; count = 0
            for line in archive.read(member).decode('utf-8-sig').splitlines():
                dm = re.match(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(June|Jun|July|Jul)\s+(\d+)', line.strip())
                if dm: day = f"2026-{'06' if dm[1].startswith('Jun') else '07'}-{int(dm[2]):02d}"
                if re.match(r'(?:\(\d+\)\s*)?\d{1,2}:\d\d\s+UTC[+-]\d+\s+.+?\s+\d+-\d+\s+', line.strip()):
                    count += 1
                    if day: dates.append(day)
            summary = {'rows': count, 'date_first': min(dates), 'date_last': max(dates), 'date_semantics': 'fecha local de partidos 2026'}
            open_summary[member] = summary
            add('Openfootball ' + member.split('/')[-1], 'data/raw/openfootball_worldcup.zip', 'validación 2026 tras sellado',
                'CC0-1.0', openlicense, proposal='include', member=member, summary=summary,
                reason='Fuente separada de Fjelstul. URL exacta del origen no confirmada en los metadatos locales.')
    add('Openfootball', 'data/raw/openfootball_worldcup.zip', 'validación 2026 tras sellado', 'CC0-1.0', openlicense,
        proposal='include', reason='Archivo intacto, licencia local; se conserva fuente separada.')
    fixture_path = 'reports/probabilistic/resolved_fixtures.csv'
    add('Partidos resueltos', fixture_path, 'metadatos de pronóstico; no entrenamiento',
        proposal='existing_pending_license', reason='Ya incluido en Git; procedencia declarada del proyecto histórico, sin licencia de entrada verificada. No modificar el archivo.',
        summary=csv_summary((ROOT / fixture_path).read_bytes(), ('date_utc',)))
    add('Calendario suministrado', 'data/raw/worldcup_fixtures.zip', 'metadatos; archivo original',
        reason='Archivo sin licencia ni URL; los slots no son resultados de entrenamiento.')
    add('Entrega de competencia', 'worldcup_2026_model_pipeline.py', 'histórico excluido de comparaciones',
        license='términos de la competencia pendientes de verificar', reason='No se utiliza como modelo ni baseline.')
    # Hash evidence as well: license claims refer to immutable local documents.
    for path in sorted(evidence.iterdir()):
        add('Evidencia documental', path.relative_to(ROOT).as_posix(), 'documentación de procedencia y condiciones',
            proposal='documentation', reason='Copia exacta del documento local de origen; no sustituye la licencia de los datos.')
    fields = list(rows[0])
    with (output / 'MANIFEST.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    report = {'inspected_at_utc': datetime.now(timezone.utc).isoformat(), 'approval_status': 'approved' if approved else 'pending',
              'network_access': False, 'model_fitting': False, 'frozen_integrity': frozen,
              'authoritative_counts_file': 'reports/final_evaluation/data_inventory.json',
              'sources': rows, 'transfermarkt_tables': tables,
              'statsbomb': {'metadata_files': len(metadata_files), 'event_files': event_files, 'license_pdf_sha256': license_hash,
                           'agreement_revision_printed_in_pdf': '8 September 2023', 'obtained_date': UNKNOWN},
              'origin_notes': 'URL no verificada significa que el paquete local no confirma la URL exacta. Fecha de publicación, modificación o inspección no equivale a obtención.'}
    (output / 'source_inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    docs = ['# Fuentes locales y reproducción', '',
            'Trabajo retrospectivo. El inventario distingue el snapshot completo del historial admitido antes del corte exclusivo 2026-06-10. No reajusto modelos ni recalculo métricas en esta comprobación.', '',
            'La incorporación aprobada comprende únicamente los ZIP de martj42, Fjelstul y Openfootball, además de esta documentación. Las restantes fuentes permanecen locales.', '',
            '## Integridad y reconstrucción', '', '```powershell', 'python tools/verify_data.py',
            'python tools/verify_data.py --rebuild-history', '```', '',
            'Si solo dispongo de los insumos del historial, uso `python tools/verify_data.py --history-only --rebuild-history`. Este alcance exige martj42, Fjelstul y el calendario resuelto; no exige fuentes opcionales o excluidas y no acredita su integridad.', '',
            'El primer comando verifica bytes y SHA256 de archivos y miembros del ZIP, más los 43 artefactos y cinco archivos de código protegidos. Falla ante un archivo ausente o distinto. `--included-only` verifica solo fuentes rastreadas y no acredita reproducción completa.', '',
            'El segundo reconstruye el historial en memoria con el cargador existente, sin entrenar modelos, generar variables ni guardar resultados. Compara el CSV con CRLF con `history_sha256` y lee todos los conteos esperados de `reports/final_evaluation/data_inventory.json`.', '',
            '| Comprobación | Esperado (inventario ejecutado) |', '|---|---:|']
    for key, label in [('history_matches','Historial'),('model_training_matches','Ajuste 2000–2022'),('pre2023_walk_forward_matches','Validación 2016–2022'),('semiconfirmatory_matches','Evaluación semiconfirmatoria'),('group_forecasts','Partidos de grupos')]:
        docs.append(f'| {label} | {inventory[key]:,} |')
    docs += ['', f"SHA256 del historial: `{inventory['history_sha256']}`.", '',
             '## Obtención manual de dependencias externas', '',
             'No hay descarga automática. Recupero el mismo snapshot local y lo coloco con el nombre indicado en el manifiesto. Cuando existe un enlace confirmado en documentación local, puedo consultar allí su disponibilidad; una descarga actual puede tener otro hash y no reproduce este estudio. Para las fuentes sin URL o licencia confirmada, necesito el enlace o la documentación de origen del proveedor antes de proponer su redistribución.', '',
             'Martj42 se actualiza: la versión queda fijada por el SHA256 del ZIP y de sus cuatro CSV, no por el nombre del archivo ni por las cantidades desactualizadas del README de origen.', '',
             'Registro la modificación local de cada archivo como «fecha local del archivo»; no es una fecha de obtención verificada. Ambas categorías están separadas en `MANIFEST.csv`.', '',
             '| Archivo local | Fecha local del archivo | Origen confirmado | Licencia / decisión | SHA256 esperado |', '|---|---|---|---|---|']
    for row in rows:
        if row['archive_member'] or row['source']=='Evidencia documental': continue
        docs.append(f"| `{row['file']}` | {row['local_file_date']} | {row['origin_url']} | {row['license']}; {row['decision_reason']} | `{row['sha256']}` |")
    docs += ['', 'El DuckDB se proporciona como snapshot del dataset dcaribou. Su README local contiene el enlace de descarga, pero no demuestra la identidad del archivo recibido; la correspondencia exacta queda no verificada. El ranking semestral y GeoNames solo pueden recuperarse del snapshot suministrado hasta confirmar su origen.', '',
             '## Atribución y alcance', '',
             'Martj42: cuatro CSV sin modificar y licencia CC0 local. Openfootball: archivo separado, sin modificar, CC0 local. Sus URLs exactas requieren confirmación; no deduzco un enlace solo del nombre del ZIP.', '',
             'Fjelstul: © 2023 Joshua C. Fjelstul, Ph.D.; autoría indicada en el README de origen como "Joshua C. Fjelstul, Ph.D." y aviso "© 2023 Joshua C. Fjelstul, Ph.D.". [Repositorio](https://github.com/jfjelstul/worldcup); [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode). Redistribuyo el ZIP sin modificar. Las adaptaciones de esta base, incluido el historial reconstruido cuando incorpora su información, conservan atribución y CC BY-SA 4.0. La licencia MIT del código propio no reemplaza estas condiciones.', '',
             'StatsBomb permanece local: su acuerdo, incluido en el ZIP, impide redistribuir los datos (1.2.1 y 7); cualquier análisis publicado que lo utilice requiere la atribución y logo indicados en sus condiciones. Esta inspección no convierte la validación opcional en evidencia ejecutada.', '',
             '`resolved_fixtures.csv` y `worldcup_2026_model_pipeline.py`: **términos de la competencia pendientes de verificar**. El calendario resuelto ya está rastreado y permanece intacto como metadato del sellado. La entrega de competencia queda como histórico excluido de modelos y comparaciones. No asumo que MIT cubra estas entradas.', '',
             'Las copias de documentación en `license_evidence/` permiten inspeccionar las afirmaciones sobre licencias. En StatsBomb registro el hash y la ubicación del PDF sin extraerlo para redistribución.', '']
    (output / 'README.md').write_text('\n'.join(docs), encoding='utf-8')
    proposal = ['# Inclusión de fuentes', '', 'Aprobada explícitamente: únicamente los tres ZIP de la tabla y documentación. Modelos, métricas y etiquetas anteriores permanecen intactos.', '',
                '| Archivo propuesto | Bytes | Licencia local | Condiciones |', '|---|---:|---|---|']
    for row in rows:
        if row['proposed_action']=='include' and not row['archive_member']:
            proposal.append(f"| `{row['file']}` | {row['bytes']:,} | {row['license']} | {row['decision_reason']} |")
    proposal += ['', 'Los cuatro CSV de martj42 se incluyen dentro del ZIP intacto. El manifiesto verifica también los bytes descomprimidos de cada CSV. No duplico los datos ni cambio las rutas del cargador.', '',
                 'Exclusiones propuestas: ranking semestral y foto repetida (licencia no verificada), GeoNames (licencia no verificada), Transfermarkt DuckDB (tamaño, vínculo exacto no verificado), StatsBomb (restricción expresa y tamaño), calendario original (licencia no verificada), otros archivos históricos de la competencia (no son insumos del diseño final).', '',
                 'Incluyo documentación, manifiesto y verificadores. El calendario resuelto ya está en Git; su licencia no verificada requiere confirmación independiente, sin modificar el sellado.', '',
                 'Pendientes de confirmar: URLs exactas martj42, Openfootball, ranking semestral, GeoNames y calendario; fechas de obtención de todas las fuentes; licencias de ranking, GeoNames y calendario; identidad de origen del DuckDB exacto.', '',
                 'Tras aprobación: aplico una lista explícita de archivos permitidos en `.gitignore`, traslado la sección Datos propuesta al README principal, registro la revisión documental sin cambiar auditorías históricas de métricas y creo el commit separado con etiqueta `docs-data-sources`. Las etiquetas existentes permanecen intactas.', '']
    (ROOT / 'docs/PROPUESTA_DATOS_GIT.md').write_text('\n'.join(proposal), encoding='utf-8')
    section = ['## Datos', '',
               f"Uso **{inventory['history_matches']:,} partidos** ({inventory['history_first_date']}–{inventory['history_latest_date']}) para el estado Elo y la forma; **{inventory['model_training_matches']:,}** para el ajuste, **{inventory['pre2023_walk_forward_matches']:,}** para selección temporal y **{inventory['semiconfirmatory_matches']:,}** para evaluación semiconfirmatoria. El informe presenta **{inventory['group_forecasts']} partidos de grupos** y **{inventory['worldcup_teams']} selecciones**. Estas cantidades se generan leyendo `reports/final_evaluation/data_inventory.json`.", '',
               '| Fuente | Contenido | Uso en el estudio | Licencia documentada | Enlace de origen | Incluida en Git |', '|---|---|---|---|---|---|']
    selected = ['martj42 snapshot','Fjelstul','Ranking FIFA semestral contenedor','Transfermarkt DuckDB','GeoNames cities15000','StatsBomb','Openfootball','Partidos resueltos']
    content = ['Resultados, goles, tandas y nombres históricos','Catálogo y periodos de Mundiales','Posición y puntos por año/semestre','Jugadores, valoraciones y partidos','Ciudades y altitud','Eventos y metadatos de partidos','Resultados de Mundial, separado de Fjelstul','Calendario, equipos, grupos y sedes']
    for name, description in zip(selected, content):
        row = next(r for r in rows if r['source']==name)
        link = f"[Origen]({row['origin_url']})" if row['origin_url']!=UNKNOWN else UNKNOWN
        included = 'Sí (términos de competencia pendientes)' if name=='Partidos resueltos' else 'Sí' if row['included_in_git']=='yes' else 'No'
        section.append(f"| {name} | {description} | {row['role']} | {row['license']} | {link} | {included} |")
    section += ['', 'Conservo el snapshot exacto por SHA256: el contenido actual de una fuente que se actualiza, como martj42, puede ser distinto. Las fechas de obtención no están verificadas. El [manifiesto](data/MANIFEST.csv), la [guía de fuentes](data/README.md) y el [diccionario de variables](docs/DATOS_Y_DICCIONARIO.md) detallan archivos, cantidades, cobertura, hashes y condiciones originales.', '',
                '### Datos que no uso y por qué', '',
                '- Valor de mercado: la cobertura histórica de las plantillas no permite evaluarlo en los bloques de selección. El valor y club actuales no son variables históricas válidas.',
                '- Ranking FIFA 2026: no hay histórico vigente disponible; no lo extrapolo. La foto repetida está excluida. El ranking semestral con rezago fue una ablación y no forma parte del modelo elegido.',
                '- Altitud GeoNames: evaluada como variable secundaria, no admitida en el diseño final.',
                '- StatsBomb: validación opcional, no entrenamiento ni evidencia adicional ejecutada.',
                '- `national_teams` de Transfermarkt: foto sin fecha histórica; no es ranking por partido.',
                '- Entrega DataCamp: histórico de la competencia, excluido como modelo y línea base.', '',
                'La logística utiliza las seis variables documentadas en el diccionario, calculadas únicamente con el pasado. Los datos completos posteriores al corte se conservan como fuente; sus resultados no entran en el ajuste. Las licencias de datos son independientes de MIT para el código propio.', '']
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    start = readme.index('## Datos')
    end = readme.index('## Método y lectura de resultados')
    draft = readme[:start] + '\n'.join(section) + '\n' + readme[end:]
    if approved:
        draft = draft.replace('Los archivos grandes están fuera de Git y necesito las mismas fuentes para repetir el procesamiento.', 'El historial y la presentación de los resultados finales se reconstruyen con los ZIP incluidos y `resolved_fixtures.csv`, utilizando las predicciones y métricas congeladas. Las ablaciones y la corroboración con Transfermarkt requieren las fuentes excluidas indicadas en `data/README.md`.')
        (ROOT/'README.md').write_text(draft, encoding='utf-8')
    else:
        (ROOT / 'docs/README_DATOS_PROPUESTO.md').write_text(draft, encoding='utf-8')
    frozen_checks()
    print(json.dumps({'manifest_entries': len(rows), 'source_inventory': 'data/source_inventory.json',
                      'approval_status': 'approved' if approved else 'pending', 'readme_draft': 'docs/README_DATOS_PROPUESTO.md'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
