.data
arr_len equ 8
arr db 5,3,9,1,4,2,8,6

msg_before db 'Before: $'
msg_after  db 'After : $'
hex_digits db '0123456789ABCDEF'

.code
start:
    mov dx, offset msg_before
    mov ah, 09h
    int 21h

    mov cx, arr_len
    mov si, offset arr
    call print_array

    call bubble_sort

    mov dx, offset msg_after
    mov ah, 09h
    int 21h

    mov cx, arr_len
    mov si, offset arr
    call print_array

    mov ax, 4C00h
    int 21h

; Bubble sort over the byte array at `arr`
bubble_sort:
    mov cx, arr_len
    dec cx              ; number of outer passes (len - 1)
    jz bs_done          ; arrays of length 1 are already sorted
bs_outer:
    mov si, offset arr
    mov dx, cx          ; inner loop runs `cx` comparisons
bs_inner:
    mov al, [si]
    mov ah, [si+1]
    cmp al, ah
    jle bs_no_swap
    mov [si], ah
    mov [si+1], al
bs_no_swap:
    inc si
    dec dx
    jnz bs_inner
    dec cx
    jnz bs_outer
bs_done:
    ret

; Prints CX bytes starting at DS:SI as two-digit hex values
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
    mov dl, 13
    mov ah, 02h
    int 21h
    mov dl, 10
    mov ah, 02h
    int 21h
    pop cx
    pop si
    pop dx
    pop bx
    pop ax
    ret

; Prints AL as two hex characters using `hex_digits`
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
