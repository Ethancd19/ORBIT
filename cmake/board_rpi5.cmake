# ===============================================================
# board_rpi5.cmake - Raspberry Pi 5 (BCM2712, Cortex-A76 / AArch64)
# Included by top-level CMakeLists.txt when BOARD=rpi5 is selected
# Native Linux target: builds a host executable and runs it locally.
# ===============================================================

file(GLOB ALGO_SOURCES CONFIGURE_DEPENDS "${ALGO_DIR}/*.c")

set(TARGET_NAME "ORBIT_${ALGO_SELECTED}_rpi5")

if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(aarch64|arm64)$")
    set(RPI5_TARGET_ARCH "aarch64")
else()
    set(RPI5_TARGET_ARCH "${CMAKE_SYSTEM_PROCESSOR}")
endif()

add_executable(${TARGET_NAME}
    bench/main.c
    bench/util.c
    ${ALGO_SOURCES}
)

target_include_directories(${TARGET_NAME} PRIVATE
    include
    bench
    "${ALGO_DIR}"
    "platforms/rpi5"
)

target_compile_definitions(${TARGET_NAME} PRIVATE
    _POSIX_C_SOURCE=200809L
    ALGO_NAME=${ALGO_SELECTED}
    BOARD_NAME="rpi5"
    VERSION_STR="0.1.0"
    COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    COMPILER_FLAGS="-O2"
    TARGET_ARCH="${RPI5_TARGET_ARCH}"
    PLATFORM_EXIT_AFTER_BENCHMARK=1
)

if(ALGO_SELECTED STREQUAL "aes_128_gcm")
    target_compile_definitions(${TARGET_NAME} PRIVATE SLOW_ALGO=1)
endif()

if(ALGO_SELECTED STREQUAL "ml_kem_512")
    target_compile_definitions(${TARGET_NAME} PRIVATE IS_KEM=1 SLOW_ALGO=1)
endif()

target_compile_options(${TARGET_NAME} PRIVATE
    -O2
    -Wall
    -Wextra
)

target_link_libraries(${TARGET_NAME} PRIVATE m)
