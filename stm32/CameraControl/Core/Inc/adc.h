/**
  ******************************************************************************
  * @file    adc.h
  * @brief   This file contains all the function prototypes for
  *          the adc.c file
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __ADC_H
#define __ADC_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Exported types ------------------------------------------------------------*/
/* ADC 句柄结构体 - 如果 HAL_ADC_MODULE_ENABLED 未定义，提供空定义 */
#ifdef HAL_ADC_MODULE_ENABLED

/* ADC 初始化函数 */
void MX_ADC1_Init(void);
void MX_ADC2_Init(void);

#endif /* HAL_ADC_MODULE_ENABLED */

#ifdef __cplusplus
}
#endif

#endif /* __ADC_H */
