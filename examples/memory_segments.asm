.data
msg db 'Segment override demo $'
hex_digits db '0123456789ABCDEF'
val db 0

.code
start:
    mov dx, offset msg
    mov ah, 09h
    int 21h

    mov ax, ds
    mov es, ax

    mov di, offset val
    mov al, 7Bh
    mov byte ptr es:[di], al

    mov al, byte ptr ds:[di]
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
