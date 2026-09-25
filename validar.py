import cv2
import numpy as np
import pickle
import sys

# Segunda estimacion, con otra tecnica, para contrastar con main.py.
# Arma un kimograma: apila la linea de conteo en el tiempo, asi cada
# persona que cruza deja una raya diagonal (ver README).
#
# Uso:  python validar.py video_estable.mp4 regiones.pkl

nombre_video = sys.argv[1] if len(sys.argv) > 1 else 'video_estable.mp4'
nombre_regiones = sys.argv[2] if len(sys.argv) > 2 else 'regiones.pkl'

SEPARACION = 12   # hueco en px para separar dos personas
MIN_ANCHO = 8     # px minimos para no confundir ruido con persona
MIN_DURACION = 4  # cuadros minimos de una racha

regiones = pickle.load(open(nombre_regiones, 'rb'))
# la linea de conteo es el borde superior de la region B
x, y, w, h = regiones[1]
X0, X1, LINEA = x, x + w, y

video = cv2.VideoCapture(nombre_video)
fps = video.get(cv2.CAP_PROP_FPS) or 30

# Sustraccion de fondo: el piso es fijo, lo que sobra es la gente.
fondo = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=40,
                                           detectShadows=False)

filas = []
n = 0
while True:
    check, img = video.read()
    if not check:
        break
    n += 1
    mascara = fondo.apply(img)
    mascara = cv2.medianBlur(mascara, 5)
    franja = mascara[LINEA - 4:LINEA + 5, X0:X1].max(axis=0)
    filas.append(franja)
    if n % 1500 == 0:
        print('cuadro', n)
video.release()

kimo = np.array(filas, np.uint8)
cv2.imwrite('kimograma.png', kimo)

# un pixel por cuadro: se corta en tiras de un minuto para poder verlo
tira = int(fps * 60)
n_tiras = int(np.ceil(len(kimo) / tira))
alto_vis = 520
trozos = []
for t in range(n_tiras):
    parte = kimo[t * tira:(t + 1) * tira]
    if len(parte) < tira:
        parte = np.vstack([parte, np.zeros((tira - len(parte), kimo.shape[1]), np.uint8)])
    parte = cv2.resize(parte, (kimo.shape[1], alto_vis), interpolation=cv2.INTER_AREA)
    parte = cv2.cvtColor(parte, cv2.COLOR_GRAY2BGR)
    cv2.putText(parte, 'min ' + str(t), (6, 18), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (0, 255, 255), 1)
    cv2.rectangle(parte, (0, 0), (parte.shape[1] - 1, alto_vis - 1), (60, 60, 60), 1)
    trozos.append(parte)
cv2.imwrite('kimograma_vista.png', np.hstack(trozos))

presente = (kimo > 0).sum(axis=1) > MIN_ANCHO

rachas = []
ini = None
for i, val in enumerate(presente):
    if val and ini is None:
        ini = i
    if not val and ini is not None:
        if i - ini >= MIN_DURACION:
            rachas.append((ini, i))
        ini = None
if ini is not None:
    rachas.append((ini, len(presente)))

personas = 0
detalle = []
for a, b in rachas:
    maximo = 1
    for fila in (kimo[a:b] > 0):
        idx = np.where(fila)[0]
        if len(idx) == 0:
            continue
        g = 1
        for p, q in zip(idx, idx[1:]):
            if q - p > SEPARACION:
                g += 1
        maximo = max(maximo, g)
    personas += maximo
    detalle.append((round(a / fps, 1), round((b - a) / fps, 1), maximo))

print('\n===== VALIDACION =====')
print('Duracion:', round(n / fps, 1), 's')
print('Rachas de ocupacion de la linea:', len(rachas))
print('Personas estimadas (separando grupos):', personas)
print('Personas por racha (promedio):', round(personas / max(len(rachas), 1), 2))
print('\nDetalle (segundo, duracion, personas en la racha):')
for s, d, p in detalle[:25]:
    print('   %7.1f s   %5.1f s   %d' % (s, d, p))
if len(detalle) > 25:
    print('   ... y', len(detalle) - 25, 'rachas mas')
print('\nKimograma guardado en kimograma.png')
print('Comparar "personas estimadas" con el total que imprime main.py:')
print('la diferencia es la gente que el metodo de regiones pierde porque')
print('camina en grupo y la region la ve como una sola mancha.')
