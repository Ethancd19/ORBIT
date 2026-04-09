#ifndef PLATFORM_H
#define PLATFORM_H

#include <stdint.h>
#include "stm32f4xx_hal.h"

#define PLATFORM_FREQ_HZ    16000000UL
#define TRIGGER_PIN_PORT    GPIOA
#define TRIGGER_PIN         GPIO_PIN_8

extern UART_HandleTypeDef huart2;

static inline int __io_putchar(int ch) {
    HAL_UART_Transmit(&huart2, (uint8_t *)&ch, 1, HAL_MAX_DELAY);
    return ch;
}

static inline void _dwt_init(void) {
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL  |= DWT_CTRL_CYCCNTENA_Msk;
}

static inline void platform_init(void) {
    /* Raw register UART test - before HAL_Init */
    /* Enable GPIOA and USART2 clocks directly */
    RCC->AHB1ENR |= (1 << 0);   /* GPIOA clock */
    RCC->APB1ENR |= (1 << 17);  /* USART2 clock */
    
    /* PA2 = AF7 (USART2 TX) */
    GPIOA->MODER   &= ~(3 << 4);
    GPIOA->MODER   |=  (2 << 4);   /* Alternate function */
    GPIOA->AFR[0]  &= ~(0xF << 8);
    GPIOA->AFR[0]  |=  (7 << 8);   /* AF7 = USART2 */
    
    /* Configure USART2: 115200 baud at 16MHz HSI */
    /* BRR = 16000000 / 115200 = 138.8 -> mantissa=138, fraction=13 */
    USART2->BRR = (138 << 4) | 13;
    USART2->CR1 = (1 << 3) | (1 << 13); /* TE | UE */
    
    /* Send "X\r\n" */
    while (!(USART2->SR & (1 << 7)));  /* Wait TXE */
    USART2->DR = 'X';
    while (!(USART2->SR & (1 << 7)));
    USART2->DR = '\r';
    while (!(USART2->SR & (1 << 7)));
    USART2->DR = '\n';
    while (!(USART2->SR & (1 << 6)));  /* Wait TC */
    
    HAL_Init();

    __HAL_RCC_USART2_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef gpio = {0};
    gpio.Pin       = GPIO_PIN_2 | GPIO_PIN_3;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &gpio);

    huart2.Instance          = USART2;
    huart2.Init.BaudRate     = 115200;
    huart2.Init.WordLength   = UART_WORDLENGTH_8B;
    huart2.Init.StopBits     = UART_STOPBITS_1;
    huart2.Init.Parity       = UART_PARITY_NONE;
    huart2.Init.Mode         = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart2);

    gpio.Pin       = TRIGGER_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = 0;
    HAL_GPIO_Init(TRIGGER_PIN_PORT, &gpio);
    HAL_GPIO_WritePin(TRIGGER_PIN_PORT, TRIGGER_PIN, GPIO_PIN_RESET);

    _dwt_init();
}

static inline uint64_t platform_cycle_count(void) {
    return (uint64_t)(DWT->CYCCNT);
}

static inline void platform_trigger_high(void) {
    HAL_GPIO_WritePin(TRIGGER_PIN_PORT, TRIGGER_PIN, GPIO_PIN_SET);
}

static inline void platform_trigger_low(void) {
    HAL_GPIO_WritePin(TRIGGER_PIN_PORT, TRIGGER_PIN, GPIO_PIN_RESET);
}

static inline uint32_t platform_freq_hz(void) {
    return PLATFORM_FREQ_HZ;
}

static inline int platform_stdio_ready(void) { return 1; }
static inline void platform_delay_ms(uint32_t ms) { HAL_Delay(ms); }

#endif /* PLATFORM_H */