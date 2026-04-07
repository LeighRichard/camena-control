cmake_minimum_required(VERSION 3.22)

#
# This file is generated only once,
# and is not re-generated if converter is called multiple times.
#
# User is free to modify the file as much as necessary
#

# Setup compiler settings
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)


# Define the build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug")
endif()

# Set the project name
set(CMAKE_PROJECT_NAME CameraControl)

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME})
message("Build type: " ${CMAKE_BUILD_TYPE})

# Enable CMake support for ASM and C languages
enable_language(C ASM)

get_filename_component(ARM_GNU_BIN_DIR "${CMAKE_C_COMPILER}" DIRECTORY)
find_program(ARM_NONE_EABI_OBJCOPY
    NAMES arm-none-eabi-objcopy arm-none-eabi-objcopy.exe
    HINTS "${ARM_GNU_BIN_DIR}"
    REQUIRED
    NO_DEFAULT_PATH
)
find_program(ARM_NONE_EABI_SIZE
    NAMES arm-none-eabi-size arm-none-eabi-size.exe
    HINTS "${ARM_GNU_BIN_DIR}"
    REQUIRED
    NO_DEFAULT_PATH
)

# Create an executable object type
add_executable(${CMAKE_PROJECT_NAME})

# Add STM32CubeMX generated sources
add_subdirectory(cmake/stm32cubemx)

# Link directories setup
target_link_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined library search paths
)

# Add sources to executable
target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user sources here
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined include paths
)

# Add project symbols (macros)
target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined symbols
)

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx

    # Add user defined libraries
)

set(FIRMWARE_ELF "${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.elf")
set(FIRMWARE_HEX "${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.hex")
set(FIRMWARE_BIN "${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin")

# Keep the link rule free of nested POST_BUILD cmd.exe wrappers. Generating
# HEX/BIN as a separate build step is much more stable on Windows when the
# project path contains spaces.
add_custom_command(
    OUTPUT "${FIRMWARE_HEX}" "${FIRMWARE_BIN}"
    COMMAND "${ARM_NONE_EABI_OBJCOPY}" -O ihex "${CMAKE_PROJECT_NAME}.elf" "${CMAKE_PROJECT_NAME}.hex"
    COMMAND "${ARM_NONE_EABI_OBJCOPY}" -O binary "${CMAKE_PROJECT_NAME}.elf" "${CMAKE_PROJECT_NAME}.bin"
    COMMAND "${ARM_NONE_EABI_SIZE}" "${CMAKE_PROJECT_NAME}.elf"
    DEPENDS ${CMAKE_PROJECT_NAME}
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    COMMENT "Generating HEX/BIN firmware artifacts"
    VERBATIM
)

add_custom_target(firmware_artifacts ALL
    DEPENDS "${FIRMWARE_HEX}" "${FIRMWARE_BIN}"
)

find_program(STM32_PROGRAMMER_CLI
    NAMES STM32_Programmer_CLI STM32_Programmer_CLI.exe
    HINTS
        "D:/STM32CubeCLT_1.20.0/STM32CubeProgrammer/bin"
        "D:/STM32CubeCLT_1.20.0/programmer/2.22.0+st.1/bin"
        "D:/STM32CubeCLT_1.20.0/programmer/2.21.0/bin"
        "D:/STM32CubeCLT_1.20.0/programmer/2.20.0/bin"
)

if(STM32_PROGRAMMER_CLI)
    add_custom_target(erase
        COMMAND "${STM32_PROGRAMMER_CLI}" -c port=SWD mode=UR reset=HWrst -e all
        COMMENT "Erasing target via STM32CubeProgrammer"
        USES_TERMINAL
        VERBATIM
    )

    add_custom_target(flash
        COMMAND "${STM32_PROGRAMMER_CLI}" -c port=SWD mode=UR reset=HWrst
                -w "${FIRMWARE_BIN}" 0x08000000 -v -rst
        DEPENDS firmware_artifacts
        COMMENT "Flashing ${CMAKE_PROJECT_NAME}.bin via STM32CubeProgrammer"
        USES_TERMINAL
        VERBATIM
    )
else()
    message(WARNING "STM32_Programmer_CLI not found. 'flash' and 'erase' targets are unavailable.")
endif()
