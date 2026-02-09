# Emulador MASM 6.11 (Python, subconjunto)

Este es un **emulador de software** para un pequeño subconjunto compatible con MASM 6.11. Se centra en las interrupciones DOS para impresión, E/S de archivos y color de texto. **No** ensambla a código máquina; analiza la sintaxis tipo MASM en un IR interno y la interpreta.

## Funciones actuales
- Estado de CPU de 16 bits con banderas (CF, PF, AF, ZF, SF, OF, IF, DF)
- Modelo de memoria de 1 MB
- Secciones `.data`, `.code` y `.stack`
- Directivas de datos `db`/`dw`, `dup`, `org` en `.data` y constantes `equ` (incluyendo expresiones con `$` como `$ - etiqueta`)
- Etiquetas estilo MASM y soporte de `offset`
- Instrucciones de cadena con semántica REP/REPE/REPNE para `cmps`/`scas`
- IU: editor de código, puntos de interrupción, cuadrícula de registros y visores emergentes de memoria/pila

## Referencia de instrucciones
### Movimiento de datos
- `mov`: copia registro/memoria/inmediato a registro o memoria
- `lea`: carga la dirección efectiva (offset de etiqueta) en un registro de 16 bits
- `xchg`: intercambia dos registros o registro con memoria
- `push`/`pop`: apilar/desapilar valor de 16 bits
- `pushf`/`popf`: apilar/desapilar FLAGS
- `pusha`/`popa`: apilar/desapilar todos los registros generales
- `enter`/`leave`: configuración/desmontaje de marco de pila (`enter` solo soporta nivel de anidamiento 0)
- `cbw`: extiende con signo AL a AX
- `cwd`: extiende con signo AX a DX:AX
- `xlat`: búsqueda en tabla: AL = DS:[BX + AL]

### Aritmética
- `add`/`adc`: suma (con acarreo)
- `sub`/`sbb`: resta (con préstamo)
- `cmp`: compara (resta, solo actualiza banderas)
- `inc`/`dec`: incrementa/decrementa
- `neg`: negación en complemento a dos
- `daa`/`das`: ajuste decimal después de suma/resta
- `aaa`/`aas`: ajuste ASCII después de suma/resta
- `aam`/`aad`: ajuste ASCII después de multiplicación/división (base opcional)
- `mul`/`imul`: multiplicación sin signo/con signo
- `div`/`idiv`: división sin signo/con signo

### Lógica y operaciones bit a bit
- `and`/`or`/`xor`: lógica bit a bit
- `test`: AND lógico que solo actualiza banderas
- `not`: complemento bit a bit
- `shl`/`sal`: desplazamiento a la izquierda
- `shr`: desplazamiento lógico a la derecha
- `sar`: desplazamiento aritmético a la derecha
- `rol`/`ror`: rotación izquierda/derecha

### Flujo de control
- `jmp`: salto incondicional
- `je`/`jz`: salta si ZF=1
- `jne`/`jnz`: salta si ZF=0
- `jc`: salta si CF=1
- `jnc`/`jae`: salta si CF=0
- `jg`: salta si es mayor (ZF=0 y SF=OF)
- `jl`: salta si es menor (SF≠OF)
- `jge`: salta si es mayor o igual (SF=OF)
- `jle`: salta si es menor o igual (ZF=1 o SF≠OF)
- `loop`: decrementa CX y salta si no es cero
- `loope`: bucle mientras CX!=0 y ZF=1
- `loopne`: bucle mientras CX!=0 y ZF=0
- `call`: llama a un procedimiento (apila la dirección de retorno)
- `ret`: retorna; si no hay dirección de retorno, el emulador se detiene

### Banderas
- `clc`/`stc`/`cmc`: limpia/establece/complementa CF
- `cli`/`sti`: limpia/establece IF
- `lahf`: carga SF,ZF,AF,PF,CF en AH
- `sahf`: guarda AH en SF,ZF,AF,PF,CF

### Instrucciones de cadena
- `movsb`/`movsw`: mueve byte/palabra de DS:SI a ES:DI
- `stosb`/`stosw`: almacena AL/AX en ES:DI
- `lodsb`/`lodsw`: carga desde DS:SI a AL/AX
- `cmpsb`/`cmpsw`: compara DS:SI con ES:DI
- `scasb`/`scasw`: compara AL/AX con ES:DI
- `rep`/`repe`/`repne`: repite instrucción de cadena; `repe/repne` solo afectan la terminación de `cmps`/`scas`

### Sistema
- `int`: interrupción de software
- `int3`: interrupción de punto de interrupción (detiene el emulador)
- `iret`: retorno de interrupción (extrae IP, CS, FLAGS)
- `nop`: sin operación
- `hlt`: detiene la ejecución

## Interrupciones y servicios
### DOS INT 21h
- `AH=01h`: leer carácter con eco
- `AH=08h`: leer carácter sin eco
- `AH=0Ch`: limpiar entrada + leer
- `AH=02h`: mostrar carácter (`DL`)
- `AH=09h`: mostrar cadena terminada en `$` (`DS:DX`)
- `AH=0Ah`: entrada con búfer (`DS:DX`)
- `AH=1Ah`: establecer DTA
- `AH=19h`: obtener unidad actual
- `AH=3Ch`: crear archivo (DOS 8.3)
- `AH=3Dh`: abrir archivo (lectura/escritura/rdwr)
- `AH=3Eh`: cerrar archivo
- `AH=3Fh`: leer archivo
- `AH=40h`: escribir archivo (handle 1 = stdout)
- `AH=41h`: borrar archivo
- `AH=42h`: mover puntero
- `AH=43h`: obtener/establecer atributos de archivo (solo obtener)
- `AH=47h`: obtener directorio actual
- `AH=4Eh`: buscar primero (DTA)
- `AH=4Fh`: buscar siguiente (DTA)
- `AH=57h`: obtener/establecer fecha/hora de archivo (solo obtener)
- `AH=4Ch`: salir

### BIOS INT 10h (modo texto)
- `AH=00h`: establecer modo de video
- `AH=0Fh`: obtener modo de video
- `AH=02h`: establecer posición del cursor
- `AH=03h`: obtener posición del cursor
- `AH=0Bh`: establecer fondo/borde
- `AH=09h`: escribir carácter+atributo
- `AH=0Eh`: salida teletipo

### BIOS INT 16h (teclado)
- `AH=00h`: leer tecla (devuelve AL)
- `AH=01h`: comprobar tecla (pone ZF si no hay)

### BIOS INT 1Ah (tiempo)
- `AH=00h`: ticks desde medianoche en CX:DX
- `AH=02h`: hora actual en BCD (CH=HH, CL=MM, DH=SS)

### DOS INT 20h
- Terminar programa (usa AL como código de salida)

## Reglas DOS 8.3
- Los nombres de archivo se validan estrictamente como 8.3 (por segmento de ruta).
- Los nombres inválidos ponen `CF=1` y `AX` en un código de error.

## Notas del analizador del ensamblador
- Se soportan constantes `equ`.
- Se soporta `org` en `.data`.
- Se soporta `dup` en `db`/`dw` (p. ej., `db 10 dup(0)`).
- Se soportan literales binarios (p. ej., `1011b`).
- Se soportan caracteres escapados en cadenas (p. ej., `\n`, `\r`, `\t`).

## Ejecutar los ejemplos
- `python src/main.py examples/hello.asm`
- `python src/main.py examples/bubble_sort.asm`

## Estructura del proyecto
- src/emu: núcleo del emulador
- examples: programas de ejemplo
