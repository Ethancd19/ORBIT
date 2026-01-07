cmake_minimum_required(VERSION 4.2)

project(master_project_ascon C)

# Language standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Default build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

if(NOT DEFINED USER_VERSION)
    set(USER_VERSION "manual-build")
endif()
if(NOT DEFINED BOARD)
    set(BOARD "pc")
endif()
if(NOT DEFINED ALGO_SELECTED)
    set(ALGO_SELECTED "ascon128-aead128")
endif()
if(NOT DEFINED IMPL_SELECTED)
    set(IMPL_SELECTED "ref")
endif()

if(CMAKE_SYSTEM_PROCESSOR)
    set(TARGET_ARCH ${CMAKE_SYSTEM_PROCESSOR})
else()
    set(TARGET_ARCH "unknown")
endif()

set(TARGET_NAME "bench_${ALGO_SELECTED}_${IMPL_SELECTED}")
set(IMPL_DIR "${CMAKE_SOURCE_DIR}/impl/${ALGO_SELECTED}_${IMPL_SELECTED}")

if(NOT EXISTS "${IMPL_DIR}")
    message(FATAL_ERROR
        "Implementation folder not found: ${IMPL_DIR}\n"
        "Check -DALGO_SELECTED and -DIMPL_SELECTED match your impl folder name."
    )
endif()

file(GLOB IMPL_SOURCES CONFIGURE_DEPENDS "${IMPL_DIR}/*.c")


# Executable
add_executable(${TARGET_NAME}
    bench/main.c
    bench/util.c
    ${IMPL_SOURCES}
)

# Include directories
target_include_directories(${TARGET_NAME} PRIVATE
    include
    bench
    "${IMPL_DIR}"
)

target_compile_definitions(${TARGET_NAME} PRIVATE
    ALGO_NAME=${ALGO_SELECTED}
    IMPL_NAME=${IMPL_SELECTED}
    BOARD_NAME="${BOARD}"
    VERSION_STR="${USER_VERSION}"
    TARGET_ARCH="${TARGET_ARCH}"
    COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    COMPILER_FLAGS="${CMAKE_C_FLAGS}"
)

if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${TARGET_NAME} PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()