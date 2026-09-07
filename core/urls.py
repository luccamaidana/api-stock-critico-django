# core/urls.py

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('api/insumos-criticos/', views.listado_insumos_criticos, name='listado_insumos_criticos'),
    path('api/insumos-criticos/<str:identificador>/', views.detalle_insumo_critico, name='detalle_insumo_critico'),
]