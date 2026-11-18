/* Copyright (c) 2026 getBoolean. SPDX-License-Identifier: BSD-3-Clause */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

void qsort(void *base, size_t count, size_t size,
           int (*compare)(const void *, const void *)) {
  if (count < 2 || size == 0) return;
  if (count > SIZE_MAX / size) abort();
  unsigned char *buffer = malloc(count * size);
  if (buffer == NULL) abort();
  unsigned char *input = base;
  for (size_t width = 1; width < count;
       width = width > count / 2 ? count : width * 2) {
    for (size_t start = 0; start < count;) {
      size_t middle = start + (width < count - start ? width : count - start);
      size_t end = middle + (width < count - middle ? width : count - middle);
      size_t left = start, right = middle;
      for (size_t at = start; at < end; ++at) {
        int take_left = right == end ||
            (left < middle && compare(input + left * size,
                                      input + right * size) <= 0);
        size_t index = take_left ? left++ : right++;
        memcpy(buffer + at * size, input + index * size, size);
      }
      memcpy(input + start * size, buffer + start * size, (end - start) * size);
      start = end;
    }
  }
  free(buffer);
}
