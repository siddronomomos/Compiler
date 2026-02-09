.data
msg db 'Hola desde el emulador MASM$'

.code
    mov dx, offset msg
    mov ah, 09h
    int 21h

    mov al, 0
    mov ah, 4Ch
    int 21h
