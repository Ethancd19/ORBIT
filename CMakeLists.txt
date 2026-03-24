cmake_minimum_required(VERSION 3.13)

include ($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(ECLIPSE C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

pico_sdk_init()

if(NOT DEFINED BOARD)
    set(BOARD "pico")
endif()
if(NOT DEFINED ALGO_SELECTED)
    set(ALGO_SELECTED "ascon_aead128")
endif()

set(TARGET_NAME "ECLIPSE_${ALGO_SELECTED}_${BOARD}")
set(ALGO_DIR "${CMAKE_SOURCE_DIR}/algorithms/${ALGO_SELECTED}")

if(NOT EXISTS "${ALGO_DIR}")
    message(FATAL_ERROR 
        "Algorithm folder not found: ${ALGO_DIR}\n"
        "Check -DALGO_SELECTED matches your algorithm folder name in ${CMAKE_SOURCE_DIR}/algorithms/"
    )
endif()

file(GLOB ALGO_SOURCES CONFIGURE_DEPENDS "${ALGO_DIR}/*.c")

add_executable(${TARGET_NAME}
    bench/main.c
    bench/util.c
    ${ALGO_SOURCES}
)

target_include_directories(${TARGET_NAME} PRIVATE
    include
    bench
    "${ALGO_DIR}"
    "platforms/${BOARD}"
)

target_compile_definitions(${TARGET_NAME} PRIVATE
    ALGO_NAME=${ALGO_SELECTED}
    BOARD_NAME="${BOARD}"
    VERSION_STR="0.1.0"
    COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    COMPILER_FLAGS="-O2"
    TARGET_ARCH="armv6-m"
)

target_compile_options(${TARGET_NAME} PRIVATE -O2 -Wall -Wextra)

target_link_libraries(${TARGET_NAME}
    pico_stdlib
    hardware_gpio
)

pico_enable_stdio_usb(${TARGET_NAME} 1)
pico_enable_stdio_uart(${TARGET_NAME} 0)

pico_add_extra_outputs(${TARGET_NAME})