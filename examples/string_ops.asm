.data
src db 10h, 20h, 30h, 40h, 50h
len equ 5
dst db 5 dup(0)
msg_copy db 'REP MOVSB copied $'
msg_cmp db 'REPE CMPSB remaining CX $'
msg_find db 'REPNE SCASB remaining CX $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov ax, ds
    mov es, ax

    mov dx, offset msg_copy
    mov ah, 09h
    int 21h

    mov si, offset src
    mov di, offset dst
    mov cx, len
    rep movsb

    mov cx, len
    mov si, offset dst
    call print_array
    call print_nl

    mov dx, offset msg_cmp
    mov ah, 09h
    int 21h

    mov si, offset src
    mov di, offset dst
    mov cx, len
    repe cmpsb
    mov ax, cx
    call print_word_hex
    call print_nl

    mov dx, offset msg_find
    mov ah, 09h
    int 21h

    mov al, 30h
    mov di, offset dst
    mov cx, len
    repne scasb
    mov ax, cx
    call print_word_hex
    call print_nl

    mov ax, 4C00h
    int 21h

print_array:
    push ax
    push bx
    push dx
    push si
    push cx
pa_loop:
    mov al, [si]
    call print_byte_hex
    mov dl, ' '
    mov ah, 02h
    int 21h
    inc si
    loop pa_loop
    pop cx
    pop si
    pop dx
    pop bx
    pop ax
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
