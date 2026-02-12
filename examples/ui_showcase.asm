.stack 64                 ; Pila pequena para la demo
.data
buf db 16 dup(0)          ; Buffer usado para el visor de memoria
word_val dw 0000h         ; Variable word para copiar registros
.code
start:
    mov ax, 1234h         ; Cargar registros con valores faciles de ver
    mov bx, 00F0h
    mov cx, 0003h
    mov dx, 0FF0h
    lea si, buf            ; Apuntar SI al inicio del buffer
    lea di, buf+8          ; Apuntar DI a la mitad del buffer
    mov bp, 0100h          ; Fijar BP con un valor visible

    mov word_val, ax       ; Guardar AX en variable de memoria
    mov byte ptr [buf], 11h
    mov byte ptr [buf+1], 22h
    mov word ptr [buf+2], 3344h
    mov word ptr [buf+4], 5566h
    mov word ptr [buf+6], 7788h

    push ax                ; Conservar registros durante demo_flags
    push bx
    push cx
    call demo_flags        ; Provocar cambios en los flags
    pop cx
    pop bx
    pop ax

    call demo_stack_frame  ; Probar ENTER/LEAVE y operaciones de pila

    mov ax, 4C00h          ; Salir con codigo de retorno 00h
    int 21h

demo_flags:
    mov al, 0FFh           ; Sumar overflow para CF/ZF
    add al, 01h
    mov al, 7Fh            ; Sumar para activar OF
    add al, 01h
    mov al, 80h            ; Restar para alternar SF/CF
    sub al, 01h
    cmp al, 80h            ; Comparar para ajustar flags
    test al, 0Fh           ; Test para ajustar ZF/PF
    ret

demo_stack_frame:
    enter 8                ; Crear marco de pila con locales
    mov word ptr [bp-2], 0A0Ah
    mov word ptr [bp-4], 0B0Bh
    mov word ptr [bp-6], 0C0Ch
    mov word ptr [bp-8], 0D0Dh
    pusha                  ; Guardar todos los registros y restaurar
    popa
    leave                  ; Restaurar BP y SP
    ret
