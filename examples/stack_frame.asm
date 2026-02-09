.stack 64
.data
msg db 'Demostración de marco de pila $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov dx, offset msg
    mov ah, 09h
    int 21h

    call demo

    mov ax, 4C00h
    int 21h

demo:
    enter 6
    mov word ptr [bp-2], 1234h
    mov word ptr [bp-4], 00FFh
    mov word ptr [bp-6], 0A0Ah
    pusha
    popa

    mov ax, [bp-2]
    call print_word_hex
    call print_nl

    mov ax, [bp-4]
    call print_word_hex
    call print_nl

    mov ax, [bp-6]
    call print_word_hex
    call print_nl

    leave
    ret

print_nl:
    mov dl, 13
    mov ah, 02h
    int 21h
    mov dl, 10
    mov ah, 02h
    int 21h
    ret

print_word_hex:
    push ax
    mov al, ah
    call print_byte_hex
    pop ax
    call print_byte_hex
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
