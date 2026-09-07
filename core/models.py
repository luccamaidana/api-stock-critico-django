# core/models.py

from datetime import date

from django.db import models
from django.db.models import Case, When, Value, F, CharField


class InsumoCriticoQuerySet(models.QuerySet):
    """
    Encapsula las reglas de cálculo de estado operativo como una
    anotación SQL, para que el filtrado por estado se resuelva en base
    de datos (vía QuerySet), no iterando en Python.
    """

    def con_estado_operativo(self):
        """
        Calcula el estado operativo de cada insumo mediante un CASE/WHEN
        evaluado en la base de datos. El orden de las condiciones define
        la prioridad: un insumo vencido lo es sin importar su cantidad;
        recién después se evalúa si está agotado o en stock bajo.
        """
        hoy = date.today()

        return self.annotate(
            estado_operativo=Case(
                When(fecha_vencimiento__lt=hoy, then=Value(InsumoCritico.Estado.VENCIDO)),
                When(cantidad_disponible=0, then=Value(InsumoCritico.Estado.AGOTADO)),
                When(
                    cantidad_disponible__lte=F('umbral_stock_bajo'),
                    then=Value(InsumoCritico.Estado.STOCK_BAJO),
                ),
                default=Value(InsumoCritico.Estado.DISPONIBLE),
                output_field=CharField(),
            )
        )

    def con_estado(self, estado):
        """
        Filtra por estado operativo. Requiere que con_estado_operativo()
        ya haya sido aplicado antes en la cadena, ya que filtra sobre
        la anotación calculada.
        """
        return self.filter(estado_operativo=estado)

    def con_vencimiento_en_rango(self, desde=None, hasta=None):
        queryset = self
        if desde:
            queryset = queryset.filter(fecha_vencimiento__gte=desde)
        if hasta:
            queryset = queryset.filter(fecha_vencimiento__lte=hasta)
        return queryset


class InsumoCritico(models.Model):
    """
    Insumo farmacéutico bajo seguimiento de stock crítico. Todo insumo
    registrado en este modelo pertenece al dominio de "insumos críticos"
    para producción — no es un catálogo general de inventario.

    El estado operativo NUNCA se persiste como texto libre: se deriva
    en tiempo de consulta a partir de cantidad_disponible, umbral_stock_bajo
    y fecha_vencimiento (ver InsumoCriticoQuerySet.con_estado_operativo).
    Esto evita el riesgo regulatorio de un estado desincronizado con los
    datos reales que le dieron origen.
    """

    class Estado(models.TextChoices):
        DISPONIBLE = 'disponible', 'Disponible'
        STOCK_BAJO = 'stock_bajo', 'Stock bajo'
        AGOTADO = 'agotado', 'Agotado'
        VENCIDO = 'vencido', 'Vencido'

    identificador = models.CharField(
        max_length=40,
        unique=True,
        help_text="Identificador público del insumo, ej: INS-00458"
    )
    nombre_tecnico = models.CharField(max_length=200)
    cantidad_disponible = models.PositiveIntegerField(
        help_text="Cantidad actual en stock, en la unidad de medida del insumo"
    )
    unidad_medida = models.CharField(
        max_length=20,
        default='unidad',
        help_text="Ej: kg, litros, unidades, ampollas"
    )
    umbral_stock_bajo = models.PositiveIntegerField(
        help_text="Cantidad mínima operativa. Por debajo de este valor, "
                   "el insumo se considera en stock bajo (salvo que ya esté vencido)."
    )
    fecha_vencimiento = models.DateField()
    fecha_registro = models.DateTimeField(auto_now_add=True)

    objects = InsumoCriticoQuerySet.as_manager()

    class Meta:
        verbose_name = "Insumo crítico"
        verbose_name_plural = "Insumos críticos"
        ordering = ['fecha_vencimiento']
        indexes = [
            models.Index(fields=['fecha_vencimiento']),
            models.Index(fields=['identificador']),
        ]

    def __str__(self):
        return f"{self.identificador} - {self.nombre_tecnico}"

    @property
    def estado_operativo_calculado(self):
        """
        Misma lógica que la anotación del QuerySet, pero evaluable en
        Python sobre una única instancia ya cargada en memoria (por
        ejemplo, en la vista de detalle, donde no hace falta una query
        anotada para un solo registro). Ambas implementaciones deben
        mantenerse alineadas: si cambia una regla, cambia en las dos.
        """
        hoy = date.today()

        if self.fecha_vencimiento < hoy:
            return self.Estado.VENCIDO
        if self.cantidad_disponible == 0:
            return self.Estado.AGOTADO
        if self.cantidad_disponible <= self.umbral_stock_bajo:
            return self.Estado.STOCK_BAJO
        return self.Estado.DISPONIBLE