import cv2
import pickle
import sys

# Marca las regiones sobre el primer cuadro. ENTER confirma, ESC termina.
# Van de a dos: primero A, luego B, en el sentido en que la gente entra.
#
# Uso:  python obtener_regiones.py video_estable.mp4

nombre_video = sys.argv[1] if len(sys.argv) > 1 else 'video_estable.mp4'

video = cv2.VideoCapture(nombre_video)
check, img = video.read()
if not check:
    print('No se pudo leer el video', nombre_video)
    sys.exit(1)

regiones = []

while True:
    x, y, w, h = cv2.selectROI('region', img, False)
    cv2.destroyWindow('region')
    if w == 0 or h == 0:
        break
    regiones.append((x, y, w, h))

    for i, (x, y, w, h) in enumerate(regiones):
        # A en azul, B en rojo
        color = (255, 0, 0) if i % 2 == 0 else (0, 0, 255)
        cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)
        cv2.putText(img, 'A' if i % 2 == 0 else 'B', (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

with open('regiones.pkl', 'wb') as file:
    pickle.dump(regiones, file)

print('Guardadas', len(regiones), 'regiones en regiones.pkl')
