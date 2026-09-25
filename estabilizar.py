import cv2
import numpy as np
import sys

# Alinea cada cuadro contra el PRIMERO, para que las regiones fijas del
# conteo caigan siempre sobre el mismo piso.
# esquinas -> flujo optico Lucas-Kanade -> transformacion rigida -> inversa
#
# Uso:  python estabilizar.py video.mp4 video_estable.mp4

entrada = sys.argv[1] if len(sys.argv) > 1 else 'video.mp4'
salida = sys.argv[2] if len(sys.argv) > 2 else 'video_estable.mp4'

ZOOM = 1.06          # recorte leve para disimular el corrimiento en los bordes
REFRESCO = 150       # cada cuantos cuadros se rebuscan los puntos de referencia

video = cv2.VideoCapture(entrada)
n_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
fps = video.get(cv2.CAP_PROP_FPS)
ancho = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
alto = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))

# cuadro de referencia
check, ref = video.read()
if not check:
    print('No se pudo leer el video', entrada)
    sys.exit(1)
ref_gris = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(salida, fourcc, fps, (ancho, alto))

T_zoom = cv2.getRotationMatrix2D((ancho / 2, alto / 2), 0, ZOOM)

out.write(cv2.warpAffine(ref, T_zoom, (ancho, alto), borderMode=cv2.BORDER_REPLICATE))

pts_ref = cv2.goodFeaturesToTrack(ref_gris, maxCorners=500,
                                  qualityLevel=0.01, minDistance=20,
                                  blockSize=3)

correcciones = []
n = 1

while True:
    check, frame = video.read()
    if not check:
        break
    n += 1
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if n % REFRESCO == 0 or pts_ref is None or len(pts_ref) < 20:
        pts_ref = cv2.goodFeaturesToTrack(ref_gris, maxCorners=500,
                                          qualityLevel=0.01, minDistance=20,
                                          blockSize=3)

    m = None
    if pts_ref is not None:
        pts_act, status, err = cv2.calcOpticalFlowPyrLK(ref_gris, gris, pts_ref, None)
        idx = np.where(status == 1)[0]

        if len(idx) >= 10:
            p0 = pts_ref[idx]
            p1 = pts_act[idx]
            m, _ = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                               ransacReprojThreshold=3)

    if m is not None:
        dx, dy = m[0, 2], m[1, 2]
        da = np.arctan2(m[1, 0], m[0, 0])
        correcciones.append(np.hypot(dx, dy))
        m_inv = cv2.invertAffineTransform(m)
        estable = cv2.warpAffine(frame, m_inv, (ancho, alto),
                                 borderMode=cv2.BORDER_REPLICATE)
    else:
        correcciones.append(0.0)
        estable = frame

    estable = cv2.warpAffine(estable, T_zoom, (ancho, alto),
                             borderMode=cv2.BORDER_REPLICATE)
    out.write(estable)

    if n % 300 == 0:
        print('cuadro', n, 'de', n_frames)

video.release()
out.release()

c = np.array(correcciones)
print('\n===== ESTABILIZACION TERMINADA =====')
print('Cuadros procesados:', n)
print('Correccion aplicada (px): media', round(c.mean(), 2),
      '| maxima', round(c.max(), 2))
print('Video estabilizado guardado en', salida)
