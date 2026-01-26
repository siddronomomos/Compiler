.data
msg_shift db 'SHL SHR SAR results $'
msg_rot db 'ROL ROR results $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov dx, offset msg_shift
    mov ah, 09h
    int 21h

    mov al, 81h
    shl al, 1
    call print_byte_hex
    call print_nl

    mov al, 80h
    shr al, 2
    call print_byte_hex
    call print_nl

    mov al, 80h
    sar al, 1
    call print_byte_hex
    call print_nl

    mov dx, offset msg_rot
    mov ah, 09h
    int 21h

    mov al, 95h
    rol al, 1
    call print_byte_hex
    call print_nl

    mov al, 95h
    ror al, 1
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
