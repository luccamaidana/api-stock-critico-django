# core/views.py

from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import InsumoCritico

LIMITE_DEFAULT = 50
LIMITE_MAXIMO = 200


class ParametroInvalido(ValueError):
    """Un query param no pudo interpretarse. Se traduce a un 400."""
    pass


def _parsear_fecha(valor, nombre_param):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        raise ParametroInvalido(
            f"'{nombre_param}' inválido: '{valor}'. Formato esperado YYYY-MM-DD."
        )


def _parsear_entero_no_negativo(valor, nombre_param, default):
    if valor is None:
        return default
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ParametroInvalido(f"'{nombre_param}' inválido: '{valor}'. Debe ser un entero.")
    if numero < 0:
        raise ParametroInvalido(f"'{nombre_param}' inválido: '{valor}'. Debe ser mayor o igual a 0.")
    return numero


def _serializar_insumo(insumo, estado_operativo):
    """
    Traduce una instancia de InsumoCritico (o una fila anotada del
    QuerySet) a un diccionario plano. Nunca se retorna la entidad del
    dominio directamente. Deliberadamente NO incluye umbral_stock_bajo:
    es una regla interna del negocio, no información que los sistemas
    consumidores necesiten para decidir.
    """
    estado_valor = str(estado_operativo)
    return {
        'id': insumo.identificador,
        'nombre_tecnico': insumo.nombre_tecnico,
        'cantidad_disponible': insumo.cantidad_disponible,
        'unidad_medida': insumo.unidad_medida,
        'fecha_vencimiento': insumo.fecha_vencimiento.isoformat(),
        'estado_operativo': estado_valor,
        'estado_operativo_display': InsumoCritico.Estado(estado_valor).label,
    }


@require_GET
def listado_insumos_criticos(request):
    """
    GET /api/insumos-criticos/?estado=&vencimiento_desde=&vencimiento_hasta=&limit=&offset=

    Lista insumos críticos filtrados y paginados. Todo el filtrado,
    ordenamiento y recorte se resuelve en el QuerySet; la vista solo
    coordina la extracción de parámetros y el armado de la respuesta.
    """

    try:
        estado_param = request.GET.get('estado')
        if estado_param and estado_param not in InsumoCritico.Estado.values:
            raise ParametroInvalido(
                f"'estado' inválido: '{estado_param}'. "
                f"Valores válidos: {', '.join(InsumoCritico.Estado.values)}."
            )

        vencimiento_desde = _parsear_fecha(request.GET.get('vencimiento_desde'), 'vencimiento_desde')
        vencimiento_hasta = _parsear_fecha(request.GET.get('vencimiento_hasta'), 'vencimiento_hasta')

        limit = _parsear_entero_no_negativo(request.GET.get('limit'), 'limit', LIMITE_DEFAULT)
        offset = _parsear_entero_no_negativo(request.GET.get('offset'), 'offset', 0)
        limit = min(limit, LIMITE_MAXIMO) if limit > 0 else LIMITE_DEFAULT

    except ParametroInvalido as error:
        return JsonResponse({'error': str(error)}, status=400)

    insumos = (
        InsumoCritico.objects
        .con_estado_operativo()
        .con_vencimiento_en_rango(vencimiento_desde, vencimiento_hasta)
    )

    if estado_param:
        insumos = insumos.con_estado(estado_param)

    # Orden explícito y estable: fecha de vencimiento primero (lo más
    # urgente arriba), identificador como desempate para que la
    # paginación por offset sea determinística entre requests.
    insumos = insumos.order_by('fecha_vencimiento', 'identificador')

    total = insumos.count()
    pagina = insumos[offset:offset + limit]

    resultados = [
        _serializar_insumo(insumo, insumo.estado_operativo)
        for insumo in pagina
    ]

    respuesta = {
        'resultados': resultados,
        'paginacion': {
            'count': total,
            'limit': limit,
            'offset': offset,
            'has_next': offset + limit < total,
            'has_previous': offset > 0,
        },
    }
    return JsonResponse(respuesta, status=200)


@require_GET
def detalle_insumo_critico(request, identificador):
    """
    GET /api/insumos-criticos/<identificador>/

    Detalle operativo de un insumo puntual. Se busca por el
    identificador público del insumo (ej: INS-00458), no por la clave
    primaria interna de la base.
    """

    try:
        insumo = InsumoCritico.objects.get(identificador=identificador)
    except InsumoCritico.DoesNotExist:
        return JsonResponse(
            {'error': f"No existe un insumo con identificador '{identificador}'."},
            status=404,
        )

    estado_operativo = insumo.estado_operativo_calculado
    return JsonResponse(_serializar_insumo(insumo, estado_operativo), status=200)