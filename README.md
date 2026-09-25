# Conteo de personas en la UNI

**Alumnos:** Isaac Antonio Martel Balvin, Sebastian Enrique Huaypar Acurio

Contamos cuantas personas recorren una alameda peatonal de la universidad y
en que sentido, sobre un video de 8 min 4 s grabado desde un piso alto
(848x478, 30 fps).

## Archivos

| Archivo | Que hace |
|---|---|
| `obtener_regiones.py` | Marca a mano las zonas de conteo sobre el primer cuadro |
| `estabilizar.py` | Alinea todos los cuadros al primero |
| `main.py` | El conteo |
| `validar.py` | Segunda estimacion con otra tecnica, para contrastar |

## Como se corre

    python estabilizar.py video.mp4 video_estable.mp4
    python main.py
    python validar.py

Salidas: `resultado.mp4`, `eventos.csv`, `kimograma_vista.png`.
Las regiones ya estan marcadas en `regiones.pkl`; para rehacerlas,
`python obtener_regiones.py video_estable.mp4`.

## Videos

En el repositorio esta `video.mp4`, la grabacion original. Los otros dos se
generan con los scripts, asi que no hace falta descargarlos:

| Archivo | Como se obtiene |
|---|---|
| `video.mp4` | Esta en el repositorio |
| `video_estable.mp4` | `estabilizar.py`, ~9 min |
| `resultado.mp4` | `main.py`, ~3 min |

El proceso es determinista: con el mismo video y las mismas regiones, los
archivos generados salen identicos.

Para ver el conteo sin correr nada:
https://drive.google.com/file/d/1f252L3wgDeqz04HkTBluB5OxOdYcggC2/view?usp=sharing

---

## RESULTADOS

    Personas que pasaron: 74
       entran: 39 | salen: 35
    Cruces detectados: 42
    Minuto con mas flujo: minuto 6 con 18 personas
    Promedio: 9.18 personas por minuto

El numero honesto es **"unas 74 personas, entre 65 y 85"**. La incertidumbre
del metodo es de 15 a 20 %, y la medimos.

---

## COMO FUNCIONA

Se marcan dos bandas cruzadas sobre el camino, A arriba y B abajo, separadas
30 pixeles. Si alguien activa primero A y despues B va bajando; al reves, va
subiendo.

Sobre cada cuadro se aplica la cadena vista en clase: `cvtColor` a grises,
`adaptiveThreshold` para dejar los bordes en blanco, `medianBlur` para sacar
ruido y `dilate` para engordar las manchas. Despues `countNonZero` cuenta los
pixeles blancos dentro de cada banda.

Mientras la banda esta ocupada se acumula ese conteo. Al vaciarse, el area
acumulada se divide entre la que deja una sola persona al cruzar. Asi se sabe
cuanta gente paso, aunque hayan ido en grupo.

### Calibracion

    UMBRAL = 120               pixeles para dar la banda por ocupada
    PIX_POR_PERSONA = 372      pixeles que aporta una persona
    CUADROS_POR_PERSONA = 135  cuadros que tarda en atravesar la banda
    MIN_CUADROS = 3            cuadros seguidos para no contar ruido
    VENTANA_PAR = 60           cuadros maximos entre banda A y banda B

Medimos cuantos pixeles genera cada cantidad de gente:

| Personas | Pixeles (mediana) |
|---|---|
| 0 | 0 |
| 1 | 370 |
| 2 | 730 |
| 3 | 1170 |

De ahi salen dos cosas. Primero, que el umbral no puede ser alto: 600 cae
entre una persona y dos, asi que ignora a quien cruce solo. Segundo, que la
relacion es lineal, o sea que `countNonZero` no solo dice si hay alguien,
dice cuantos hay. El valor exacto, 372 px por persona, sale de una regresion
con correlacion 0.81.

El tiempo de transito fue lo dificil. Lo medimos de dos formas y no
coincidieron: por geometria da ~113 cuadros, cronometrando cruces de una sola
persona da ~135. Para decidir miramos el error segun cuanta gente hay en la
banda a la vez (lo ideal es 1.00 en las tres columnas):

| T | 1 persona | 2 personas | 3 personas | Total |
|---|---|---|---|---|
| 120 | 1.12 | 1.01 | 1.16 | 84 |
| **135** | **0.99** | **0.90** | **1.03** | **74** |
| 142 | 0.94 | 0.86 | 0.98 | 71 |

Con 120 el conteo se infla cuando hay mucha gente, justo cuando mas importa.
Con 135 el error queda cerca de cero.

---

## POR QUE HUBO QUE ESTABILIZAR

Grabamos a pulso, pero el temblor entre cuadros fue minimo, medio pixel. Lo
que si encontramos es que la camara derivo lentamente:

| Momento | Corrimiento |
|---|---|
| min 2 | 43 px |
| min 4 | 64 px |
| min 8 | 71 px |

Una persona vista desde arriba mide unos 40 pixeles, asi que el corrimiento
llego a ser mas grande que una persona entera. Con regiones fijas, los
rectangulos habrian terminado apuntando al pasto.

Un estabilizador comun no servia: suaviza el temblor rapido pero conserva la
deriva lenta, porque busca que el video se vea bonito. Usamos modo ancla,
alineando cada cuadro contra el primero. Cuatro pasos: `goodFeaturesToTrack`
busca esquinas, `calcOpticalFlowPyrLK` las sigue con flujo optico,
`estimateAffinePartial2D` calcula el corrimiento con RANSAC (que descarta
sola a la gente que camina) y se aplica la transformacion inversa.

