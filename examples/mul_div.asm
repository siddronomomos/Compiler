.data
msg_mul db 'MUL and IMUL results $'
msg_div db 'DIV and IDIV results $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov dx, offset msg_mul
    mov ah, 09h
    int 21h

    mov al, 12h
    mov bl, 10h
    mul bl
    call print_word_hex
    call print_nl

    mov ax, 0FF80h
    mov bx, 0004h
    imul bx
    call print_word_hex
    mov ax, dx
    call print_word_hex
    call print_nl

    mov dx, offset msg_div
    mov ah, 09h
    int 21h

    mov ax, 0030h
    mov bl, 06h
    div bl
    call print_byte_hex
    mov al, ah
    call print_byte_hex
    call print_nl

    mov dx, 0FFFFh
    mov ax, 0FFF0h
    mov bx, 0004h
    idiv bx
    call print_word_hex
    mov ax, dx
    call print_word_hex
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
