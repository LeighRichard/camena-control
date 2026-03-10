/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define PAN_LIMIT_POS_Pin GPIO_PIN_0
#define PAN_LIMIT_POS_GPIO_Port GPIOC
#define PAN_LIMIT_NEG_Pin GPIO_PIN_1
#define PAN_LIMIT_NEG_GPIO_Port GPIOC
#define TILT_LIMIT_POS_Pin GPIO_PIN_2
#define TILT_LIMIT_POS_GPIO_Port GPIOC
#define TILT_LIMIT_NEG_Pin GPIO_PIN_3
#define TILT_LIMIT_NEG_GPIO_Port GPIOC
#define TILT_STEP_Pin GPIO_PIN_0
#define TILT_STEP_GPIO_Port GPIOA
#define RAIL_STEP_Pin GPIO_PIN_6
#define RAIL_STEP_GPIO_Port GPIOA
#define RAIL_LIMIT_POS_Pin GPIO_PIN_4
#define RAIL_LIMIT_POS_GPIO_Port GPIOC
#define RAIL_LIMIT_NEG_Pin GPIO_PIN_5
#define RAIL_LIMIT_NEG_GPIO_Port GPIOC
#define PAN_DIR_Pin GPIO_PIN_0
#define PAN_DIR_GPIO_Port GPIOB
#define PAN_EN_Pin GPIO_PIN_1
#define PAN_EN_GPIO_Port GPIOB
#define TILT_DIR_Pin GPIO_PIN_2
#define TILT_DIR_GPIO_Port GPIOB
#define ESTOP_Pin GPIO_PIN_6
#define ESTOP_GPIO_Port GPIOC
#define PAN_STEP_Pin GPIO_PIN_8
#define PAN_STEP_GPIO_Port GPIOA
#define TILT_EN_Pin GPIO_PIN_3
#define TILT_EN_GPIO_Port GPIOB
#define RAIL_DIR_Pin GPIO_PIN_4
#define RAIL_DIR_GPIO_Port GPIOB
#define RAIL_EN_Pin GPIO_PIN_5
#define RAIL_EN_GPIO_Port GPIOB

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
