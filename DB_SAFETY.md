# Seguridad de la base de datos

## Arranque local

El servidor ya no ejecuta inicializaciones o migraciones automáticas. Para una
base ya inicializada, arrancar normalmente con:

```powershell
python app.py
```

Cuando sea necesario inicializar o actualizar deliberadamente el esquema,
detener primero el servidor y ejecutar como operación separada:

```powershell
python -c "import database; database.inicializar_db()"
```

Revisar siempre la ruta configurada antes de esa operación. El reloader de
Flask no vuelve a ejecutar la inicialización.

La misma regla se aplica al legado `app_backup.py`: su arranque no crea tablas
y todas sus conexiones pasan por la protección central de `database.py`.

## Tests

El comando oficial es:

```powershell
python run_tests.py
```

El runner crea una base temporal, configura `PECHY_TESTING=1` y `PECHY_DB`
antes del discovery, y elimina el directorio temporal al terminar. Los tests
individuales también cargan el bootstrap antes de importar la aplicación.
