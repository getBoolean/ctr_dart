.section .ctr_test_image,"aw"
.global ctr_test_image_start
ctr_test_image_start:
.space 128
.global ctr_test_image_end
ctr_test_image_end:
.section .note.GNU-stack,"",@progbits
