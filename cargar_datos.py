# cargar_datos.py

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import date, timedelta
from core.models import InsumoCritico

hoy = date.today()

insumos_de_prueba = [
    # (identificador, nombre_tecnico, cantidad, unidad, umbral, dias_hasta_vencer)
    ("INS-00458", "Cloruro de sodio USP", 500, "kg", 100, 180),      # disponible
    ("INS-00459", "Lactosa monohidratada", 40, "kg", 100, 90),       # stock bajo
    ("INS-00460", "Estearato de magnesio", 0, "kg", 50, 60),         # agotado
    ("INS-00461", "Almidón de maíz pregelatinizado", 200, "kg", 50, -5),   # vencido (hace 5 días)
    ("INS-00462", "Povidona K30", 300, "kg", 80, 365),               # disponible
    ("INS-00463", "Dióxido de titanio", 25, "kg", 30, 45),           # stock bajo
    ("INS-00464", "Talco farmacéutico", 0, "kg", 20, 200),           # agotado
    ("INS-00465", "Celulosa microcristalina", 150, "kg", 100, -1),   # vencido (ayer)
    ("INS-00466", "Ácido esteárico", 90, "kg", 40, 120),             # disponible
    ("INS-00467", "Croscarmelosa sódica", 15, "kg", 50, 30),         # stock bajo
    ("INS-00468", "Óxido de hierro rojo", 60, "kg", 20, 300),        # disponible
    ("INS-00469", "Hipromelosa", 0, "kg", 25, 15),                   # agotado
]

creados = 0
for identificador, nombre, cantidad, unidad, umbral, dias in insumos_de_prueba:
    InsumoCritico.objects.create(
        identificador=identificador,
        nombre_tecnico=nombre,
        cantidad_disponible=cantidad,
        unidad_medida=unidad,
        umbral_stock_bajo=umbral,
        fecha_vencimiento=hoy + timedelta(days=dias),
    )
    creados += 1

print(f"Creados {creados} insumos de prueba.")
print(f"Total en base: {InsumoCritico.objects.count()}")

from collections import Counter
estados = Counter(
    i.estado_operativo_calculado for i in InsumoCritico.objects.all()
)
print("Distribución por estado:", dict(estados))