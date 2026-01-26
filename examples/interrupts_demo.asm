.data
bios_msg db 'BIOS teletype output $'
kb_msg db 'Press a key $'
time_msg db 'Current time BCD HH MM SS $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov si, offset bios_msg
bios_loop:
    lodsb
    cmp al, '$'
    je bios_done
    mov ah, 0Eh
    int 10h
    jmp bios_loop
bios_done:
    call print_nl

    mov dx, offset kb_msg
    mov ah, 09h
    int 21h
    mov ah, 00h
    int 16h
    mov dl, al
    mov ah, 02h
    int 21h
    call print_nl

    mov dx, offset time_msg
    mov ah, 09h
    int 21h
    mov ah, 02h
    int 1Ah
    mov al, ch
    call print_byte_hex
    mov dl, ' '
    mov ah, 02h
    int 21h
    mov al, cl
    call print_byte_hex
    mov dl, ' '
    mov ah, 02h
    int 21h
    mov al, dh
    call print_byte_hex
    call print_nl

    int 20h

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