La deriva bajo de 71 px a menos de 3.

---

## VALIDACION

No nos quedamos con el numero: lo medimos contra otra cosa.

`validar.py` arma un **kimograma**: una imagen donde el eje horizontal es la
posicion a lo ancho del camino y el vertical es el tiempo. De cada cuadro se
toma una franja de pixeles sobre la linea de conteo y se apila hacia abajo,
asi cada persona que cruza deja una raya diagonal. Contar personas se vuelve
contar rayas en una sola imagen, en vez de revisar 14535 cuadros.

Contrastamos los dos metodos automaticos contra un conteo manual sobre una
ventana de 90 segundos:

| Metodo | Personas en 90 s | Total del video |
|---|---|---|
| Conteo manual | 15 | - |
| `main.py` | 16.2 | 74 |
| `validar.py` | 18 | 84 |

`validar.py` no es la verdad de campo, es otra estimacion con sus propios
sesgos: cuenta el maximo de personas separadas *a la vez* en cada racha, asi
que dos que cruzan una detras de otra cuentan como una. Por eso va un 20 %
por encima del conteo manual.

Lo que la coincidencia si demuestra es que dos metodos con fallas distintas
llegan a un numero parecido.

---

## ERRORES Y LIMITACIONES

**El umbral ignoraba a quien cruzaba solo.** La primera version usaba 600 y
daba 43 personas, la mitad de las reales. Nos dimos cuenta mirando un cuadro
donde se ve a alguien cruzando y las dos bandas seguian en verde, con 450 y
239 pixeles. Como muestra la tabla de calibracion, 600 cae entre una persona
y dos: el programa solo contaba cuando pasaban dos juntas.

**Calibramos contra una referencia sin verificarla.** Despues elegimos el
tiempo de transito que hacia coincidir el conteo con `validar.py`. Daba 84 y
los dos metodos coincidian, asi que parecia correcto. Pero coincidian porque
habiamos ajustado la constante para eso. Al medirla de forma independiente,
el total bajo a 74.

**La direccion es lo menos resuelto.** El metodo deduce el sentido del orden
en que se activan las bandas, y eso se rompe de dos maneras. Con mucha gente,
las dos bandas quedan ocupadas al 100 % durante veinte segundos seguidos y no
hay ninguna transicion que mirar. Y cuando alguien entra y otro sale casi a
la vez, la banda no se vacia entre los dos y se cuentan como una sola
ocupacion: 57 de las 74 personas caen en ese caso.

Probamos varias formas de resolverlo:

| Variante | Reparto (entra / sale) |
|---|---|
| Aceptar que la banda A este ya ocupada | 63 / 19 |
| Centro de masa entre inicio y fin | 50 / 33 |
| Pendiente del centro de masa | 63 / 37 |
| Ventana deslizante | 57-66 % entradas |
| **Desfase entre senales (el que quedo)** | **39 / 35** |

El reparto real, medido por la inclinacion de las rayas del kimograma, es
48 % y 52 %. Las primeras variantes inventaban un desbalance inexistente. La
que quedo compara las dos senales enteras para ver cual va adelantada, y
antes de aplicarla verificamos que coincide en 90 % con el emparejamiento
donde este si funciona.

Aun asi, la direccion de cada persona acierta cerca del 60 %. Separar a dos
que se cruzan en sentidos opuestos sobre la misma banda necesitaria seguir a
cada una por separado, y eso ya es otro metodo.

### Que se puede creer y que no

| Medida | Confiabilidad |
|---|---|
| Total de 74 personas | Buena, 15-20 % de incertidumbre |
| Reparto global 53 / 47 | Aceptable, la referencia da 48-55 % |
| Direccion de cada persona | Poco confiable, ~60 % de acierto |

Ademas: el metodo cuenta bordes, no personas, asi que una sombra dura suma
pixeles igual que alguien caminando. Alguien que se detiene sobre la linea se
cuenta como varias personas. Y la calibracion vale para estas regiones
concretas: si se mueven los rectangulos hay que volver a medir las
constantes. Lo comprobamos, con regiones distintas el mismo video da 101
personas en vez de 74.

---

## CONCLUSIONES

**1. El metodo no cuenta personas, cuenta ocupaciones de una region.** Sirve
para un estacionamiento, donde cada auto tiene su espacio. En una alameda no
alcanza, porque la gente camina en grupo. Sin calibrar cuantos pixeles y
cuanto tiempo deja una persona, el conteo daba 43 en vez de 74.

**2. Un conteo mal calibrado se ve perfectamente bien y aun asi se equivoca
por el doble.** El video se veia normal y el numero estaba al 50 % de error.
Un resultado de vision por computador no se valida mirandolo, se valida
midiendolo contra otra cosa.

**3. La estabilizacion no era por el pulso, era por la deriva.** El temblor
era despreciable, pero la camara se corrio 71 pixeles, mas que el ancho de
una persona.

**4. El metodo mide bien un total y mal cada caso individual.** Los errores
por cruce se compensan a lo largo del video, por eso el total sirve aunque
los casos sueltos no.

**5. No todo se arregla con mas codigo.** De seis correcciones que
intentamos, tres empeoraron el resultado y las revertimos. Reconocer el
limite del metodo tambien fue parte del trabajo.
