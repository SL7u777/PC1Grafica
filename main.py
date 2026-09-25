import cv2
import pickle
import numpy as np
import sys
import csv

# Conteo de personas en una alameda peatonal.
# grises -> umbral adaptativo -> mediana -> dilatacion -> countNonZero
#
# Uso:  python main.py video_estable.mp4 regiones.pkl

nombre_video = sys.argv[1] if len(sys.argv) > 1 else 'video_estable.mp4'
nombre_regiones = sys.argv[2] if len(sys.argv) > 2 else 'regiones.pkl'

UMBRAL = 120            # pixeles para dar la region por ocupada (el piso vacio da 0)
MIN_CUADROS = 3         # cuadros seguidos ocupada para no contar ruido
VENTANA_PAR = 60        # cuadros maximos entre que se activa A y luego B
DESFASE = 33            # cuadros que tarda una persona en ir de A a B

# Calibracion medida sobre nuestro video (ver README).
PIX_POR_PERSONA = 372
CUADROS_POR_PERSONA = 135

AREA_POR_PERSONA = PIX_POR_PERSONA * CUADROS_POR_PERSONA

regiones = []
with open(nombre_regiones, 'rb') as file:
    regiones = pickle.load(file)


video = cv2.VideoCapture(nombre_video)
fps = video.get(cv2.CAP_PROP_FPS) or 24
ancho = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
alto = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
out = cv2.VideoWriter('resultado.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (ancho, alto))

# De cada par, la region B es la linea de conteo; la A da la direccion.
ocupada = [False] * len(regiones)
cuadros_ocupada = [0] * len(regiones)
ultimo_activado = [-10**9] * len(regiones)
area = [0] * len(regiones)
direccion_par = [None] * len(regiones)   # direccion vigente en este momento
retardo = [0] * len(regiones)     # cuadros entre A y B en esta ocupacion
pendiente = [0] * len(regiones)   # area aun sin direccion conocida
repartido = [None] * len(regiones)   # {direccion: area} de la ocupacion actual
hist_a = [None] * len(regiones)   # serie de la banda A durante la ocupacion
hist_b = [None] * len(regiones)   # serie de la banda B durante la ocupacion


def direccion_por_desfase(a, b):
    """Direccion cuando no hay transiciones: mira cual serie va adelantada."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if len(a) <= DESFASE + 5:
        return None
    a = a - a.mean()
    b = b - b.mean()
    if a.std() < 1 or b.std() < 1:
        return None
    baja = np.corrcoef(a[:-DESFASE], b[DESFASE:])[0, 1]
    sube = np.corrcoef(b[:-DESFASE], a[DESFASE:])[0, 1]
    if not np.isfinite(baja) or not np.isfinite(sube):
        return None
    return 'entra' if baja > sube else 'sale'

area_global = 0      # area acumulada de la linea de conteo, cuadro a cuadro
pasos_total = 0.0    # se acumula en fracciones y se redondea al final
entran = 0.0
salen = 0.0
sin_definir = 0.0
eventos = []
por_minuto = {}


def acumular(i, count):
    """Suma el area de este cuadro a la direccion vigente."""
    global entran, salen, pasos_total, area_global
    area[i] += count
    area_global += count
    pasos_total += count / AREA_POR_PERSONA
    d = direccion_par[i]
    if d is None:
        pendiente[i] += count
        return
    if repartido[i] is None:
        repartido[i] = {}
    repartido[i][d] = repartido[i].get(d, 0) + count
    if d == 'entra':
        entran += count / AREA_POR_PERSONA
    else:
        salen += count / AREA_POR_PERSONA


def fijar_direccion(i, d):
    """Al conocerse la direccion, el area pendiente se asigna a ella."""
    global entran, salen
    direccion_par[i] = d
    if pendiente[i]:
        if repartido[i] is None:
            repartido[i] = {}
        repartido[i][d] = repartido[i].get(d, 0) + pendiente[i]
        if d == 'entra':
            entran += pendiente[i] / AREA_POR_PERSONA
        else:
            salen += pendiente[i] / AREA_POR_PERSONA
        pendiente[i] = 0


def cerrar_ocupacion(i, segundo):
    """Al vaciarse la linea se cierra la racha y se anota lo que paso."""
    global sin_definir, entran, salen
    personas = area[i] / AREA_POR_PERSONA
    rep = repartido[i] or {}
    if pendiente[i]:
        d = direccion_por_desfase(hist_a[i] or [], hist_b[i] or [])
        if d is not None:
            rep[d] = rep.get(d, 0) + pendiente[i]
            if d == 'entra':
                entran += pendiente[i] / AREA_POR_PERSONA
            else:
                salen += pendiente[i] / AREA_POR_PERSONA
        else:
            sin_definir += pendiente[i] / AREA_POR_PERSONA
            rep['indefinida'] = rep.get('indefinida', 0) + pendiente[i]
    minuto = int(segundo // 60)
    por_minuto[minuto] = por_minuto.get(minuto, 0) + personas
    eventos.append((round(segundo, 2), i // 2,
                    round(rep.get('entra', 0) / AREA_POR_PERSONA, 2),
                    round(rep.get('sale', 0) / AREA_POR_PERSONA, 2),
                    round(rep.get('indefinida', 0) / AREA_POR_PERSONA, 2),
                    round(personas, 2), area[i]))
    direccion_par[i] = None
    retardo[i] = 0
    pendiente[i] = 0
    repartido[i] = None
    hist_a[i] = None
    hist_b[i] = None


n = 0
while True:
    check, img = video.read()
    if not check:
        break
    n += 1
    segundo = n / fps

    # escala de grises
    imgBN = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    imgTH = cv2.adaptiveThreshold(imgBN, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 16)
    imgMedian = cv2.medianBlur(imgTH, 5)
    kernel = np.ones((5, 5), np.int8)
    imgDil = cv2.dilate(imgMedian, kernel)

    conteos = []
    for x, y, w, h in regiones:
        conteos.append(cv2.countNonZero(imgDil[y:y+h, x:x+w]))

    for i, (x, y, w, h) in enumerate(regiones):
        count = conteos[i]
        if i % 2 == 1 and ocupada[i]:
            if hist_a[i] is None:
                hist_a[i] = []
                hist_b[i] = []
            hist_a[i].append(conteos[i - 1])
            hist_b[i].append(count)
        hay_algo = count > UMBRAL

        es_linea = (i % 2 == 1)      # la region B de cada par
        companera = i - 1 if es_linea else i + 1

        if hay_algo:
            cuadros_ocupada[i] += 1
            if i % 2 == 1 and ocupada[i]:
                acumular(i, count)
            if not ocupada[i] and cuadros_ocupada[i] >= MIN_CUADROS:
                # la region pasa de vacia a ocupada
                ocupada[i] = True
                ultimo_activado[i] = n

                if es_linea:
                    # si A se activo justo antes, la persona venia bajando
                    salto = n - ultimo_activado[companera]
                    if salto <= VENTANA_PAR:
                        fijar_direccion(i, 'entra')
                        retardo[i] = salto
                    acumular(i, count)
                elif ocupada[companera]:
                    # A se activa con B ocupada: alguien va subiendo
                    fijar_direccion(companera, 'sale')
                    if retardo[companera] == 0:
                        retardo[companera] = n - ultimo_activado[companera]
        else:
            if ocupada[i] and es_linea:
                cerrar_ocupacion(i, segundo)
            cuadros_ocupada[i] = 0
            ocupada[i] = False
            area[i] = 0

        etiqueta = str(count)
        if ocupada[i]:
            etiqueta += '  (~%.1f)' % (area[i] / AREA_POR_PERSONA)
        if ocupada[i] and i % 2 == 1 and direccion_par[i]:
            etiqueta += ' ' + direccion_par[i]
        cv2.putText(img, etiqueta, (x, y+h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        color = (0, 0, 255) if ocupada[i] else (0, 255, 0)
        cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)

    # la linea de sin direccion solo aparece si hay casos sin resolver
    hay_sin_dir = round(sin_definir) >= 1
    alto_panel = 122 if hay_sin_dir else 96
    cv2.rectangle(img, (0, 0), (355, alto_panel), (0, 0, 0), -1)
    cv2.putText(img, 'Personas: ' + str(int(round(area_global / AREA_POR_PERSONA))),
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img, 'Entran: %d   Salen: %d' % (round(entran), round(salen)), (10, 53),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    if hay_sin_dir:
        cv2.putText(img, 'Sin direccion: %d' % round(sin_definir), (10, 79),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 2)
    cv2.putText(img, 'Tiempo: %02d:%02d' % (segundo // 60, segundo % 60),
                (10, alto_panel - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    out.write(img)
    cv2.imshow('video', img)
    # cv2.imshow('video Dilatada', imgDil)
    if cv2.waitKey(1) & 0xFF == 27:   # ESC para salir
        break

# cerrar las ocupaciones que quedaron abiertas al terminar el video
for i in range(len(regiones)):
    if ocupada[i] and i % 2 == 1:
        cerrar_ocupacion(i, n / fps)

video.release()
out.release()
cv2.destroyAllWindows()

with open('eventos.csv', 'w', newline='') as f:
    esc = csv.writer(f)
    esc.writerow(['segundo', 'puerta', 'entran', 'salen', 'sin_direccion',
                  'personas', 'area_acumulada'])
    esc.writerows(eventos)

print('\n===== RESULTADOS =====')
print('Duracion analizada:', round(n / fps, 1), 'segundos')
print('Personas que pasaron:', int(round(area_global / AREA_POR_PERSONA)))
print('   entran:', int(round(entran)), '| salen:', int(round(salen)),
      '| direccion indefinida:', int(round(sin_definir)))
print('Cruces detectados:', len(eventos))
if por_minuto:
    pico_min = max(por_minuto, key=por_minuto.get)
    print('Minuto con mas flujo: minuto', pico_min, 'con',
          int(round(por_minuto[pico_min])), 'personas')
    print('Personas por minuto:', {k: int(round(v)) for k, v in sorted(por_minuto.items())})
    print('Promedio:', round(pasos_total / (n / fps / 60), 2), 'personas por minuto')
print('Eventos guardados en eventos.csv, video en resultado.mp4')
