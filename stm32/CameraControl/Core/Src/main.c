/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "dma.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "protocol.h"
#include "motion.h"
#include "safety.h"
#include "uart_comm.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
/* 上次运动更新时间 */
static uint32_t last_motion_update = 0;
#define MOTION_UPDATE_INTERVAL_MS  1  /* 1ms 更新周期 */
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
static void process_command(const Command* cmd);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART1_UART_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  /* USER CODE BEGIN 2 */
  
  /* 初始化业务模块 */
  motion_init();
  safety_init();
  uart_comm_init();
  
  /* 使能电机驱动器 (低电平使能 TMC2209) */
  HAL_GPIO_WritePin(PAN_EN_GPIO_Port, PAN_EN_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(TILT_EN_GPIO_Port, TILT_EN_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(RAIL_EN_GPIO_Port, RAIL_EN_Pin, GPIO_PIN_RESET);
  
  last_motion_update = HAL_GetTick();

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    
    /* 处理 UART 接收到的指令 */
    uart_comm_process(process_command);
    
    /* 执行安全检查 */
    SafetyStatus safety_status = safety_check();
    if (safety_status == SAFETY_ESTOP || safety_status == SAFETY_LIMIT_HIT)
    {
      safety_emergency_stop();
    }
    
    /* 检查通信看门狗 */
    safety_watchdog_check();
    
    /* 定时更新运动控制 (1ms) */
    uint32_t current_time = HAL_GetTick();
    if (current_time - last_motion_update >= MOTION_UPDATE_INTERVAL_MS)
    {
      motion_update();
      last_motion_update = current_time;
    }
    
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 8;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 4;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

/**
 * @brief 处理接收到的指令
 */
static void process_command(const Command* cmd)
{
  Response rsp;
  rsp.status = STATUS_OK;
  
  /* 喂狗 */
  safety_watchdog_feed();
  
  /* 检查安全状态 */
  SafetyStatus safety_status = safety_check();
  if (safety_status == SAFETY_ESTOP)
  {
    rsp.status = STATUS_ESTOP;
    rsp.type = (ResponseType)(cmd->type | 0x80);
    uart_comm_send_response(&rsp);
    return;
  }
  else if (safety_status == SAFETY_LIMIT_HIT)
  {
    rsp.status = STATUS_LIMIT_HIT;
    rsp.type = (ResponseType)(cmd->type | 0x80);
    uart_comm_send_response(&rsp);
    return;
  }
  
  /* 处理指令 */
  switch (cmd->type)
  {
    case CMD_POSITION:
      motion_move_to(cmd->axis, cmd->value);
      rsp.type = RSP_POSITION;
      break;
      
    case CMD_STATUS:
      {
        Position pos = motion_get_current();
        rsp.type = RSP_STATUS;
        rsp.pan_pos = pos.pan_angle;
        rsp.tilt_pos = pos.tilt_angle;
        rsp.rail_pos = pos.rail_pos;
      }
      break;
      
    case CMD_CONFIG:
      {
        /* 处理配置指令 */
        rsp.type = RSP_CONFIG;
        
        /* 配置数据在 cmd->value 中编码
         * 格式: 
         *   - value 高16位: 配置参数ID
         *   - value 低16位: 配置值
         */
        uint16_t config_id = (cmd->value >> 16) & 0xFFFF;
        uint16_t config_value = cmd->value & 0xFFFF;
        
        switch (config_id) {
          case 0x0001:  /* 设置最大速度 */
            motion_set_max_velocity((float)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0002:  /* 设置最大加速度 */
            motion_set_max_accel((float)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0003:  /* 设置PID参数P */
            motion_set_pid_p(cmd->axis, (float)config_value / 100.0f);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0004:  /* 设置PID参数I */
            motion_set_pid_i(cmd->axis, (float)config_value / 100.0f);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0005:  /* 设置PID参数D */
            motion_set_pid_d(cmd->axis, (float)config_value / 100.0f);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0010:  /* 设置看门狗超时 (ms) */
            safety_set_watchdog_timeout((uint32_t)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0011:  /* 启用/禁用看门狗 */
            safety_watchdog_enable(config_value != 0);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0020:  /* 设置位置限位 - Pan最小值 */
            motion_set_limit_min(AXIS_PAN, (int32_t)(int16_t)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0021:  /* 设置位置限位 - Pan最大值 */
            motion_set_limit_max(AXIS_PAN, (int32_t)(int16_t)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0022:  /* 设置位置限位 - Tilt最小值 */
            motion_set_limit_min(AXIS_TILT, (int32_t)(int16_t)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0023:  /* 设置位置限位 - Tilt最大值 */
            motion_set_limit_max(AXIS_TILT, (int32_t)(int16_t)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0024:  /* 设置位置限位 - Rail最小值 */
            motion_set_limit_min(AXIS_RAIL, (int32_t)(int16_t)config_value);
            rsp.status = STATUS_OK;
            break;
            
          case 0x0025:  /* 设置位置限位 - Rail最大值 */
            motion_set_limit_max(AXIS_RAIL, (int32_t)(int16_t)config_value);
            rsp.status = STATUS_OK;
            break;
            
          default:
            rsp.status = STATUS_ERROR;
            break;
        }
      }
      break;
      
    case CMD_ESTOP:
      safety_emergency_stop();
      rsp.type = RSP_ESTOP;
      rsp.status = STATUS_ESTOP;
      break;
      
    case CMD_HOME:
      motion_home(cmd->axis);
      rsp.type = RSP_HOME;
      break;
      
    default:
      rsp.status = STATUS_ERROR;
      rsp.type = (ResponseType)(cmd->type | 0x80);
      break;
  }
  
  uart_comm_send_response(&rsp);
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
