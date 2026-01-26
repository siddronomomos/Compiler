.data
msg_add db 'ADD and ADC results $'
msg_sub db 'SUB and SBB results $'
msg_logic db 'AND OR XOR TEST results $'
msg_misc db 'INC DEC NEG NOT results $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov dx, offset msg_add
    mov ah, 09h
    int 21h

    mov al, 05h
    add al, 03h
    call print_byte_hex
    call print_nl

    stc
    adc al, 01h
    call print_byte_hex
    call print_nl

    mov dx, offset msg_sub
    mov ah, 09h
    int 21h

    mov al, 10h
    sub al, 02h
    call print_byte_hex
    call print_nl

    stc
    sbb al, 01h
    call print_byte_hex
    call print_nl

    mov dx, offset msg_logic
    mov ah, 09h
    int 21h

    mov al, 0Fh
    and al, 33h
    call print_byte_hex
    call print_nl

    mov al, 55h
    or al, 0Ah
    call print_byte_hex
    call print_nl

    mov al, 5Ah
    xor al, 0FFh
    call print_byte_hex
    call print_nl

    mov al, 3Ch
    test al, 0Fh
    call print_byte_hex
    call print_nl

    mov dx, offset msg_misc
    mov ah, 09h
    int 21h

    mov al, 0FFh
    inc al
    call print_byte_hex
    call print_nl

    dec al
    call print_byte_hex
    call print_nl

    neg al
    call print_byte_hex
    call print_nl

    not al
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
