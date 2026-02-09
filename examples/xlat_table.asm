.data
table db 11h, 22h, 33h, 44h, 55h
msg db 'Resultado de XLAT $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov dx, offset msg
    mov ah, 09h
    int 21h

    mov bx, offset table
    mov al, 03h
    xlat
    call print_byte_hex
    call print_nl

    mov ax, 4C00h
    int 21h

print_nl:
    mov dl, 13
    mov ah, 02h
    int 21h
    mov dl, 10
    mov ah, 02h
    int 21h
    ret

print_byte_hex:
    push ax
    push bx
    push si
    mov bl, al
    shr bl, 4
    xor bh, bh
    mov si, offset hex_digits
    mov dl, [si+bx]
    mov ah, 02h
    int 21h
    mov bl, al
    and bl, 0Fh
    xor bh, bh
    mov dl, [si+bx]
    mov ah, 02h
    int 21h
    pop si
    pop bx
    pop ax
    ret
