cmake_minimum_required(VERSION 4.2)

project(master_project_ascon C)

# Language standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Default build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# Executable
add_executable(bench_ascon
    bench/main.c
    bench/util.c

    # ASCON reference implementation sources
    impl/ascon_aead128_ref/aead.c
    impl/ascon_aead128_ref/printstate.c
)

# Include directories
target_include_directories(bench_ascon PRIVATE
    include
    bench
    impl/ascon_aead128_ref
)

# Compiler warnings
if (CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(bench_ascon PRIVATE
        -Wall
        -Wextra
        -Wshadow
        -Wconversion
    )
endif()

# Platform-specific libraries
# clock_gettime on older Linux may need -lrt; safe to add math lib
if(UNIX AND NOT APPLE)
    target_link_libraries(bench_ascon PRIVATE m)
endif()