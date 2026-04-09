#include "stm32f4xx_hal.h"

static void fault_puts(const char *str) {
    while (*str) {
        while (!(USART2->SR & USART_SR_TXE)) {}
        USART2->DR = (uint8_t)(*str++);
    }
    while (!(USART2->SR & USART_SR_TC)) {}
}

void SysTick_Handler(void) {
    HAL_IncTick();
}

void HardFault_Handler(void) {
    fault_puts("HardFault\r\n");
    while (1) {}
}

void MemManage_Handler(void) {
    fault_puts("MemManage\r\n");
    while (1) {}
}

void BusFault_Handler(void) {
    fault_puts("BusFault\r\n");
    while (1) {}
}

void UsageFault_Handler(void) {
    fault_puts("UsageFault\r\n");
    while (1) {}
}

void NMI_Handler(void) {
    fault_puts("NMI\r\n");
    while (1) {}
}
