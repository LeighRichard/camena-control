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
#include "adc.h"
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
typedef struct {
  ConfigParamId id;
  uint16_t raw_value;
} ConfigCommand;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
/* Last time the motion loop was serviced. */
static uint32_t last_motion_update = 0;
#define MOTION_UPDATE_INTERVAL_MS  1  /* 1 ms control period */
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
static ConfigCommand decode_config_command(const Command* cmd);
static StatusCode handle_config_command(const Command* cmd);
static void process_command(const Command* cmd);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static ConfigCommand decode_config_command(const Command* cmd)
{
  ConfigCommand decoded = {
    .id = config_param_from_value(cmd->value),
    .raw_value = config_raw_value(cmd->value)
  };

  return decoded;
}

static StatusCode handle_config_command(const Command* cmd)
{
  ConfigCommand config = decode_config_command(cmd);

  switch (config.id) {
    case CONFIG_MAX_VELOCITY:
      motion_set_max_velocity((float)config.raw_value);
      return STATUS_OK;

    case CONFIG_MAX_ACCEL:
      motion_set_max_accel((float)config.raw_value);
      return STATUS_OK;

    case CONFIG_PID_P:
      motion_set_pid_p(cmd->axis, (float)config.raw_value / 100.0f);
      return STATUS_OK;

    case CONFIG_PID_I:
      motion_set_pid_i(cmd->axis, (float)config.raw_value / 100.0f);
      return STATUS_OK;

    case CONFIG_PID_D:
      motion_set_pid_d(cmd->axis, (float)config.raw_value / 100.0f);
      return STATUS_OK;

    case CONFIG_WATCHDOG_TIMEOUT_MS:
      safety_set_watchdog_timeout((uint32_t)config.raw_value);
      return STATUS_OK;

    case CONFIG_WATCHDOG_ENABLE:
      safety_watchdog_enable(config.raw_value != 0u);
      return STATUS_OK;

    case CONFIG_PAN_MIN_LIMIT:
      motion_set_limit_min(AXIS_PAN, (int32_t)config_signed_value(cmd->value));
      return STATUS_OK;

    case CONFIG_PAN_MAX_LIMIT:
      motion_set_limit_max(AXIS_PAN, (int32_t)config_signed_value(cmd->value));
      return STATUS_OK;

    case CONFIG_TILT_MIN_LIMIT:
      motion_set_limit_min(AXIS_TILT, (int32_t)config_signed_value(cmd->value));
      return STATUS_OK;

    case CONFIG_TILT_MAX_LIMIT:
      motion_set_limit_max(AXIS_TILT, (int32_t)config_signed_value(cmd->value));
      return STATUS_OK;

    case CONFIG_RAIL_MIN_LIMIT:
      motion_set_limit_min(AXIS_RAIL, (int32_t)config.raw_value);
      return STATUS_OK;

    case CONFIG_RAIL_MAX_LIMIT:
      motion_set_limit_max(AXIS_RAIL, (int32_t)config.raw_value);
      return STATUS_OK;

    default:
      return STATUS_ERROR;
  }
}
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
  MX_ADC1_Init();
  MX_ADC2_Init();
  MX_USART1_UART_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  /* USER CODE BEGIN 2 */

  /* Initialize the motion, safety, and transport layers. */
  motion_init();
  safety_init();
  uart_comm_init();

  /* Pan/tilt are now PWM servos. Only the rail stepper driver needs an enable pin. */
  HAL_GPIO_WritePin(RAIL_EN_GPIO_Port, RAIL_EN_Pin, GPIO_PIN_RESET);

  last_motion_update = HAL_GetTick();

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */

    /* Process pending commands from Jetson. */
    uart_comm_process(process_command);

    /* Stop immediately if any safety interlock is active. */
    SafetyStatus safety_status = safety_check();
    if (safety_status == SAFETY_ESTOP || safety_status == SAFETY_LIMIT_HIT)
    {
      safety_emergency_stop();
    }

    /* Stop motion if communication has timed out. */
    safety_watchdog_check();

    /* Maintain a 1 ms motion-control update period. */
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
 * @brief Execute one parsed command and send a matching response.
 */
static void process_command(const Command* cmd)
{
  Response rsp = {0};
  rsp.seq = cmd->seq;
  rsp.status = STATUS_OK;

  /* Any valid command refreshes the communication watchdog. */
  safety_watchdog_feed();

  /* Reject motion commands while safety interlocks are active. */
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

  /* Execute command-specific behavior. */
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
      rsp.type = RSP_CONFIG;
      rsp.status = handle_config_command(cmd);
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

    case CMD_SET_VELOCITY:
      /* Pan/tilt keep Jetson compatibility values and convert them into servo slew rates internally.
       * Rail still uses signed steps per second.
       */
      motion_set_velocity(cmd->axis, (float)cmd->value);
      rsp.type = RSP_SET_VELOCITY;
      break;

    case CMD_STOP:
      /* STOP supports either one axis or all axes. */
      if (cmd->axis == AXIS_ALL) {
        motion_stop_all();
      } else {
        motion_stop_axis(cmd->axis);
      }
      rsp.type = RSP_STOP;
      break;

    case CMD_MOVE_ABSOLUTE:
      /* Positions use 0.01 degree / 0.01 mm units. */
      motion_move_to(cmd->axis, cmd->value);
      rsp.type = RSP_MOVE_ABSOLUTE;
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
